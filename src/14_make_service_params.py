"""이동류(movement = 진입 leg × 회전)별 Arena Process 서비스 파라미터 생성.

데이터에는 포화교통류율/서비스시간이 없으므로, HCM 표준 포화류율을 가정한다.
  - 차로당 포화류율 s0 = 1900 veh/h  ->  차로당 방출 헤드웨이 = 3600/1900 ≈ 1.895 s
  - 이동류 용량(capacity) = 차로수 × s0
Arena에서는 Process를 Seize(차로자원, cap=차로수) → Delay(헤드웨이) → Release 로 구성하면
이동류 방출률이 차로수/헤드웨이 = 차로수×s0/3600 veh/s 로 재현된다.

차로수는 signal_movement_map.csv(net.xml 기반)의 (inter_id, approach_node, direction)별
distinct from_lane 개수로 센다. (직진 4, 좌 1, 우 1 — 우회전은 직진 lane 0과 공유)

출력: data_processed/leg_service_params.csv
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data_processed"
SAT_FLOW_PER_LANE = 1900.0  # veh/h/lane (HCM 표준 가정)
SAT_HEADWAY_SEC = 3600.0 / SAT_FLOW_PER_LANE  # 차로당 방출 헤드웨이 ≈ 1.895 s


def main() -> None:
    m = pd.read_csv(PROC / "signal_movement_map.csv", encoding="utf-8-sig")

    g = (
        m.groupby(["inter_id", "approach_node", "dir_code", "direction"])["from_lane"]
        .nunique()
        .reset_index()
        .rename(columns={"from_lane": "lane_count"})
    )
    g["sat_headway_sec"] = round(SAT_HEADWAY_SEC, 4)
    g["resource_capacity"] = g["lane_count"]                    # Process 자원 capacity
    g["capacity_veh_per_sec"] = (g["lane_count"] * SAT_FLOW_PER_LANE / 3600.0).round(4)
    g["sat_flow_veh_per_hr"] = (g["lane_count"] * SAT_FLOW_PER_LANE).astype(int)
    g["service_delay_sec"] = round(SAT_HEADWAY_SEC, 4)          # Arena Delay 값(차량당)

    g = g.sort_values(["inter_id", "approach_node", "dir_code"]).reset_index(drop=True)
    out = PROC / "leg_service_params.csv"
    g.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[ok] {out.name}: {len(g)} rows")
    print(g.to_string(index=False))


if __name__ == "__main__":
    main()
