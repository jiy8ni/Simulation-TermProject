"""네트워크 데이터(SUMO net.xml)로 신호 칸 ↔ 방향·접근로 매핑 완성.

signal_state 문자열의 N번째 칸 = SUMO tlLogic의 linkIndex N 이다.
net.xml의 <connection ... tl=... linkIndex=N from=EDGE to=EDGE dir=s/l/r>가
"그 칸이 어느 진입 edge에서 어느 방향(직진/좌/우)으로 가는 신호인가"를 정의한다.

이 스크립트는:
  1) net.xml에서 대상 교차로(215173, 215174)의 linkIndex별 매핑을 추출
  2) edge의 from-node를 따라 '상류(진입) 교차로 ID = 접근로'를 역추적
  3) 1번 단계 결과(signal_green_windows.csv, signal_movement_state.csv)에 방향 라벨을 결합

출력 (data_processed/):
  - signal_movement_map.csv          : 칸 ↔ 방향·접근로 매핑표 (사전)
  - signal_green_windows_labeled.csv : 녹색 구간 + 방향 라벨
  - signal_movement_state_labeled.csv: 상세 상태 + 방향 라벨
"""

from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
NET = ROOT / "data" / "안산시_교차로_15_16_22년5월9일_월요일" / "네트워크데이터" / "anyang9_4.net.xml"
PROC = ROOT / "data_processed"

# 신호 문자열을 가진 대상 교차로 (= signal_plan의 inter_id)
TARGET_TLS = ["215173", "215174"]

# SUMO 방향 코드 -> 한글
DIR_KOR = {
    "s": "직진",
    "l": "좌회전",
    "r": "우회전",
    "t": "유턴",
    "L": "좌회전(부분)",
    "R": "우회전(부분)",
    "i": "미정",
}


def main() -> None:
    tree = ET.parse(NET)
    root = tree.getroot()

    # 1) edge -> (from_node, to_node) 사전 (일반 edge만)
    edge_from = {}
    edge_to = {}
    for e in root.iter("edge"):
        if e.get("function") == "internal":
            continue
        eid = e.get("id")
        if e.get("from"):
            edge_from[eid] = e.get("from")
        if e.get("to"):
            edge_to[eid] = e.get("to")

    # 2) 대상 교차로의 connection 추출
    rows = []
    for c in root.iter("connection"):
        tl = c.get("tl")
        if tl not in TARGET_TLS:
            continue
        li = int(c.get("linkIndex"))
        from_edge = c.get("from")
        to_edge = c.get("to")
        d = c.get("dir")
        rows.append(
            {
                "inter_id": int(tl),
                "linkIndex": li,
                "movement": li + 1,                      # signal_movement_state.csv의 movement와 일치
                "from_edge": from_edge,
                "to_edge": to_edge,
                "from_lane": int(c.get("fromLane")),
                "dir_code": d,
                "direction": DIR_KOR.get(d, d),
                "approach_node": edge_from.get(from_edge, ""),   # 상류 노드 = 진입 접근로 ID
                "exit_node": edge_to.get(to_edge, ""),           # 하류 노드 = 진출 방향
            }
        )

    mp = pd.DataFrame(rows).sort_values(["inter_id", "linkIndex"]).reset_index(drop=True)
    mp.to_csv(PROC / "signal_movement_map.csv", index=False, encoding="utf-8-sig")
    print(f"[ok] signal_movement_map.csv: {len(mp)} rows")

    # 길이 검증: linkIndex 개수 == signal_state 길이?
    for iid in TARGET_TLS:
        n = (mp["inter_id"] == int(iid)).sum()
        print(f"   inter_id {iid}: {n} links")

    # 매핑표 미리보기
    print("\n[매핑 미리보기] inter_id=215173")
    cols = ["movement", "dir_code", "direction", "approach_node", "from_edge", "to_edge"]
    print(mp[mp.inter_id == 215173][cols].to_string(index=False))

    # 3) 기존 신호 결과에 라벨 결합
    key = ["inter_id", "movement"]
    label_cols = key + ["dir_code", "direction", "approach_node", "exit_node", "from_edge", "to_edge"]

    for src_name, out_name in [
        ("signal_green_windows.csv", "signal_green_windows_labeled.csv"),
        ("signal_movement_state.csv", "signal_movement_state_labeled.csv"),
    ]:
        src = PROC / src_name
        if not src.exists():
            print(f"[skip] {src_name} 없음 (먼저 10_signal_to_arena.py 실행)")
            continue
        base = pd.read_csv(src)
        merged = base.merge(mp[label_cols], on=key, how="left")
        merged.to_csv(PROC / out_name, index=False, encoding="utf-8-sig")
        unmatched = merged["direction"].isna().sum()
        print(f"[ok] {out_name}: {len(merged)} rows (방향 미매칭 {unmatched}행)")


if __name__ == "__main__":
    main()
