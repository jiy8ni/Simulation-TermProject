"""net.xml 좌표 -> Arena 애니메이션 Station 배치 + Route 주행시간.

두 교차로(215173, 215174)와 그 진입/진출 노드를 실제 배치 비율대로 화면에 그리기 위해
net.xml junction 좌표를 화면 좌표(0~100, 종횡비 보존)로 변환하고, 진입로/진출로 edge의
길이÷속도로 Route 주행시간을 계산한다.

출력 (data_processed/):
  1) layout_coords.csv : Station 위치 (node_id, role, inter_id, net_x/y, screen_x/y)
  2) layout_routes.csv : movement별 진입/진출 Route 주행시간 (edge 길이·속도 포함)
"""

from pathlib import Path
import re

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data_processed"
NET = ROOT / "data" / "안산시_교차로_15_16_22년5월9일_월요일" / "네트워크데이터" / "anyang9_4.net.xml"

CENTERS = {215173: "15", 215174: "16"}
CANVAS = 100.0  # 화면 정규화 범위


def parse_net(txt: str):
    coord = {}
    for m in re.finditer(r'<junction id="([^"]+)"[^>]*?\sx="([-0-9.]+)" y="([-0-9.]+)"', txt):
        coord[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    # edge 길이/속도: lane id = "<edge>_<laneIdx>" 의 첫 lane에서 취득
    edge_len, edge_spd = {}, {}
    for m in re.finditer(r'<lane id="([^"]+)"[^>]*?\sspeed="([-0-9.]+)"[^>]*?\slength="([-0-9.]+)"', txt):
        edge = m.group(1).rsplit("_", 1)[0]
        if edge not in edge_len:
            edge_spd[edge] = float(m.group(2))
            edge_len[edge] = float(m.group(3))
    return coord, edge_len, edge_spd


def main() -> None:
    txt = NET.read_text(encoding="utf-8")
    coord, edge_len, edge_spd = parse_net(txt)
    mm = pd.read_csv(PROC / "signal_movement_map.csv", encoding="utf-8-sig")

    # --- Station 노드 모으기: 교차로 중심 + leg 노드 ---
    # 각 leg 노드는 진입(ENTER/STOPLINE)이자 진출(EXIT)로 모두 쓰이므로 role="leg".
    nodes = {}
    for cid in CENTERS:
        nodes[str(cid)] = ("center", cid)
    for r in mm.itertuples(index=False):
        for nid in (r.approach_node, r.exit_node):
            nid = str(nid)
            if nid not in nodes:
                nodes[nid] = ("leg", r.inter_id)

    pts = {nid: coord[nid] for nid in nodes if nid in coord}
    xs = [p[0] for p in pts.values()]; ys = [p[1] for p in pts.values()]
    minx, miny = min(xs), min(ys)
    scale = max(max(xs) - minx, max(ys) - miny) or 1.0  # 종횡비 보존

    coord_rows = []
    for nid, (role, iid) in nodes.items():
        if nid not in coord:
            continue
        x, y = coord[nid]
        coord_rows.append({
            "node_id": nid, "role": role, "inter_id": iid,
            "net_x": round(x, 2), "net_y": round(y, 2),
            "screen_x": round((x - minx) / scale * CANVAS, 2),
            "screen_y": round((y - miny) / scale * CANVAS, 2),
        })
    coord_df = pd.DataFrame(coord_rows).sort_values(["inter_id", "role", "node_id"])
    coord_df.to_csv(PROC / "layout_coords.csv", index=False, encoding="utf-8-sig")

    # --- Route 주행시간: 진입 from_edge, 진출 to_edge ---
    def t(edge):
        L, v = edge_len.get(edge), edge_spd.get(edge)
        return (round(L, 2), round(v, 2), round(L / v, 2)) if (L and v) else (None, None, None)

    route_rows = []
    seen = set()
    for r in mm.itertuples(index=False):
        key = f"{r.inter_id}_{r.approach_node}_{r.dir_code}"
        if key in seen:
            continue
        seen.add(key)
        aL, aV, aT = t(r.from_edge)
        eL, eV, eT = t(r.to_edge)
        route_rows.append({
            "movement_key": key, "inter_id": r.inter_id, "approach_node": r.approach_node,
            "dir_code": r.dir_code, "direction": r.direction,
            "from_edge": r.from_edge, "approach_len_m": aL, "approach_speed_ms": aV, "approach_time_sec": aT,
            "to_edge": r.to_edge, "exit_len_m": eL, "exit_speed_ms": eV, "exit_time_sec": eT,
        })
    route_df = pd.DataFrame(route_rows).sort_values(["inter_id", "approach_node", "dir_code"])
    route_df.to_csv(PROC / "layout_routes.csv", index=False, encoding="utf-8-sig")

    print(f"[ok] layout_coords.csv: {len(coord_df)} stations")
    print(coord_df.to_string(index=False))
    print(f"\n[ok] layout_routes.csv: {len(route_df)} movements (approach/exit Route 주행시간)")
    print(route_df[["movement_key", "approach_len_m", "approach_time_sec", "exit_len_m", "exit_time_sec"]].to_string(index=False))


if __name__ == "__main__":
    main()
