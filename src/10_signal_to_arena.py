"""signal_plan_as_is.csv -> ARENA용 이동류별 신호 스케줄로 변환.

ARENA는 'grrrrrrrrrrGGGGyrrrrr' 같은 신호 문자열을 직접 이해하지 못한다.
그래서 문자열의 각 자리(=이동류)를 시간축으로 풀어,
"이동류 k가 몇 초에 녹색/황색/적색인가" 형태의 테이블로 바꾼다.

출력 (data_processed/):
  1) signal_movement_state.csv : 행 단위 long 포맷
       (group, inter_id, movement, char_index, start_sec, end_sec, duration_sec, state)
  2) signal_green_windows.csv  : 이동류별로 연속된 '통행 가능' 구간을 병합한 테이블
       (group, inter_id, movement, green_start_sec, green_end_sec, green_dur_sec)
       -> ARENA Hold(Wait for Signal) + Signal 제어 엔티티에 바로 공급

문자 해석:
  'G','g' -> green(통행 가능)
  'y','Y' -> yellow
  'r'      -> red
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data_processed" / "signal_plan_as_is.csv"
OUT_LONG = ROOT / "data_processed" / "signal_movement_state.csv"
OUT_GREEN = ROOT / "data_processed" / "signal_green_windows.csv"

# 황색을 '통행 가능'으로 볼지 여부. False면 녹색만 통행으로 본다.
YELLOW_AS_PASSABLE = False


def classify(ch: str) -> str:
    if ch in ("G", "g"):
        return "green"
    if ch in ("y", "Y"):
        return "yellow"
    return "red"


def main() -> None:
    df = pd.read_csv(SRC)

    long_rows = []
    for row in df.itertuples(index=False):
        start = float(row.offset_sec)
        end = start + float(row.duration_sec)
        for idx, ch in enumerate(str(row.signal_state)):
            long_rows.append(
                {
                    "intersection_group": row.intersection_group,
                    "inter_id": row.inter_id,
                    "movement": idx + 1,          # 1-based(사람이 읽기 쉬움)
                    "char_index": idx,            # 0-based(원본 문자열 위치)
                    "phase": row.phase,
                    "start_sec": start,
                    "end_sec": end,
                    "duration_sec": float(row.duration_sec),
                    "state": classify(ch),
                }
            )

    long_df = pd.DataFrame(long_rows).sort_values(
        ["intersection_group", "inter_id", "movement", "start_sec"]
    ).reset_index(drop=True)
    long_df.to_csv(OUT_LONG, index=False, encoding="utf-8-sig")
    print(f"[ok] {OUT_LONG.name}: {len(long_df)} rows")

    # ---- 연속된 통행 가능 구간 병합 ----
    passable = {"green", "yellow"} if YELLOW_AS_PASSABLE else {"green"}
    long_df["passable"] = long_df["state"].isin(passable)

    green_rows = []
    keys = ["intersection_group", "inter_id", "movement"]
    for key, grp in long_df.groupby(keys, sort=False):
        grp = grp.sort_values("start_sec")
        seg_start = None
        prev_end = None
        for r in grp.itertuples(index=False):
            if r.passable:
                if seg_start is None:
                    seg_start = r.start_sec
                elif r.start_sec > prev_end + 1e-6:  # 끊긴 구간 -> 이전 구간 닫기
                    green_rows.append((*key, seg_start, prev_end, prev_end - seg_start))
                    seg_start = r.start_sec
                prev_end = r.end_sec
            else:
                if seg_start is not None:
                    green_rows.append((*key, seg_start, prev_end, prev_end - seg_start))
                    seg_start = None
        if seg_start is not None:
            green_rows.append((*key, seg_start, prev_end, prev_end - seg_start))

    green_df = pd.DataFrame(
        green_rows,
        columns=[
            "intersection_group",
            "inter_id",
            "movement",
            "green_start_sec",
            "green_end_sec",
            "green_dur_sec",
        ],
    )
    green_df.to_csv(OUT_GREEN, index=False, encoding="utf-8-sig")
    print(f"[ok] {OUT_GREEN.name}: {len(green_df)} rows")

    # ---- 요약: 이동류별 총 녹색시간 / 녹색구간 수 ----
    summary = (
        green_df.groupby(["intersection_group", "inter_id", "movement"])
        .agg(n_green=("green_dur_sec", "size"), total_green_sec=("green_dur_sec", "sum"))
        .reset_index()
    )
    print("\n[요약] 이동류별 통행시간 (앞부분):")
    print(summary.to_string(index=False, max_rows=25))


if __name__ == "__main__":
    main()
