"""출발지(from_inter_id) -> 물리 진입 leg(approach_node) 브리지 생성.

도착 데이터는 '직전 출발 교차로(from_inter_id)' 단위(교차로15: 11개, 16: 8개)이고,
신호 데이터는 '물리 진입 leg(approach_node)' 단위(교차로당 4개)다. 두 키는 서로 다른
번호 체계라 직접 join이 안 된다. 여기서는 net.xml의 junction 좌표로 방위각(bearing)을
계산해, 각 출발지를 교차로에서 본 방향이 가장 가까운 물리 leg에 배정한다.

출력 (data_processed/):
  1) leg_from_inter_map.csv      : from_inter_id -> leg(approach_node) 매핑 (방위/각오차 포함)
  2) leg_arrival_signal_bridge.csv: leg별 시간평균 도착률 + 회전비율 + 신호 녹색요약
  3) leg_arrival_5min.csv         : leg별 5분 단위 도착률 (Arena Arrival Schedule용, 비정상 포아송)

설계 메모:
  - 도착 '대수/도착률'은 통합소스(arrival_input_arena, 완전 모집단)에서 leg별 합산.
  - 회전 '비율'은 unknown이 적은 정식본(movement_ratio.csv, 개별폴더)에서 leg별 집계 후
    unknown 제거하고 l/s/r 재정규화.
  - 신호 녹색구간은 signal_green_windows_labeled(이미 approach_node 단위)에서 leg별 요약.
"""

from pathlib import Path
import math
import re

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data_processed"
NET = ROOT / "data" / "안산시_교차로_15_16_22년5월9일_월요일" / "네트워크데이터" / "anyang9_4.net.xml"

# 교차로(inter_id) -> 그룹 라벨 / 4개 물리 leg(approach_node)
TARGETS = {
    215173: {"group": "15", "legs": ["216151", "216286", "216287", "216288"]},
    215174: {"group": "16", "legs": ["215431", "215432", "215433", "215434"]},
}
WINDOW_SEC = 3600.0  # 08:00~09:00


def load_junction_coords() -> dict[str, tuple[float, float]]:
    txt = NET.read_text(encoding="utf-8")
    coord: dict[str, tuple[float, float]] = {}
    for m in re.finditer(r'<junction id="([^"]+)"[^>]*?\sx="([-0-9.]+)" y="([-0-9.]+)"', txt):
        coord[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    return coord


def bearing(center: tuple[float, float], point: tuple[float, float]) -> float:
    """center에서 point를 본 나침반 방위(0=N, 90=E, 시계방향)."""
    dx, dy = point[0] - center[0], point[1] - center[1]
    return math.degrees(math.atan2(dx, dy)) % 360


def ang_diff(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def compass(b: float) -> str:
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][round(b / 45) % 8]


def main() -> None:
    coord = load_junction_coords()
    arrival = pd.read_csv(PROC / "arrival_input_arena.csv")
    arrival["from_inter_id"] = arrival["from_inter_id"].astype(str)
    mr = pd.read_csv(PROC / "movement_ratio.csv", encoding="utf-8-sig")
    mr["from_inter_id"] = mr["from_inter_id"].astype(str)
    sig = pd.read_csv(PROC / "signal_green_windows_labeled.csv", encoding="utf-8-sig")
    sig["approach_node"] = sig["approach_node"].astype(str)

    map_rows = []
    bridge_rows = []
    bin_rows = []

    for tid, info in TARGETS.items():
        group, legs = info["group"], info["legs"]
        center = coord[str(tid)]
        leg_bear = {n: bearing(center, coord[n]) for n in legs}
        link_leg = min(legs, key=lambda n: ang_diff(leg_bear[n], bearing(center, coord["215174" if tid == 215173 else "215173"])))

        a_grp = arrival[arrival["intersection_group"] == group]
        mr_grp = mr[mr["intersection_group"] == group]
        origins = sorted(a_grp["from_inter_id"].unique())

        # --- 출발지 -> leg 배정 ---
        assign: dict[str, str] = {}
        for o in origins:
            if o not in coord:
                assign[o] = "UNMAPPED"
                continue
            b = bearing(center, coord[o])
            leg = min(legs, key=lambda n: ang_diff(b, leg_bear[n]))
            assign[o] = leg
            map_rows.append({
                "intersection_group": group, "inter_id": tid, "from_inter_id": o,
                "approach_node": leg, "leg_compass": compass(leg_bear[leg]),
                "bearing_to_origin": round(b, 1), "leg_bearing": round(leg_bear[leg], 1),
                "angle_err_deg": round(ang_diff(b, leg_bear[leg]), 1),
                "is_link_leg": leg == link_leg,
            })

        # --- leg별 집계 ---
        for leg in legs:
            o_in_leg = [o for o, lg in assign.items() if lg == leg]
            a_leg = a_grp[a_grp["from_inter_id"].isin(o_in_leg)]
            total_veh = int(a_leg["vehicle_count"].sum())

            # 회전비율: movement_ratio의 count를 leg로 합산 후 unknown 제거 재정규화
            mr_leg = mr_grp[mr_grp["from_inter_id"].isin(o_in_leg)]
            cnt = mr_leg.groupby("turn_typ2to_inter")["movement_count"].sum()
            lsr = {t: float(cnt.get(t, 0)) for t in ("l", "s", "r")}
            denom = sum(lsr.values())
            ratio = {t: (lsr[t] / denom if denom else 0.0) for t in ("l", "s", "r")}

            # 신호 녹색요약 (방향별)
            s_leg = sig[(sig["inter_id"] == tid) & (sig["approach_node"] == leg)
                        & (sig["intersection_group"] == group)]
            green = {}
            for dir_kr, key in [("직진", "s"), ("좌회전", "l"), ("우회전", "r")]:
                w = s_leg[s_leg["direction"] == dir_kr]
                green[f"green_{key}_n"] = int(len(w))
                green[f"green_{key}_total_sec"] = round(float(w["green_dur_sec"].sum()), 1)
                green[f"green_{key}_first_start_sec"] = round(float(w["green_start_sec"].min()), 1) if len(w) else None

            bridge_rows.append({
                "intersection_group": group, "inter_id": tid, "approach_node": leg,
                "leg_compass": compass(leg_bear[leg]), "leg_bearing": round(leg_bear[leg], 1),
                "is_link_leg": leg == link_leg,
                "from_inter_ids": "|".join(o_in_leg),
                "n_origins": len(o_in_leg),
                "total_veh_hour": total_veh,
                "arrival_per_min": round(total_veh / (WINDOW_SEC / 60), 3),
                "mean_interarrival_sec": round(WINDOW_SEC / total_veh, 2) if total_veh else None,
                "ratio_left": round(ratio["l"], 4),
                "ratio_straight": round(ratio["s"], 4),
                "ratio_right": round(ratio["r"], 4),
                **green,
            })

            # --- 5분 단위 leg 도착률 (비정상 포아송 / Arena Schedule) ---
            per_bin = (
                a_leg.groupby(["time_bin", "period_start_sec", "period_end_sec"])["vehicle_count"]
                .sum()
                .reset_index()
                .sort_values("period_start_sec")
            )
            for b in per_bin.itertuples(index=False):
                bin_sec = float(b.period_end_sec) - float(b.period_start_sec)
                veh = int(b.vehicle_count)
                bin_rows.append({
                    "intersection_group": group, "inter_id": tid, "approach_node": leg,
                    "leg_compass": compass(leg_bear[leg]), "is_link_leg": leg == link_leg,
                    "time_bin": b.time_bin,
                    "period_start_sec": float(b.period_start_sec),
                    "period_end_sec": float(b.period_end_sec),
                    "veh": veh,
                    "arrival_per_min": round(veh / (bin_sec / 60), 3) if bin_sec else None,
                    "mean_interarrival_sec": round(bin_sec / veh, 2) if veh else None,
                })

    map_df = pd.DataFrame(map_rows).sort_values(["inter_id", "approach_node", "total_veh_hour" if False else "from_inter_id"])
    bridge_df = pd.DataFrame(bridge_rows)
    bin_df = pd.DataFrame(bin_rows).sort_values(
        ["inter_id", "approach_node", "period_start_sec"]
    )
    map_df.to_csv(PROC / "leg_from_inter_map.csv", index=False, encoding="utf-8-sig")
    bridge_df.to_csv(PROC / "leg_arrival_signal_bridge.csv", index=False, encoding="utf-8-sig")
    bin_df.to_csv(PROC / "leg_arrival_5min.csv", index=False, encoding="utf-8-sig")
    print(f"[ok] leg_from_inter_map.csv: {len(map_df)} rows")
    print(f"[ok] leg_arrival_signal_bridge.csv: {len(bridge_df)} rows")
    print(f"[ok] leg_arrival_5min.csv: {len(bin_df)} rows")
    print("\n=== leg 브리지 요약 ===")
    show = ["intersection_group", "approach_node", "leg_compass", "is_link_leg", "n_origins",
            "total_veh_hour", "arrival_per_min", "ratio_left", "ratio_straight", "ratio_right",
            "green_s_n", "green_l_n", "green_r_n"]
    print(bridge_df[show].to_string(index=False))


if __name__ == "__main__":
    main()
