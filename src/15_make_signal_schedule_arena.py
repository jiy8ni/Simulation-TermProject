"""신호 녹색창 -> Arena 신호 컨트롤 로직용 토글 이벤트 타임라인.

Arena Hold(Scan: Green[movement]==1) 를 구동하려면, 각 이동류(movement)의 Green 상태변수가
언제 1(녹색)/0(적색)으로 바뀌는지 이벤트 목록이 필요하다. signal_green_windows_labeled.csv의
녹색 구간(green_start_sec, green_end_sec)을 읽어 movement별 토글 이벤트로 펼친다.

movement_key = inter_id + approach_node + dir_code  (예: 215173_216288_s)

출력: data_processed/signal_schedule_arena.csv
  (intersection_group, movement_key, inter_id, approach_node, dir_code, direction,
   event_time_sec, green)   -- event_time_sec 시점에 Green을 green(1/0)으로 설정
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data_processed"
GROUPS = ["15", "16"]  # Tier 1: 개별 교차로


def main() -> None:
    w = pd.read_csv(PROC / "signal_green_windows_labeled.csv", encoding="utf-8-sig")
    w = w[w["intersection_group"].astype(str).isin(GROUPS)].copy()
    w["movement_key"] = (
        w["inter_id"].astype(str) + "_" + w["approach_node"].astype(str) + "_" + w["dir_code"].astype(str)
    )

    rows = []
    for key, grp in w.groupby("movement_key", sort=False):
        grp = grp.sort_values("green_start_sec")
        first = grp.iloc[0]
        meta = {
            "intersection_group": first["intersection_group"],
            "movement_key": key,
            "inter_id": int(first["inter_id"]),
            "approach_node": int(first["approach_node"]),
            "dir_code": first["dir_code"],
            "direction": first["direction"],
        }
        for r in grp.itertuples(index=False):
            rows.append({**meta, "event_time_sec": float(r.green_start_sec), "green": 1})
            rows.append({**meta, "event_time_sec": float(r.green_end_sec), "green": 0})

    out_df = (
        pd.DataFrame(rows)
        .sort_values(["inter_id", "approach_node", "dir_code", "event_time_sec", "green"])
        .reset_index(drop=True)
    )
    out = PROC / "signal_schedule_arena.csv"
    out_df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[ok] {out.name}: {len(out_df)} rows, {out_df['movement_key'].nunique()} movements")
    summary = (
        out_df[out_df["green"] == 1]
        .groupby(["inter_id", "approach_node", "dir_code"])
        .size()
        .reset_index(name="n_green_windows")
    )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
