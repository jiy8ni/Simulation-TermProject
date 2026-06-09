"""movement_ratio를 개별 교차로 폴더에서 재생성 (소스 분리).

배경:
  기존 movement_ratio.csv는 vehicle_core(통합 폴더 15+16 기반)에서 만들어져
  회전방향 unknown이 ~43.5%였다. 통합 폴더는 대기열 차량까지 담지만 회전 라벨이
  절반 가까이 비어 있기 때문이다.
  같은 교차로·같은 시간대라도 '개별 교차로 폴더'(교차로_15, 교차로_16)에는
  회전 라벨이 거의 완비되어 있다(빈값 2.5~7%).

소스 분리 원칙:
  - 차량 수/도착률/검증 지표 = 통합 폴더 기반(현행 유지, 대기열 포함 완전한 모집단)
  - 회전 '비율'(movement_ratio) = 개별 폴더 기반(깨끗한 라벨)
  movement_ratio는 접근로별 직진/좌/우 '비율'이라 count 모집단과 정확히 일치할
  필요가 없으므로, 깨끗한 개별 폴더로 비율만 정확히 산출한다.

집계 방식(부풀림 방지):
  차량(vhcl_id) × 진입로(from_inter_id) 단위로 1건만 남기되, 회전 라벨이 있으면
  라벨을 우선한다(빈값 기록 때문에 unknown이 중복 계상되는 문제 제거).

출력:
  - data_processed/movement_ratio.csv            (개별 폴더 기반, 신규 정식본)
  - data_processed/movement_ratio_combined_legacy.csv (기존 통합 기반 백업, 비교용)
"""

from pathlib import Path
import glob

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "안산시_교차로_15_16_22년5월9일_월요일" / "교통량(개별차량기반)"
PROC = ROOT / "data_processed"

WINDOW_START = pd.Timestamp("2022-05-09 08:00:00")
WINDOW_END = pd.Timestamp("2022-05-09 09:00:00")

# (분석 그룹, 개별 폴더, 그 교차로의 to_inter_id)
INTERSECTIONS = [("15", "교차로_15", "215173"), ("16", "교차로_16", "215174")]

USECOLS = ["vhcl_id", "unix_time", "to_inter_id", "from_inter_id", "turn_typ2to_inter"]


def load_individual(folder: str, to_inter: str) -> pd.DataFrame:
    """개별 폴더에서 08:00~09:00, 해당 교차로로 향하는 차량-진입로 단위 회전 라벨."""
    files = sorted(glob.glob(str(RAW / folder / "20220509" / "*2022050908*tra.csv")))
    parts = []
    for f in files:
        df = pd.read_csv(f, usecols=USECOLS, dtype=str, low_memory=False)
        parts.append(df)
    raw = pd.concat(parts, ignore_index=True)
    raw["unix_time"] = pd.to_numeric(raw["unix_time"], errors="coerce")
    raw["dt"] = pd.to_datetime(raw["unix_time"], unit="s") + pd.Timedelta(hours=9)  # KST
    raw = raw[(raw["dt"] >= WINDOW_START) & (raw["dt"] < WINDOW_END)]
    raw = raw[raw["to_inter_id"] == to_inter]
    raw = raw[raw["from_inter_id"].notna() & (raw["from_inter_id"] != "")]

    raw["turn"] = raw["turn_typ2to_inter"].fillna("").str.lower().replace("", "unknown")

    # 차량 × 진입로 단위로 1건: 라벨 있으면 라벨 우선(없으면 unknown)
    raw["has_label"] = (raw["turn"] != "unknown").astype(int)
    raw = raw.sort_values(["has_label", "unix_time"], ascending=[False, True])
    one = raw.drop_duplicates(["vhcl_id", "from_inter_id"], keep="first")
    return one[["vhcl_id", "from_inter_id", "turn"]]


def aggregate(vehicles: pd.DataFrame, group: str) -> pd.DataFrame:
    movement = (
        vehicles.groupby(["from_inter_id", "turn"]).size().rename("movement_count").reset_index()
    )
    movement["intersection_group"] = group
    movement["window_start"] = WINDOW_START
    movement["window_end"] = WINDOW_END
    movement["total_count"] = movement.groupby("from_inter_id")["movement_count"].transform("sum")
    movement["movement_ratio"] = movement["movement_count"] / movement["total_count"]
    return movement.rename(columns={"turn": "turn_typ2to_inter"})


def main() -> None:
    per_group_vehicles = {}
    for group, folder, to_inter in INTERSECTIONS:
        per_group_vehicles[group] = load_individual(folder, to_inter)

    frames = []
    for group in ("15", "16"):
        frames.append(aggregate(per_group_vehicles[group], group))
    # 15+16 = 두 교차로 차량 합집합 (연동 축 비교용)
    union = pd.concat([per_group_vehicles["15"], per_group_vehicles["16"]], ignore_index=True)
    frames.append(aggregate(union, "15+16"))

    out = pd.concat(frames, ignore_index=True)[
        [
            "intersection_group",
            "window_start",
            "window_end",
            "from_inter_id",
            "turn_typ2to_inter",
            "movement_count",
            "total_count",
            "movement_ratio",
        ]
    ].sort_values(["intersection_group", "from_inter_id", "turn_typ2to_inter"])

    # 기존(통합 기반) 백업
    canonical = PROC / "movement_ratio.csv"
    legacy = PROC / "movement_ratio_combined_legacy.csv"
    if canonical.exists() and not legacy.exists():
        pd.read_csv(canonical).to_csv(legacy, index=False, encoding="utf-8-sig")
        print(f"[backup] 기존 통합 기반 -> {legacy.name}")

    out.to_csv(canonical, index=False, encoding="utf-8-sig")
    print(f"[ok] {canonical.name}: {len(out)} rows (개별 폴더 기반)")

    # before/after unknown 비교
    print("\n=== unknown 비율 비교 ===")
    if legacy.exists():
        old = pd.read_csv(legacy)
        for g in ("15", "16", "15+16"):
            sub = old[old.intersection_group.astype(str) == g]
            u = sub[sub.turn_typ2to_inter == "unknown"]["movement_count"].sum()
            print(f"  [통합 legacy] {g:5s}: unknown {u/sub['movement_count'].sum()*100:.1f}%")
    for g in ("15", "16", "15+16"):
        sub = out[out.intersection_group == g]
        u = sub[sub.turn_typ2to_inter == "unknown"]["movement_count"].sum()
        print(f"  [개별 신규 ] {g:5s}: unknown {u/sub['movement_count'].sum()*100:.1f}%")


if __name__ == "__main__":
    main()
