"""신호 1주기 템플릿 추출 (신호 현시/주기 조정 시나리오의 기반).

현재 신호는 고정식(현시 = 녹색 57s + 황색 3s, 60s 슬롯으로 순환)이다. signal_plan_as_is.csv는
1시간치를 펼친 '재생본'이라 "어느 현시를 몇 초로" 식의 수정이 직접 안 된다. 이 스크립트는
신호를 **현시(phase) 단위 템플릿**으로 정리한다: 각 현시가 어떤 이동류를 녹색으로 켜는지 +
표준 녹색/황색 길이 + 등장 횟수. 이 표의 녹색 길이(split)를 바꾸는 것이 곧 신호 개선 시나리오다.

입력:
  - data_processed/signal_plan_as_is.csv      (현시 구간: offset, duration, signal_state)
  - data_processed/signal_movement_map.csv    (linkIndex=문자위치 -> 이동류/방향/진입로)
출력:
  - data_processed/signal_cycle_template.csv  (교차로별 현시 템플릿)
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data_processed"
GROUPS = {"15": 215173, "16": 215174}
MIN_GREEN_SEC = 10.0  # 본녹색(57s)만; 3s 황색/전이 현시는 제외
MAIN_PHASE_MIN_OCC = 3  # 이 횟수 이상 반복돼야 '주요 현시'(녹화 경계의 1회성 전이 현시 제외)


def green_indices(state: str) -> list[int]:
    return [i for i, c in enumerate(str(state)) if c in ("G", "g")]


def main() -> None:
    plan = pd.read_csv(PROC / "signal_plan_as_is.csv")
    mm = pd.read_csv(PROC / "signal_movement_map.csv", encoding="utf-8-sig")

    rows = []
    for grp, iid in GROUPS.items():
        # linkIndex(=문자 위치) -> 이동류 라벨
        sub_map = mm[mm["inter_id"] == iid]
        idx2mv = {
            int(r.linkIndex): f"{iid}_{r.approach_node}_{r.dir_code}"
            for r in sub_map.itertuples(index=False)
        }

        g = plan[(plan["intersection_group"] == grp) & (plan["inter_id"] == iid)]
        greens = g[g["duration_sec"] >= MIN_GREEN_SEC].sort_values("offset_sec")
        # 현시(=고유 녹색 신호상태)별로 묶기
        order, seen = [], set()
        for st in greens["signal_state"]:
            if st not in seen:
                seen.add(st); order.append(st)

        # 주요 현시 = 일정 횟수 이상 반복(녹화 경계의 1회성 전이 현시 제외). 주기는 주요 현시 기준.
        occ_count = {st: int((greens["signal_state"] == st).sum()) for st in order}
        n_main = sum(1 for st in order if occ_count[st] >= MAIN_PHASE_MIN_OCC)
        for phase_id, state in enumerate(order, start=1):
            occ = greens[greens["signal_state"] == state]
            movements = sorted({idx2mv[i] for i in green_indices(state) if i in idx2mv})
            is_main = occ_count[state] >= MAIN_PHASE_MIN_OCC
            rows.append({
                "intersection_group": grp,
                "inter_id": iid,
                "phase_id": phase_id,
                "is_main_phase": is_main,
                "n_main_phases": n_main,
                "cycle_len_sec_est": n_main * 60,             # 주요 현시 × 60s 슬롯(녹57+황3)
                "green_sec": int(round(occ["duration_sec"].median())),
                "yellow_sec": 3,
                "n_occurrences": int(len(occ)),
                "signal_state": state,
                "green_movements": ";".join(movements),
            })

    out_df = pd.DataFrame(rows)
    out = PROC / "signal_cycle_template.csv"
    out_df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[ok] {out.name}: {len(out_df)} phases")
    for grp, iid in GROUPS.items():
        sub = out_df[out_df["inter_id"] == iid]
        n_main = int(sub["n_main_phases"].iloc[0]) if len(sub) else 0
        cyc = int(sub["cycle_len_sec_est"].iloc[0]) if len(sub) else 0
        print(f"\n=== 교차로 {grp} (inter {iid}) : 주요 현시 {n_main}개, 추정 주기 ~{cyc}s "
              f"(전체 현시 {len(sub)}개) ===")
        print(sub[["phase_id", "is_main_phase", "green_sec", "n_occurrences", "green_movements"]].to_string(index=False))


if __name__ == "__main__":
    main()
