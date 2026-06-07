from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Iterable
import xml.etree.ElementTree as ET

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import MultipleLocator, PercentFormatter
from scipy import stats


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data"
PROCESSED_ROOT = PROJECT_ROOT / "data_processed"
FIGURES_ROOT = PROJECT_ROOT / "figures"
REPORTS_ROOT = PROJECT_ROOT / "reports"

ANALYSIS_DATE = pd.Timestamp("2022-05-09")
ANALYSIS_DATE_END = ANALYSIS_DATE + pd.Timedelta(days=1)
ANALYSIS_DATE_LABEL = ANALYSIS_DATE.strftime("%Y%m%d")
LOCAL_TIMEZONE = "Asia/Seoul"
CHUNK_SIZE = 200_000

TARGET_INTERSECTIONS = {"15": 215173, "16": 215174}
TARGET_INTERSECTION_IDS = set(TARGET_INTERSECTIONS.values())
INTERSECTION_LABELS = {value: key for key, value in TARGET_INTERSECTIONS.items()}
INTERSECTION_GROUPS = ["15", "16", "15+16"]
WINDOW_SIZES = (12, 24)
ENFORCE_SHARED_WINDOW = True
SHARED_WINDOW_ANCHOR_GROUP = "15+16"

VEHICLE_TYPE_NAMES = {
    1: "passenger_car",
    2: "bus",
    3: "truck",
    4: "special_purpose",
    5: "special_vehicle",
    6: "motorcycle",
}

VEHICLE_CORE_COLUMNS = [
    "vhcl_id",
    "unix_time",
    "to_inter_id",
    "from_inter_id",
    "turn_typ2to_inter",
    "vhcl_typ",
    "spd",
    "tl",
    "que_all",
    "que_200_500",
    "que_500",
]

VEHICLE_CORE_OUTPUT_COLUMNS = [
    "source_file",
    "source_area",
    "vhcl_id",
    "unix_time",
    "datetime",
    "to_inter_id",
    "from_inter_id",
    "turn_typ2to_inter",
    "vhcl_typ",
    "spd",
    "tl",
    "que_all",
    "que_200_500",
    "que_500",
]

ARRIVAL_EVENT_OUTPUT_COLUMNS = [
    "intersection_group",
    "analysis_date",
    "vhcl_id",
    "to_inter_id",
    "from_inter_id",
    "turn_typ2to_inter",
    "vhcl_typ",
    "arrival_unix_time",
    "arrival_datetime",
    "spd",
    "tl",
    "que_all",
    "que_200_500",
    "que_500",
    "source_file",
    "source_area",
]


def raw_data_root() -> Path:
    candidates = sorted(path for path in DATA_ROOT.iterdir() if path.is_dir())
    if not candidates:
        raise FileNotFoundError(f"No raw data folders found in {DATA_ROOT}")

    preferred = [path for path in candidates if "안산시" in path.name]
    return preferred[0] if preferred else candidates[0]


RAW_DATA_ROOT = raw_data_root()


def ensure_output_dirs() -> None:
    for path in (PROCESSED_ROOT, FIGURES_ROOT, REPORTS_ROOT):
        path.mkdir(parents=True, exist_ok=True)


def relative_path(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def list_raw_files() -> list[Path]:
    files = [
        path
        for path in RAW_DATA_ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in {".csv", ".xml"}
    ]
    return sorted(files)


def classify_file(path: Path) -> str:
    rel = relative_path(path)
    if "교통량(개별차량기반)" in rel and path.name.endswith("tra.csv"):
        return "individual_vehicle_csv"
    if "교통량(기종점량기반)" in rel and path.name.endswith("od.csv"):
        return "origin_destination_csv"
    if "교통량(회전교통량기반)" in rel and path.suffix.lower() == ".xml":
        return "turn_movement_xml"
    if "신호데이터" in rel and path.suffix.lower() == ".csv":
        return "signal_csv"
    if "신호데이터" in rel and path.suffix.lower() == ".xml":
        return "signal_xml"
    if "지표데이터" in rel and path.suffix.lower() == ".csv":
        return "indicator_csv"
    if "영상데이터" in rel:
        return "video_or_image"
    return "other"


def area_label(path: Path) -> str:
    joined = "/".join(path.parts)
    if "교차로_15_16" in joined:
        return "15+16"
    if "교차로_15" in joined:
        return "15"
    if "교차로_16" in joined:
        return "16"
    return "unknown"


def csv_preview(path: Path, nrows: int = 3) -> pd.DataFrame:
    return pd.read_csv(path, nrows=nrows, low_memory=False, encoding="utf-8-sig")


def csv_columns(path: Path) -> list[str]:
    return pd.read_csv(path, nrows=0, low_memory=False, encoding="utf-8-sig").columns.tolist()


def iter_csv_chunks(
    path: Path,
    usecols: Iterable[str] | None = None,
    chunksize: int = CHUNK_SIZE,
) -> Iterable[pd.DataFrame]:
    yield from pd.read_csv(
        path,
        usecols=list(usecols) if usecols is not None else None,
        chunksize=chunksize,
        low_memory=False,
        encoding="utf-8-sig",
    )


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def text(series: pd.Series, default: str = "") -> pd.Series:
    result = series.astype("string")
    result = result.fillna(default)
    result = result.replace({"<NA>": default, "nan": default, "None": default})
    return result.str.strip()


def unix_to_local_datetime(series: pd.Series) -> pd.Series:
    clean = numeric(series)
    non_null = clean.dropna()
    if non_null.empty:
        return pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")

    median = non_null.abs().median()
    unit = "ms" if median >= 1e11 else "s"
    dt = pd.to_datetime(clean, unit=unit, utc=True, errors="coerce")
    return dt.dt.tz_convert(LOCAL_TIMEZONE).dt.tz_localize(None)


def intersection_group_from_id(series: pd.Series) -> pd.Series:
    return series.map(INTERSECTION_LABELS)


def queue_flag(series: pd.Series) -> pd.Series:
    return numeric(series).eq(1).astype(float)


def long_queue_flag(df: pd.DataFrame) -> pd.Series:
    return (
        numeric(df["que_200_500"]).eq(1) | numeric(df["que_500"]).eq(1)
    ).astype(float)


def herfindahl(counts: pd.Series) -> float:
    total = float(counts.sum())
    if total <= 0:
        return float("nan")
    shares = counts / total
    return float((shares**2).sum())


def append_csv(df: pd.DataFrame, path: Path) -> None:
    mode = "a" if path.exists() else "w"
    df.to_csv(path, mode=mode, header=not path.exists(), index=False)


def full_five_min_grid() -> pd.DataFrame:
    bins = pd.date_range(
        ANALYSIS_DATE,
        ANALYSIS_DATE_END - pd.Timedelta(minutes=5),
        freq="5min",
    )
    grid = pd.MultiIndex.from_product(
        [INTERSECTION_GROUPS, bins],
        names=["intersection_group", "time_bin"],
    )
    return grid.to_frame(index=False)


def bool_from_any(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def dataframe_to_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows_"

    headers = [str(col) for col in df.columns]
    rows = [[str(value) for value in row] for row in df.to_numpy()]
    widths = [
        max(len(headers[idx]), max(len(row[idx]) for row in rows))
        for idx in range(len(headers))
    ]

    def render(row: list[str]) -> str:
        return "| " + " | ".join(value.ljust(widths[idx]) for idx, value in enumerate(row)) + " |"

    separator = "| " + " | ".join("-" * width for width in widths) + " |"
    output = [render(headers), separator]
    output.extend(render(row) for row in rows)
    return "\n".join(output)


def translate_intersection_group(value: object) -> str:
    mapping = {"15": "교차로 15", "16": "교차로 16", "15+16": "교차로 15+16"}
    return mapping.get(str(value), str(value))


def translate_data_family(value: object) -> str:
    mapping = {
        "indicator_csv": "지표 CSV",
        "individual_vehicle_csv": "개별차량 CSV",
        "origin_destination_csv": "기종점량 CSV",
        "signal_csv": "신호 CSV",
        "signal_xml": "신호 XML",
        "turn_movement_xml": "회전교통량 XML",
    }
    return mapping.get(str(value), str(value))


def translate_turn(value: object) -> str:
    mapping = {"l": "좌회전", "r": "우회전", "s": "직진", "u": "유턴", "unknown": "미상", "": "미상"}
    return mapping.get(str(value), str(value))


def translate_vehicle_type_name(value: object) -> str:
    mapping = {
        "passenger_car": "승용차",
        "bus": "버스",
        "truck": "트럭",
        "special_purpose": "특수목적차",
        "special_vehicle": "특수차량",
        "motorcycle": "이륜차",
        "unknown": "미상",
    }
    return mapping.get(str(value), str(value))


def percent_text(series: pd.Series, digits: int = 1) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce") * 100.0
    return values.map(lambda value: f"{value:.{digits}f}%" if pd.notna(value) else "")


def round_numeric_columns(df: pd.DataFrame, digits: dict[str, int]) -> pd.DataFrame:
    output = df.copy()
    for column, precision in digits.items():
        if column in output.columns:
            output[column] = pd.to_numeric(output[column], errors="coerce").round(precision)
    return output


def selected_windows() -> pd.DataFrame:
    path = PROCESSED_ROOT / "candidate_window.csv"
    df = pd.read_csv(path, parse_dates=["window_start", "window_end"])
    if "is_selected" in df.columns:
        df = df[df["is_selected"].map(bool_from_any)]
    df = df.sort_values(["intersection_group", "rank", "window_start"])
    return df.drop_duplicates("intersection_group", keep="first")


def load_arrival_events() -> pd.DataFrame:
    return pd.read_csv(
        PROCESSED_ROOT / "arrival_events.csv",
        parse_dates=["arrival_datetime"],
        low_memory=False,
    )


def events_in_selected_windows(events: pd.DataFrame | None = None) -> pd.DataFrame:
    if events is None:
        events = load_arrival_events()

    windows = selected_windows()[
        ["intersection_group", "window_start", "window_end", "window_minutes"]
    ]
    merged = events.merge(windows, on="intersection_group", how="inner")
    mask = (merged["arrival_datetime"] >= merged["window_start"]) & (
        merged["arrival_datetime"] < merged["window_end"]
    )
    return merged.loc[mask].copy()


def log_stage(name: str, **metrics: object) -> None:
    print(f"[{name}]")
    for key, value in metrics.items():
        print(f"  - {key}: {value}")


def safe_json_records(df: pd.DataFrame, limit: int = 2) -> str:
    if df.empty:
        return "[]"
    return json.dumps(
        df.head(limit).replace({np.nan: None}).to_dict(orient="records"),
        ensure_ascii=False,
    )


def matching_columns(columns: list[str], needles: Iterable[str]) -> list[str]:
    lowered = {column: column.lower() for column in columns}
    matched = []
    for column, lower in lowered.items():
        if any(needle in lower for needle in needles):
            matched.append(column)
    return matched


def vehicle_files() -> list[Path]:
    return [path for path in list_raw_files() if classify_file(path) == "individual_vehicle_csv"]


def od_files() -> list[Path]:
    return [path for path in list_raw_files() if classify_file(path) == "origin_destination_csv"]


def signal_csv_files() -> list[Path]:
    return [path for path in list_raw_files() if classify_file(path) == "signal_csv"]


def inventory_outputs() -> tuple[Path, Path]:
    return PROCESSED_ROOT / "data_inventory.csv", PROCESSED_ROOT / "column_profile.csv"


def vehicle_core_canonical_path() -> Path:
    return PROCESSED_ROOT / f"vehicle_core_{ANALYSIS_DATE_LABEL}.csv"


def next_vehicle_core_output_path() -> Path:
    canonical = vehicle_core_canonical_path()
    if not canonical.exists():
        return canonical

    try:
        canonical.unlink()
        return canonical
    except PermissionError:
        pass

    counter = 1
    while True:
        candidate = PROCESSED_ROOT / f"vehicle_core_{ANALYSIS_DATE_LABEL}_rerun{counter}.csv"
        if not candidate.exists():
            return candidate
        counter += 1


def latest_vehicle_core_path() -> Path:
    candidates = sorted(
        PROCESSED_ROOT.glob(f"vehicle_core_{ANALYSIS_DATE_LABEL}*.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("No vehicle_core output found. Run src/02_make_vehicle_core.py first.")
    return candidates[0]


def run_inventory() -> None:
    ensure_output_dirs()
    inventory_path, column_profile_path = inventory_outputs()
    if inventory_path.exists():
        inventory_path.unlink()
    if column_profile_path.exists():
        column_profile_path.unlink()

    inventory_rows: list[dict[str, object]] = []
    column_rows: list[dict[str, object]] = []
    files = list_raw_files()

    for index, path in enumerate(files, start=1):
        family = classify_file(path)
        columns: list[str] = []
        row_preview = ""
        time_cols = []
        inter_cols = []
        vehicle_cols = []

        if path.suffix.lower() == ".csv":
            preview = csv_preview(path)
            columns = preview.columns.tolist()
            row_preview = safe_json_records(preview)
            time_cols = matching_columns(columns, ["time", "date", "ymd", "hm", "ss"])
            inter_cols = matching_columns(columns, ["inter", "phase", "signal"])
            vehicle_cols = matching_columns(columns, ["vhcl", "vehicle"])

            for column in columns:
                sample_value = None
                if column in preview.columns and not preview.empty:
                    non_null = preview[column].dropna()
                    sample_value = non_null.iloc[0] if not non_null.empty else None
                column_rows.append(
                    {
                        "file_path": relative_path(path),
                        "data_family": family,
                        "source_area": area_label(path),
                        "column_name": column,
                        "sample_value": sample_value,
                        "is_time_candidate": column in time_cols,
                        "is_intersection_candidate": column in inter_cols,
                        "is_vehicle_id_candidate": column in vehicle_cols,
                    }
                )
        else:
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                lines = []
                for _ in range(5):
                    line = handle.readline()
                    if not line:
                        break
                    if line.strip():
                        lines.append(line.strip())
                row_preview = "\n".join(lines)

        inventory_rows.append(
            {
                "file_path": relative_path(path),
                "data_family": family,
                "source_area": area_label(path),
                "file_size_bytes": path.stat().st_size,
                "extension": path.suffix.lower(),
                "column_count": len(columns),
                "columns": "|".join(columns),
                "time_columns": "|".join(time_cols),
                "intersection_columns": "|".join(inter_cols),
                "vehicle_id_columns": "|".join(vehicle_cols),
                "row_preview": row_preview,
            }
        )

        if index % 250 == 0 or index == len(files):
            print(f"[inventory] scanned {index}/{len(files)} files")

    pd.DataFrame(inventory_rows).to_csv(inventory_path, index=False)
    pd.DataFrame(column_rows).to_csv(column_profile_path, index=False)
    family_counts = pd.DataFrame(inventory_rows)["data_family"].value_counts().to_dict()
    log_stage(
        "inventory",
        scanned_files=len(inventory_rows),
        column_profile_rows=len(column_rows),
        data_inventory=relative_path(inventory_path),
        column_profile=relative_path(column_profile_path),
        family_counts=family_counts,
    )


def run_make_vehicle_core() -> None:
    ensure_output_dirs()
    output_path = next_vehicle_core_output_path()
    if output_path.exists():
        output_path.unlink()

    scanned_rows = 0
    kept_rows = 0
    missing_key_rows = 0
    per_intersection = defaultdict(int)
    min_datetime = None
    max_datetime = None

    for file_index, path in enumerate(vehicle_files(), start=1):
        source_area = area_label(path)
        available_columns = csv_columns(path)
        usecols = [column for column in VEHICLE_CORE_COLUMNS if column in available_columns]

        required = {"vhcl_id", "unix_time", "to_inter_id"}
        if not required.issubset(set(usecols)):
            print(f"[vehicle_core] skipped missing required columns: {relative_path(path)}")
            continue

        for chunk in iter_csv_chunks(path, usecols=usecols):
            scanned_rows += len(chunk)

            chunk["vhcl_id"] = text(chunk["vhcl_id"])
            chunk["to_inter_id"] = numeric(chunk["to_inter_id"]).astype("Int64")
            chunk["unix_time"] = numeric(chunk["unix_time"])
            chunk["datetime"] = unix_to_local_datetime(chunk["unix_time"])

            filtered = chunk[
                chunk["vhcl_id"].ne("")
                & chunk["to_inter_id"].isin(TARGET_INTERSECTION_IDS)
                & chunk["unix_time"].notna()
                & chunk["datetime"].notna()
            ].copy()

            filtered = filtered[
                (filtered["datetime"] >= ANALYSIS_DATE)
                & (filtered["datetime"] < ANALYSIS_DATE_END)
            ]

            missing_key_rows += len(chunk) - len(filtered)
            if filtered.empty:
                continue

            filtered["source_file"] = relative_path(path)
            filtered["source_area"] = source_area
            filtered["from_inter_id"] = text(filtered.get("from_inter_id", pd.Series("", index=filtered.index)))
            filtered["turn_typ2to_inter"] = text(
                filtered.get("turn_typ2to_inter", pd.Series("", index=filtered.index))
            ).str.lower()

            for column in ["vhcl_typ", "spd", "tl", "que_all", "que_200_500", "que_500"]:
                if column in filtered.columns:
                    filtered[column] = numeric(filtered[column])
                else:
                    filtered[column] = np.nan

            filtered = filtered[VEHICLE_CORE_OUTPUT_COLUMNS].sort_values("datetime")
            append_csv(filtered, output_path)
            kept_rows += len(filtered)
            chunk_min = filtered["datetime"].min()
            chunk_max = filtered["datetime"].max()
            min_datetime = chunk_min if min_datetime is None else min(min_datetime, chunk_min)
            max_datetime = chunk_max if max_datetime is None else max(max_datetime, chunk_max)

            counts = filtered["to_inter_id"].value_counts(dropna=True).to_dict()
            for inter_id, count in counts.items():
                per_intersection[int(inter_id)] += int(count)

        if file_index % 25 == 0 or file_index == len(vehicle_files()):
            print(f"[vehicle_core] processed {file_index}/{len(vehicle_files())} files")

    log_stage(
        "vehicle_core",
        source_files=len(vehicle_files()),
        scanned_rows=scanned_rows,
        kept_rows=kept_rows,
        dropped_rows=missing_key_rows,
        time_range=f"{min_datetime} -> {max_datetime}",
        per_intersection={INTERSECTION_LABELS.get(key, key): value for key, value in per_intersection.items()},
        output=relative_path(output_path),
    )


def run_make_arrival_events() -> None:
    ensure_output_dirs()
    source_path = latest_vehicle_core_path()
    output_path = PROCESSED_ROOT / "arrival_events.csv"
    if output_path.exists():
        output_path.unlink()

    best_rows: dict[tuple[str, int, str, str], dict[str, object]] = {}
    source_rows = 0

    for chunk in pd.read_csv(source_path, parse_dates=["datetime"], chunksize=CHUNK_SIZE, low_memory=False):
        source_rows += len(chunk)
        chunk["from_inter_id"] = text(chunk["from_inter_id"])
        chunk["turn_typ2to_inter"] = text(chunk["turn_typ2to_inter"]).str.lower()
        chunk = chunk.sort_values("unix_time")
        chunk = chunk.drop_duplicates(
            subset=["vhcl_id", "to_inter_id", "from_inter_id", "turn_typ2to_inter"],
            keep="first",
        )

        for row in chunk.itertuples(index=False):
            key = (
                str(row.vhcl_id),
                int(row.to_inter_id),
                str(row.from_inter_id),
                str(row.turn_typ2to_inter),
            )
            current_best = best_rows.get(key)
            if current_best is None or float(row.unix_time) < float(current_best["arrival_unix_time"]):
                best_rows[key] = {
                    "analysis_date": ANALYSIS_DATE.date().isoformat(),
                    "vhcl_id": row.vhcl_id,
                    "to_inter_id": int(row.to_inter_id),
                    "from_inter_id": row.from_inter_id,
                    "turn_typ2to_inter": row.turn_typ2to_inter,
                    "vhcl_typ": row.vhcl_typ,
                    "arrival_unix_time": row.unix_time,
                    "arrival_datetime": row.datetime,
                    "spd": row.spd,
                    "tl": row.tl,
                    "que_all": row.que_all,
                    "que_200_500": row.que_200_500,
                    "que_500": row.que_500,
                    "source_file": row.source_file,
                    "source_area": row.source_area,
                }

    base_events = pd.DataFrame(best_rows.values()).sort_values("arrival_datetime")
    base_events["intersection_group"] = base_events["to_inter_id"].map(INTERSECTION_LABELS)
    combined_events = base_events.copy()
    combined_events["intersection_group"] = "15+16"

    output = pd.concat([base_events, combined_events], ignore_index=True)
    output = output[ARRIVAL_EVENT_OUTPUT_COLUMNS]
    output.to_csv(output_path, index=False)

    base_counts = base_events["intersection_group"].value_counts().to_dict()
    log_stage(
        "arrival_events",
        source_file=relative_path(source_path),
        source_rows=source_rows,
        unique_base_events=len(base_events),
        duplicated_with_combined_group=len(output),
        removed_duplicates=source_rows - len(base_events),
        time_range=f"{output['arrival_datetime'].min()} -> {output['arrival_datetime'].max()}",
        per_group=base_counts | {"15+16": int((output['intersection_group'] == '15+16').sum())},
        output=relative_path(output_path),
    )


def normalized_scores(df: pd.DataFrame) -> pd.DataFrame:
    specs = {
        "vehicle_count": ("positive", 0.25),
        "avg_speed": ("inverse", 0.20),
        "queue_ratio": ("positive", 0.20),
        "avg_delay": ("positive", 0.20),
        "direction_imbalance": ("positive", 0.10),
        "signal_imbalance": ("positive", 0.05),
    }

    score_columns = []
    for column, (direction, _) in specs.items():
        score_column = f"{column}_score"
        values = pd.to_numeric(df[column], errors="coerce")
        valid = values.dropna()

        if valid.empty or math.isclose(float(valid.max()), float(valid.min()), rel_tol=0.0, abs_tol=1e-12):
            df[score_column] = np.nan
        elif direction == "positive":
            df[score_column] = (values - valid.min()) / (valid.max() - valid.min())
        else:
            df[score_column] = (valid.max() - values) / (valid.max() - valid.min())
        score_columns.append(score_column)

    weighted_sum = pd.Series(0.0, index=df.index)
    weight_total = pd.Series(0.0, index=df.index)
    for column, (_, weight) in specs.items():
        score_column = f"{column}_score"
        mask = df[score_column].notna()
        weighted_sum.loc[mask] += df.loc[mask, score_column] * weight
        weight_total.loc[mask] += weight

    df["bottleneck_score"] = np.where(weight_total > 0, weighted_sum / weight_total, 0.0)
    return df


def run_screening_5min() -> None:
    ensure_output_dirs()
    source = load_arrival_events()
    source["from_inter_id"] = text(source["from_inter_id"]).replace("", "unknown")
    source["turn_typ2to_inter"] = text(source["turn_typ2to_inter"]).replace("", "unknown")
    source["time_bin"] = source["arrival_datetime"].dt.floor("5min")
    source["queue_flag"] = queue_flag(source["que_all"])
    source["long_queue_flag"] = long_queue_flag(source)

    base = (
        source.groupby(["intersection_group", "time_bin"], dropna=False)
        .agg(
            vehicle_count=("vhcl_id", "count"),
            avg_speed=("spd", "mean"),
            avg_delay=("tl", "mean"),
            queue_ratio=("queue_flag", "mean"),
            long_queue_ratio=("long_queue_flag", "mean"),
        )
        .reset_index()
    )

    direction_counts = (
        source.groupby(["intersection_group", "time_bin", "from_inter_id"], dropna=False)
        .size()
        .rename("count")
        .reset_index()
    )
    direction_imbalance = (
        direction_counts.groupby(["intersection_group", "time_bin"])["count"]
        .apply(herfindahl)
        .rename("direction_imbalance")
        .reset_index()
    )

    screening = full_five_min_grid().merge(base, on=["intersection_group", "time_bin"], how="left")
    screening = screening.merge(direction_imbalance, on=["intersection_group", "time_bin"], how="left")
    screening["vehicle_count"] = screening["vehicle_count"].fillna(0).astype(int)
    screening["arrival_rate_per_min"] = screening["vehicle_count"] / 5.0
    screening["mean_interarrival_sec"] = np.where(
        screening["vehicle_count"] > 0,
        300.0 / screening["vehicle_count"],
        np.nan,
    )
    screening["signal_imbalance"] = 0.0
    screening = normalized_scores(screening)
    screening = screening[
        [
            "intersection_group",
            "time_bin",
            "vehicle_count",
            "arrival_rate_per_min",
            "mean_interarrival_sec",
            "avg_speed",
            "avg_delay",
            "queue_ratio",
            "long_queue_ratio",
            "direction_imbalance",
            "signal_imbalance",
            "bottleneck_score",
        ]
    ]

    output_path = PROCESSED_ROOT / "screening_5min.csv"
    screening.to_csv(output_path, index=False)
    log_stage(
        "screening_5min",
        rows=len(screening),
        zero_vehicle_bins=int((screening["vehicle_count"] == 0).sum()),
        max_bottleneck_score=float(screening["bottleneck_score"].max()),
        output=relative_path(output_path),
    )


def selection_reason(row: pd.Series) -> str:
    return (
        f"mean_score={row['mean_bottleneck_score']:.4f}; "
        f"vehicles={int(row['total_vehicle_count'])}; "
        f"avg_speed={row['avg_speed']:.3f}; "
        f"avg_delay={row['avg_delay']:.3f}; "
        f"queue_ratio={row['queue_ratio']:.3f}"
    )


def run_select_candidate_window() -> None:
    ensure_output_dirs()
    screening = pd.read_csv(
        PROCESSED_ROOT / "screening_5min.csv",
        parse_dates=["time_bin"],
        low_memory=False,
    )

    window_rows: list[pd.DataFrame] = []
    for group, group_df in screening.groupby("intersection_group", sort=False):
        group_df = group_df.sort_values("time_bin").reset_index(drop=True)
        group_df["weighted_speed"] = group_df["avg_speed"].fillna(0.0) * group_df["vehicle_count"]
        group_df["weighted_delay"] = group_df["avg_delay"].fillna(0.0) * group_df["vehicle_count"]
        group_df["weighted_queue"] = group_df["queue_ratio"].fillna(0.0) * group_df["vehicle_count"]

        for window_size in WINDOW_SIZES:
            result = pd.DataFrame(
                {
                    "intersection_group": group,
                    "window_minutes": window_size * 5,
                    "window_end": group_df["time_bin"] + pd.Timedelta(minutes=5),
                    "mean_bottleneck_score": group_df["bottleneck_score"].rolling(window_size).mean(),
                    "max_bottleneck_score": group_df["bottleneck_score"].rolling(window_size).max(),
                    "total_vehicle_count": group_df["vehicle_count"].rolling(window_size).sum(),
                    "speed_weighted_sum": group_df["weighted_speed"].rolling(window_size).sum(),
                    "delay_weighted_sum": group_df["weighted_delay"].rolling(window_size).sum(),
                    "queue_weighted_sum": group_df["weighted_queue"].rolling(window_size).sum(),
                }
            )
            result["window_start"] = result["window_end"] - pd.Timedelta(minutes=window_size * 5)
            result["avg_speed"] = np.where(
                result["total_vehicle_count"] > 0,
                result["speed_weighted_sum"] / result["total_vehicle_count"],
                np.nan,
            )
            result["avg_delay"] = np.where(
                result["total_vehicle_count"] > 0,
                result["delay_weighted_sum"] / result["total_vehicle_count"],
                np.nan,
            )
            result["queue_ratio"] = np.where(
                result["total_vehicle_count"] > 0,
                result["queue_weighted_sum"] / result["total_vehicle_count"],
                np.nan,
            )
            result = result.dropna(subset=["mean_bottleneck_score"]).copy()
            window_rows.append(result)

    windows = pd.concat(window_rows, ignore_index=True)
    windows = windows.sort_values(
        [
            "intersection_group",
            "mean_bottleneck_score",
            "total_vehicle_count",
            "avg_speed",
            "avg_delay",
            "queue_ratio",
        ],
        ascending=[True, False, False, True, False, False],
    )

    ranked_frames = []
    shared_anchor = None
    if ENFORCE_SHARED_WINDOW:
        anchor_candidates = windows[windows["intersection_group"] == SHARED_WINDOW_ANCHOR_GROUP].reset_index(drop=True)
        if anchor_candidates.empty:
            raise ValueError(f"No candidate windows found for shared anchor group: {SHARED_WINDOW_ANCHOR_GROUP}")
        shared_anchor = anchor_candidates.iloc[0][["window_start", "window_end", "window_minutes"]].to_dict()

    for group, group_df in windows.groupby("intersection_group", sort=False):
        ordered = group_df.reset_index(drop=True).copy()
        ordered["rank"] = range(1, len(ordered) + 1)
        top = ordered.head(5).copy()
        top["is_selected"] = False
        top["selection_reason"] = top.apply(selection_reason, axis=1)

        if ENFORCE_SHARED_WINDOW and shared_anchor is not None:
            shared_mask = (
                (ordered["window_start"] == shared_anchor["window_start"])
                & (ordered["window_end"] == shared_anchor["window_end"])
                & (ordered["window_minutes"] == shared_anchor["window_minutes"])
            )
            shared_rows = ordered.loc[shared_mask].copy()
            if shared_rows.empty:
                raise ValueError(f"Shared window not found for group {group}")

            shared_row = shared_rows.iloc[[0]].copy()
            shared_row["is_selected"] = True
            shared_row["selection_reason"] = shared_row.apply(selection_reason, axis=1) + (
                f"; shared_window_from={SHARED_WINDOW_ANCHOR_GROUP}"
            )

            top_key = set(
                zip(
                    top["window_start"],
                    top["window_end"],
                    top["window_minutes"],
                )
            )
            shared_key = (
                shared_row.iloc[0]["window_start"],
                shared_row.iloc[0]["window_end"],
                shared_row.iloc[0]["window_minutes"],
            )
            if shared_key not in top_key:
                top = pd.concat([top, shared_row], ignore_index=True)
            else:
                top.loc[
                    (top["window_start"] == shared_key[0])
                    & (top["window_end"] == shared_key[1])
                    & (top["window_minutes"] == shared_key[2]),
                    ["is_selected", "selection_reason"],
                ] = [True, shared_row.iloc[0]["selection_reason"]]
        else:
            top.loc[top["rank"] == 1, "is_selected"] = True

        ranked_frames.append(top)

    ranked = pd.concat(ranked_frames, ignore_index=True)
    ranked = ranked[
        [
            "intersection_group",
            "window_start",
            "window_end",
            "window_minutes",
            "mean_bottleneck_score",
            "max_bottleneck_score",
            "total_vehicle_count",
            "avg_speed",
            "avg_delay",
            "queue_ratio",
            "rank",
            "is_selected",
            "selection_reason",
        ]
    ]
    output_path = PROCESSED_ROOT / "candidate_window.csv"
    ranked.to_csv(output_path, index=False)
    log_stage(
        "candidate_window",
        rows=len(ranked),
        selected=ranked.loc[ranked["is_selected"], ["intersection_group", "window_start", "window_end"]]
        .to_dict(orient="records"),
        output=relative_path(output_path),
    )


def fit_distribution(values: np.ndarray) -> dict[str, object]:
    values = values[np.isfinite(values)]
    values = values[values > 0]
    n = len(values)
    base = {
        "n": n,
        "best_distribution": "empirical",
        "param_1": np.nan,
        "param_2": np.nan,
        "param_3": np.nan,
        "mean_interarrival_sec": float(np.mean(values)) if n else np.nan,
        "std_interarrival_sec": float(np.std(values, ddof=1)) if n > 1 else np.nan,
        "ks_stat": np.nan,
        "ks_pvalue": np.nan,
        "aic": np.nan,
        "bic": np.nan,
    }
    if n < 30:
        return base

    candidates = {
        "exponential": stats.expon,
        "gamma": stats.gamma,
        "lognormal": stats.lognorm,
    }

    best_name = "empirical"
    best_payload = base
    best_aic = float("inf")

    def evaluate_candidate(name: str, distribution: object, params: tuple[float, ...]) -> None:
        nonlocal best_aic, best_name, best_payload
        try:
            log_likelihood = float(np.sum(distribution.logpdf(values, *params)))
            k = len(params)
            aic = 2 * k - 2 * log_likelihood
            bic = k * np.log(n) - 2 * log_likelihood
            ks_stat, ks_pvalue = stats.kstest(values, distribution.cdf, args=params)
        except Exception:
            return

        if aic < best_aic:
            best_aic = aic
            best_name = name
            best_payload = {
                **base,
                "best_distribution": best_name,
                "param_1": params[0] if len(params) > 0 else np.nan,
                "param_2": params[1] if len(params) > 1 else np.nan,
                "param_3": params[2] if len(params) > 2 else np.nan,
                "ks_stat": ks_stat,
                "ks_pvalue": ks_pvalue,
                "aic": aic,
                "bic": bic,
            }

    for name, distribution in candidates.items():
        try:
            params = distribution.fit(values, floc=0)
        except Exception:
            continue
        evaluate_candidate(name, distribution, params)

    try:
        gamma_shape, _, gamma_scale = stats.gamma.fit(values, floc=0)
        erlang_shape = max(1, int(round(gamma_shape)))
        erlang_scale = float(np.mean(values) / erlang_shape)
        evaluate_candidate("erlang", stats.erlang, (erlang_shape, 0.0, erlang_scale))
    except Exception:
        pass

    return best_payload


def run_make_arena_inputs() -> None:
    ensure_output_dirs()
    selected = events_in_selected_windows()
    selected["from_inter_id"] = text(selected["from_inter_id"]).replace("", "unknown")
    selected["turn_typ2to_inter"] = text(selected["turn_typ2to_inter"]).replace("", "unknown")
    selected["time_bin"] = selected["arrival_datetime"].dt.floor("5min")
    selected["window_start"] = pd.to_datetime(selected["window_start"])
    selected["window_end"] = pd.to_datetime(selected["window_end"])

    arrival_input = (
        selected.groupby(
            ["intersection_group", "window_start", "window_end", "from_inter_id", "turn_typ2to_inter", "time_bin"],
            dropna=False,
        )
        .agg(vehicle_count=("vhcl_id", "count"))
        .reset_index()
    )
    arrival_input["period_start_sec"] = (
        arrival_input["time_bin"] - arrival_input["window_start"]
    ).dt.total_seconds().astype(int)
    arrival_input["period_end_sec"] = arrival_input["period_start_sec"] + 300
    arrival_input["arrival_rate_per_min"] = arrival_input["vehicle_count"] / 5.0
    arrival_input["mean_interarrival_sec"] = np.where(
        arrival_input["vehicle_count"] > 0,
        300.0 / arrival_input["vehicle_count"],
        np.nan,
    )
    arrival_input = arrival_input[
        [
            "intersection_group",
            "window_start",
            "window_end",
            "from_inter_id",
            "turn_typ2to_inter",
            "time_bin",
            "period_start_sec",
            "period_end_sec",
            "vehicle_count",
            "arrival_rate_per_min",
            "mean_interarrival_sec",
        ]
    ].sort_values(["intersection_group", "from_inter_id", "turn_typ2to_inter", "time_bin"])

    arrival_schedule = selected[
        [
            "intersection_group",
            "window_start",
            "window_end",
            "from_inter_id",
            "turn_typ2to_inter",
            "vhcl_id",
            "arrival_datetime",
            "vhcl_typ",
        ]
    ].copy()
    arrival_schedule = arrival_schedule.sort_values(
        ["intersection_group", "from_inter_id", "turn_typ2to_inter", "arrival_datetime", "vhcl_id"]
    )
    arrival_schedule["arrival_offset_sec"] = (
        arrival_schedule["arrival_datetime"] - arrival_schedule["window_start"]
    ).dt.total_seconds()
    arrival_schedule["interarrival_sec"] = arrival_schedule.groupby(
        ["intersection_group", "from_inter_id", "turn_typ2to_inter"],
        dropna=False,
    )["arrival_offset_sec"].diff()
    arrival_schedule["vhcl_typ"] = numeric(arrival_schedule["vhcl_typ"]).astype("Int64")

    distribution_rows = []
    for keys, group in arrival_schedule.groupby(
        ["intersection_group", "from_inter_id", "turn_typ2to_inter"],
        dropna=False,
    ):
        payload = fit_distribution(group["interarrival_sec"].to_numpy(dtype=float))
        payload.update(
            {
                "intersection_group": keys[0],
                "from_inter_id": keys[1],
                "turn_typ2to_inter": keys[2],
            }
        )
        distribution_rows.append(payload)
    distribution_fit = pd.DataFrame(distribution_rows)
    distribution_fit = distribution_fit[
        [
            "intersection_group",
            "from_inter_id",
            "turn_typ2to_inter",
            "n",
            "best_distribution",
            "param_1",
            "param_2",
            "param_3",
            "mean_interarrival_sec",
            "std_interarrival_sec",
            "ks_stat",
            "ks_pvalue",
            "aic",
            "bic",
        ]
    ].sort_values(["intersection_group", "from_inter_id", "turn_typ2to_inter"])

    movement = (
        selected.groupby(
            ["intersection_group", "window_start", "window_end", "from_inter_id", "turn_typ2to_inter"],
            dropna=False,
        )
        .size()
        .rename("movement_count")
        .reset_index()
    )
    movement["total_count"] = movement.groupby(
        ["intersection_group", "window_start", "window_end", "from_inter_id"],
        dropna=False,
    )["movement_count"].transform("sum")
    movement["movement_ratio"] = movement["movement_count"] / movement["total_count"]
    movement = movement[
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

    type_ratio = (
        selected.groupby(
            ["intersection_group", "window_start", "window_end", "from_inter_id", "vhcl_typ"],
            dropna=False,
        )
        .size()
        .rename("count")
        .reset_index()
    )
    type_ratio["total_count"] = type_ratio.groupby(
        ["intersection_group", "window_start", "window_end", "from_inter_id"],
        dropna=False,
    )["count"].transform("sum")
    type_ratio["ratio"] = type_ratio["count"] / type_ratio["total_count"]
    type_ratio["vhcl_typ"] = numeric(type_ratio["vhcl_typ"]).astype("Int64")
    type_ratio["vehicle_type_name"] = type_ratio["vhcl_typ"].map(VEHICLE_TYPE_NAMES).fillna("unknown")
    type_ratio = type_ratio[
        [
            "intersection_group",
            "window_start",
            "window_end",
            "from_inter_id",
            "vhcl_typ",
            "vehicle_type_name",
            "count",
            "ratio",
        ]
    ].sort_values(["intersection_group", "from_inter_id", "vhcl_typ"])

    outputs = {
        PROCESSED_ROOT / "arrival_input_arena.csv": arrival_input,
        PROCESSED_ROOT / "arrival_schedule_arena.csv": arrival_schedule,
        PROCESSED_ROOT / "arrival_distribution_fit.csv": distribution_fit,
        PROCESSED_ROOT / "movement_ratio.csv": movement,
        PROCESSED_ROOT / "vehicle_type_ratio.csv": type_ratio,
    }
    for path, df in outputs.items():
        df.to_csv(path, index=False)

    log_stage(
        "arena_inputs",
        selected_events=len(selected),
        arrival_input_rows=len(arrival_input),
        arrival_schedule_rows=len(arrival_schedule),
        distribution_fit_rows=len(distribution_fit),
        movement_ratio_rows=len(movement),
        vehicle_type_ratio_rows=len(type_ratio),
        outputs=[relative_path(path) for path in outputs],
    )


def load_signal_csv_rows() -> pd.DataFrame:
    frames = []
    usecols = ["interid", "aringstarttime", "signalstate", "unix_time", "phasepattern"]
    target_values = {str(value) for value in TARGET_INTERSECTION_IDS}

    for file_index, path in enumerate(signal_csv_files(), start=1):
        chunk = pd.read_csv(path, usecols=usecols, low_memory=False, encoding="utf-8-sig")
        chunk["interid"] = text(chunk["interid"])
        chunk = chunk[chunk["interid"].isin(target_values)].copy()
        if chunk.empty:
            continue

        chunk["signal_start_time"] = pd.to_datetime(chunk["aringstarttime"], errors="coerce")
        missing_times = chunk["signal_start_time"].isna()
        if missing_times.any():
            chunk.loc[missing_times, "signal_start_time"] = unix_to_local_datetime(
                chunk.loc[missing_times, "unix_time"]
            )
        chunk["signal_state"] = text(chunk["signalstate"])
        chunk["phase"] = text(chunk["phasepattern"]).replace("", pd.NA)
        chunk["source_file"] = relative_path(path)
        frames.append(
            chunk[
                [
                    "interid",
                    "signal_start_time",
                    "signal_state",
                    "phase",
                    "unix_time",
                    "source_file",
                ]
            ]
        )

        if file_index % 50 == 0 or file_index == len(signal_csv_files()):
            print(f"[signal_plan] scanned {file_index}/{len(signal_csv_files())} signal files")

    if not frames:
        return pd.DataFrame(
            columns=["interid", "signal_start_time", "signal_state", "phase", "unix_time", "source_file"]
        )

    signal_df = pd.concat(frames, ignore_index=True)
    signal_df = signal_df.dropna(subset=["signal_start_time"]).drop_duplicates(
        subset=["interid", "signal_start_time", "signal_state"]
    )
    signal_df = signal_df.sort_values(["interid", "signal_start_time"])
    return signal_df


def run_make_signal_plan() -> None:
    ensure_output_dirs()
    windows = selected_windows()
    signal_df = load_signal_csv_rows()

    rows = []
    for window in windows.itertuples(index=False):
        relevant_ids = ["215173", "215174"] if window.intersection_group == "15+16" else [str(TARGET_INTERSECTIONS[window.intersection_group])]
        for interid in relevant_ids:
            subset = signal_df[signal_df["interid"] == interid].copy()
            if subset.empty:
                continue

            before_window = subset[subset["signal_start_time"] <= window.window_start].tail(1)
            within_window = subset[
                (subset["signal_start_time"] >= window.window_start)
                & (subset["signal_start_time"] < window.window_end)
            ]
            window_states = pd.concat([before_window, within_window], ignore_index=True)
            if window_states.empty:
                continue

            window_states = window_states.sort_values("signal_start_time").drop_duplicates(
                subset=["signal_start_time", "signal_state"]
            )
            window_states["signal_start_time"] = window_states["signal_start_time"].clip(lower=window.window_start)
            window_states["signal_end_time"] = window_states["signal_start_time"].shift(-1)
            window_states["signal_end_time"] = window_states["signal_end_time"].fillna(window.window_end)
            window_states["signal_end_time"] = window_states["signal_end_time"].clip(upper=window.window_end)
            window_states = window_states[window_states["signal_end_time"] > window_states["signal_start_time"]].copy()
            window_states["duration_sec"] = (
                window_states["signal_end_time"] - window_states["signal_start_time"]
            ).dt.total_seconds()
            window_states["offset_sec"] = (
                window_states["signal_start_time"] - window.window_start
            ).dt.total_seconds()
            missing_phase = window_states["phase"].isna()
            if missing_phase.any():
                fallback_phases = [f"phase_{index + 1:02d}" for index in range(int(missing_phase.sum()))]
                window_states.loc[missing_phase, "phase"] = fallback_phases

            for row in window_states.itertuples(index=False):
                rows.append(
                    {
                        "intersection_group": window.intersection_group,
                        "window_start": window.window_start,
                        "window_end": window.window_end,
                        "inter_id": int(interid),
                        "signal_start_time": row.signal_start_time,
                        "signal_end_time": row.signal_end_time,
                        "phase": row.phase,
                        "signal_state": row.signal_state,
                        "duration_sec": row.duration_sec,
                        "offset_sec": row.offset_sec,
                    }
                )

    output = pd.DataFrame(rows).sort_values(["intersection_group", "inter_id", "signal_start_time"])
    output_path = PROCESSED_ROOT / "signal_plan_as_is.csv"
    output.to_csv(output_path, index=False)
    log_stage(
        "signal_plan_as_is",
        rows=len(output),
        intersections=sorted(output["inter_id"].unique().tolist()) if not output.empty else [],
        output=relative_path(output_path),
    )


def run_make_validation_targets() -> None:
    ensure_output_dirs()
    selected = events_in_selected_windows()
    selected["from_inter_id"] = text(selected["from_inter_id"]).replace("", "unknown")
    selected["turn_typ2to_inter"] = text(selected["turn_typ2to_inter"]).replace("", "unknown")
    selected["queue_flag"] = queue_flag(selected["que_all"])
    selected["long_queue_flag"] = long_queue_flag(selected)

    validation = (
        selected.groupby(
            ["intersection_group", "window_start", "window_end", "from_inter_id", "turn_typ2to_inter"],
            dropna=False,
        )
        .agg(
            vehicle_count=("vhcl_id", "count"),
            avg_speed=("spd", "mean"),
            avg_delay=("tl", "mean"),
            queue_ratio=("queue_flag", "mean"),
            long_queue_ratio=("long_queue_flag", "mean"),
        )
        .reset_index()
        .sort_values(["intersection_group", "from_inter_id", "turn_typ2to_inter"])
    )

    output_path = PROCESSED_ROOT / "validation_targets.csv"
    validation.to_csv(output_path, index=False)
    log_stage(
        "validation_targets",
        rows=len(validation),
        output=relative_path(output_path),
    )


def plot_metric(screening: pd.DataFrame, metric: str, ylabel: str, filename: str) -> None:
    fig, ax = plt.subplots(figsize=(14, 5))
    for group in INTERSECTION_GROUPS:
        group_df = screening[screening["intersection_group"] == group]
        ax.plot(group_df["time_bin"], group_df[metric], label=group, linewidth=1.8)
    ax.set_title(ylabel)
    ax.set_xlabel("Time")
    ax.set_ylabel(ylabel)
    ax.legend()
    ax.grid(True, alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIGURES_ROOT / filename, dpi=160)
    plt.close(fig)


def plot_movement_ratio(movement: pd.DataFrame) -> None:
    fig, axes = plt.subplots(len(INTERSECTION_GROUPS), 1, figsize=(14, 10), sharex=False)
    for ax, group in zip(axes, INTERSECTION_GROUPS):
        group_df = movement[movement["intersection_group"] == group]
        if group_df.empty:
            ax.text(0.5, 0.5, "No data", ha="center", va="center")
            ax.set_axis_off()
            continue

        pivot = group_df.pivot_table(
            index="from_inter_id",
            columns="turn_typ2to_inter",
            values="movement_ratio",
            fill_value=0.0,
        )
        pivot.plot(kind="bar", stacked=True, ax=ax, width=0.8)
        ax.set_title(f"Movement Ratio - {group}")
        ax.set_ylabel("Ratio")
        ax.yaxis.set_major_formatter(PercentFormatter(1.0))
        ax.legend(
            title="Turn",
            loc="upper left",
            bbox_to_anchor=(1.01, 1.0),
            borderaxespad=0.0,
            ncol=1,
        )
    fig.tight_layout(rect=[0, 0, 0.84, 1])
    fig.savefig(FIGURES_ROOT / "movement_ratio.png", dpi=160)
    plt.close(fig)


def plot_vehicle_type_ratio(type_ratio: pd.DataFrame) -> None:
    fig, axes = plt.subplots(len(INTERSECTION_GROUPS), 1, figsize=(12, 10), sharex=False)
    for ax, group in zip(axes, INTERSECTION_GROUPS):
        group_df = type_ratio[type_ratio["intersection_group"] == group]
        if group_df.empty:
            ax.text(0.5, 0.5, "No data", ha="center", va="center")
            ax.set_axis_off()
            continue

        summary = (
            group_df.groupby("vehicle_type_name", dropna=False)["ratio"]
            .mean()
            .sort_values(ascending=False)
        )
        summary.plot(kind="bar", ax=ax, color="#2b7a78")
        ax.set_title(f"Vehicle Type Ratio - {group}")
        ax.set_ylabel("Ratio")
        ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    fig.tight_layout()
    fig.savefig(FIGURES_ROOT / "vehicle_type_ratio.png", dpi=160)
    plt.close(fig)


def plot_interarrival_histogram(schedule: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, len(INTERSECTION_GROUPS), figsize=(15, 4), sharey=True)
    for ax, group in zip(axes, INTERSECTION_GROUPS):
        values = schedule.loc[schedule["intersection_group"] == group, "interarrival_sec"].dropna()
        values = values[values > 0]
        if values.empty:
            ax.text(0.5, 0.5, "No data", ha="center", va="center")
            ax.set_axis_off()
            continue
        upper = float(values.quantile(0.99))
        upper = upper if math.isfinite(upper) and upper > 0 else float(values.max())
        if upper <= 20:
            bin_width = 1
        elif upper <= 60:
            bin_width = 2
        elif upper <= 180:
            bin_width = 5
        else:
            bin_width = 10

        visible_values = values[values <= upper]
        bins = np.arange(0, upper + bin_width, bin_width)
        if len(bins) < 2:
            bins = 20

        ax.hist(visible_values, bins=bins, color="#fe6d73", alpha=0.8)
        ax.set_title(group)
        ax.set_xlabel("Interarrival (sec)")
        ax.set_ylabel("Count")
        ax.set_xlim(0, upper)
        ax.xaxis.set_major_locator(MultipleLocator(bin_width * 2))
        clipped_count = int((values > upper).sum())
        if clipped_count > 0:
            ax.text(
                0.98,
                0.95,
                f"Top 1% omitted: {clipped_count}",
                transform=ax.transAxes,
                ha="right",
                va="top",
                fontsize=9,
                color="#555555",
            )
    fig.tight_layout()
    fig.savefig(FIGURES_ROOT / "interarrival_histogram.png", dpi=160)
    plt.close(fig)


def plot_distribution_fit(schedule: pd.DataFrame, distribution_fit: pd.DataFrame) -> None:
    fit = distribution_fit[distribution_fit["best_distribution"] != "empirical"].sort_values(
        ["n", "aic"], ascending=[False, True]
    )
    fig, ax = plt.subplots(figsize=(10, 6))
    if fit.empty:
        ax.text(0.5, 0.5, "No fitted distribution with n >= 30", ha="center", va="center")
        ax.set_axis_off()
    else:
        row = fit.iloc[0]
        sample = schedule[
            (schedule["intersection_group"] == row["intersection_group"])
            & (schedule["from_inter_id"] == row["from_inter_id"])
            & (schedule["turn_typ2to_inter"] == row["turn_typ2to_inter"])
        ]["interarrival_sec"].dropna()
        values = np.sort(sample[sample > 0].to_numpy(dtype=float))
        y = np.arange(1, len(values) + 1) / len(values)
        ax.step(values, y, where="post", label="Empirical CDF", linewidth=2.0)

        distribution = {
            "exponential": stats.expon,
            "erlang": stats.erlang,
            "gamma": stats.gamma,
            "lognormal": stats.lognorm,
        }.get(row["best_distribution"])
        if distribution is not None:
            params = [row["param_1"], row["param_2"], row["param_3"]]
            params = [param for param in params if pd.notna(param)]
            xs = np.linspace(values.min(), values.max(), 200)
            ax.plot(xs, distribution.cdf(xs, *params), label=row["best_distribution"], linewidth=2.0)

        ax.set_title(
            f"Fit: {row['intersection_group']} / {row['from_inter_id']} / {row['turn_typ2to_inter']}"
        )
        ax.set_xlabel("Interarrival (sec)")
        ax.set_ylabel("CDF")
        ax.legend()
        ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGURES_ROOT / "distribution_fit_comparison.png", dpi=160)
    plt.close(fig)


def summary_by_group(df: pd.DataFrame, value_column: str, top_n: int = 3) -> pd.DataFrame:
    summary = (
        df.sort_values(["intersection_group", value_column], ascending=[True, False])
        .groupby("intersection_group", sort=False)
        .head(top_n)
        .copy()
    )
    return summary


def run_make_figures() -> None:
    ensure_output_dirs()
    plt.style.use("seaborn-v0_8-whitegrid")

    screening = pd.read_csv(PROCESSED_ROOT / "screening_5min.csv", parse_dates=["time_bin"], low_memory=False)
    movement = pd.read_csv(PROCESSED_ROOT / "movement_ratio.csv", parse_dates=["window_start", "window_end"])
    type_ratio = pd.read_csv(PROCESSED_ROOT / "vehicle_type_ratio.csv", parse_dates=["window_start", "window_end"])
    schedule = pd.read_csv(
        PROCESSED_ROOT / "arrival_schedule_arena.csv",
        parse_dates=["window_start", "window_end", "arrival_datetime"],
        low_memory=False,
    )
    distribution_fit = pd.read_csv(PROCESSED_ROOT / "arrival_distribution_fit.csv", low_memory=False)
    candidate = pd.read_csv(
        PROCESSED_ROOT / "candidate_window.csv",
        parse_dates=["window_start", "window_end"],
        low_memory=False,
    )
    validation = pd.read_csv(
        PROCESSED_ROOT / "validation_targets.csv",
        parse_dates=["window_start", "window_end"],
        low_memory=False,
    )
    inventory = pd.read_csv(PROCESSED_ROOT / "data_inventory.csv", low_memory=False)
    vehicle_core = pd.read_csv(
        latest_vehicle_core_path(),
        parse_dates=["datetime"],
        low_memory=False,
    )
    arrival_events = load_arrival_events()

    plot_metric(screening, "vehicle_count", "Traffic Volume per 5 Minutes", "traffic_volume_5min.png")
    plot_metric(screening, "avg_speed", "Average Speed", "avg_speed_5min.png")
    plot_metric(screening, "avg_delay", "Average Delay", "avg_delay_5min.png")
    plot_metric(screening, "queue_ratio", "Queue Ratio", "queue_ratio_5min.png")
    plot_metric(screening, "bottleneck_score", "Bottleneck Score", "bottleneck_score_5min.png")
    plot_movement_ratio(movement)
    plot_vehicle_type_ratio(type_ratio)
    plot_interarrival_histogram(schedule)
    plot_distribution_fit(schedule, distribution_fit)

    source_summary = (
        inventory.groupby("data_family").agg(file_count=("file_path", "count"), total_size=("file_size_bytes", "sum")).reset_index()
    )
    arrival_counts = (
        arrival_events.groupby("intersection_group")["vhcl_id"].count().rename("arrival_events").reset_index()
    )
    top_candidates = candidate.sort_values(["intersection_group", "rank"]).groupby("intersection_group").head(5)
    selected_candidate = candidate[candidate["is_selected"].map(bool_from_any)].copy()
    top_movements = summary_by_group(movement, "movement_ratio")
    top_vehicle_types = (
        type_ratio.groupby(["intersection_group", "vehicle_type_name"], dropna=False)["count"]
        .sum()
        .rename("count")
        .reset_index()
    )
    top_vehicle_types["total_count"] = top_vehicle_types.groupby("intersection_group")["count"].transform("sum")
    top_vehicle_types["ratio"] = top_vehicle_types["count"] / top_vehicle_types["total_count"]
    top_vehicle_types = summary_by_group(top_vehicle_types, "ratio")
    validation_summary = (
        validation.groupby("intersection_group")
        .agg(
            vehicle_count=("vehicle_count", "sum"),
            avg_speed=("avg_speed", "mean"),
            avg_delay=("avg_delay", "mean"),
            queue_ratio=("queue_ratio", "mean"),
            long_queue_ratio=("long_queue_ratio", "mean"),
        )
        .reset_index()
    )

    source_summary_table = source_summary.copy()
    source_summary_table["data_family"] = source_summary_table["data_family"].map(translate_data_family)
    source_summary_table["total_size_mb"] = (source_summary_table["total_size"] / 1024 / 1024).round(2)
    source_summary_table = source_summary_table.rename(
        columns={"data_family": "원천 데이터 종류", "file_count": "파일 수", "total_size_mb": "총 용량(MB)"}
    )[["원천 데이터 종류", "파일 수", "총 용량(MB)"]]

    arrival_counts_table = arrival_counts.copy()
    arrival_counts_table["intersection_group"] = arrival_counts_table["intersection_group"].map(translate_intersection_group)
    arrival_counts_table = arrival_counts_table.rename(
        columns={"intersection_group": "분석 대상", "arrival_events": "도착 이벤트 수"}
    )

    top_candidates_table = round_numeric_columns(
        top_candidates[
            ["intersection_group", "rank", "window_start", "window_end", "window_minutes", "mean_bottleneck_score", "total_vehicle_count"]
        ],
        {"mean_bottleneck_score": 3, "total_vehicle_count": 0},
    )
    top_candidates_table["intersection_group"] = top_candidates_table["intersection_group"].map(translate_intersection_group)
    top_candidates_table = top_candidates_table.rename(
        columns={
            "intersection_group": "분석 대상",
            "rank": "순위",
            "window_start": "시작 시각",
            "window_end": "종료 시각",
            "window_minutes": "길이(분)",
            "mean_bottleneck_score": "평균 병목 점수",
            "total_vehicle_count": "차량 수",
        }
    )

    selected_candidate_table = round_numeric_columns(
        selected_candidate[
            ["intersection_group", "window_start", "window_end", "window_minutes", "mean_bottleneck_score", "total_vehicle_count", "avg_speed", "avg_delay", "queue_ratio"]
        ],
        {"mean_bottleneck_score": 3, "total_vehicle_count": 0, "avg_speed": 2, "avg_delay": 3},
    )
    selected_candidate_table["intersection_group"] = selected_candidate_table["intersection_group"].map(translate_intersection_group)
    selected_candidate_table["queue_ratio"] = percent_text(selected_candidate_table["queue_ratio"], 1)
    selected_candidate_table = selected_candidate_table.rename(
        columns={
            "intersection_group": "최종 구간",
            "window_start": "시작 시각",
            "window_end": "종료 시각",
            "window_minutes": "길이(분)",
            "mean_bottleneck_score": "평균 병목 점수",
            "total_vehicle_count": "차량 수",
            "avg_speed": "평균 속도",
            "avg_delay": "평균 지체시간",
            "queue_ratio": "대기행렬 비율",
        }
    )

    top_movements_table = round_numeric_columns(
        top_movements[["intersection_group", "from_inter_id", "turn_typ2to_inter", "movement_ratio"]],
        {},
    )
    top_movements_table["intersection_group"] = top_movements_table["intersection_group"].map(translate_intersection_group)
    top_movements_table["turn_typ2to_inter"] = top_movements_table["turn_typ2to_inter"].map(translate_turn)
    top_movements_table["movement_ratio"] = percent_text(top_movements_table["movement_ratio"], 1)
    top_movements_table = top_movements_table.rename(
        columns={
            "intersection_group": "분석 대상",
            "from_inter_id": "유입 방향 ID",
            "turn_typ2to_inter": "이동 방향",
            "movement_ratio": "비율",
        }
    )

    top_vehicle_types_table = top_vehicle_types[["intersection_group", "vehicle_type_name", "ratio"]].copy()
    top_vehicle_types_table["intersection_group"] = top_vehicle_types_table["intersection_group"].map(translate_intersection_group)
    top_vehicle_types_table["vehicle_type_name"] = top_vehicle_types_table["vehicle_type_name"].map(translate_vehicle_type_name)
    top_vehicle_types_table["ratio"] = percent_text(top_vehicle_types_table["ratio"], 1)
    top_vehicle_types_table = top_vehicle_types_table.rename(
        columns={"intersection_group": "분석 대상", "vehicle_type_name": "차종", "ratio": "비율"}
    )

    validation_summary_table = round_numeric_columns(
        validation_summary.copy(),
        {"avg_speed": 2, "avg_delay": 3},
    )
    validation_summary_table["intersection_group"] = validation_summary_table["intersection_group"].map(translate_intersection_group)
    validation_summary_table["queue_ratio"] = percent_text(validation_summary_table["queue_ratio"], 1)
    validation_summary_table["long_queue_ratio"] = percent_text(validation_summary_table["long_queue_ratio"], 1)
    validation_summary_table = validation_summary_table.rename(
        columns={
            "intersection_group": "분석 대상",
            "vehicle_count": "차량 수",
            "avg_speed": "평균 속도",
            "avg_delay": "평균 지체시간",
            "queue_ratio": "대기행렬 비율",
            "long_queue_ratio": "긴 대기행렬 비율",
        }
    )

    validation_preview_table = round_numeric_columns(
        validation[["intersection_group", "from_inter_id", "turn_typ2to_inter", "vehicle_count", "avg_speed", "avg_delay", "queue_ratio", "long_queue_ratio"]].head(15).copy(),
        {"avg_speed": 2, "avg_delay": 3},
    )
    validation_preview_table["intersection_group"] = validation_preview_table["intersection_group"].map(translate_intersection_group)
    validation_preview_table["turn_typ2to_inter"] = validation_preview_table["turn_typ2to_inter"].map(translate_turn)
    validation_preview_table["queue_ratio"] = percent_text(validation_preview_table["queue_ratio"], 1)
    validation_preview_table["long_queue_ratio"] = percent_text(validation_preview_table["long_queue_ratio"], 1)
    validation_preview_table = validation_preview_table.rename(
        columns={
            "intersection_group": "분석 대상",
            "from_inter_id": "유입 방향 ID",
            "turn_typ2to_inter": "이동 방향",
            "vehicle_count": "차량 수",
            "avg_speed": "평균 속도",
            "avg_delay": "평균 지체시간",
            "queue_ratio": "대기행렬 비율",
            "long_queue_ratio": "긴 대기행렬 비율",
        }
    )

    eda_summary = f"""# EDA 요약 보고서

## 1. 이번 분석에서 사용한 원천 데이터
아래 파일들을 바탕으로 2022-05-09 하루 동안의 교차로 15, 16, 그리고 15+16 구간을 분석했습니다.

{dataframe_to_table(source_summary_table)}

## 2. 전처리 결과 한눈에 보기
- `vehicle_core` 행 수: {len(vehicle_core):,}건
- `arrival_events` 행 수: {len(arrival_events):,}건
- 차량 데이터 시간 범위: {vehicle_core['datetime'].min()} ~ {vehicle_core['datetime'].max()}

## 3. 분석 대상별 도착 이벤트 수
{dataframe_to_table(arrival_counts_table)}

## 4. 병목 후보 시간대 Top 5
병목 점수가 높은 시간대를 5개씩 정리했습니다. 점수가 높을수록 상대적으로 혼잡 가능성이 큰 시간대입니다.

{dataframe_to_table(top_candidates_table)}

## 5. 최종 선정된 분석 시간대
비교 목적을 맞추기 위해 세 분석 대상 모두 같은 시간대를 사용했습니다.
기준은 `교차로 15+16`에서 병목 점수가 가장 높게 나온 공통 구간입니다.

{dataframe_to_table(selected_candidate_table)}

## 6. 주요 유입 방향과 이동 방향
유입 방향별로 어떤 이동 방향 비중이 큰지 요약했습니다.

{dataframe_to_table(top_movements_table)}

## 7. 차종 구성
선정된 시간대에 어떤 차종이 많이 들어오는지 정리했습니다.

{dataframe_to_table(top_vehicle_types_table)}

## 8. 검증용 기준 지표
나중에 Arena 결과와 비교할 대표 지표입니다.

{dataframe_to_table(validation_summary_table)}

## 9. 해석할 때 참고할 점
- 이번 병목 점수 계산에서는 `signal_imbalance`를 `0`으로 두었습니다. 원시 신호 로그만으로는 모든 유입 방향에 대해 바로 비교 가능한 차로별 배분 지표를 안정적으로 만들기 어려웠기 때문입니다.
- 위 "6. 주요 유입 방향과 이동 방향"의 `미상`은 원본 회전방향 필드가 비어 있던 기록으로, 전체의 약 43.5%를 차지합니다. 처리 방법(재정규화 등)은 팀 논의가 필요합니다. (자세한 내용은 저장소 README의 "팀 논의 필요" 참고)
- 신호는 `signal_plan_as_is.csv`(원본 문자열) → `signal_green_windows.csv`(녹/적 타이밍) → `signal_green_windows_labeled.csv`(방향 라벨 포함, 네트워크 데이터 사용)까지 가공되어 있습니다.
- Arena 입력에 바로 쓰는 주요 파일은 `data_processed/arrival_input_arena.csv`, `data_processed/arrival_schedule_arena.csv`, `data_processed/movement_ratio.csv`, `data_processed/vehicle_type_ratio.csv`, `data_processed/signal_green_windows_labeled.csv`, `data_processed/validation_targets.csv` 입니다.
"""

    arena_summary = f"""# Arena 입력 요약 보고서

## 1. 어떤 시간대를 Arena에 넣는가
아래 시간대가 최종 분석 구간입니다.
이번에는 교차로 15, 교차로 16, 교차로 15+16을 공정하게 비교하기 위해 세 대상 모두 같은 시간대를 사용했습니다.
기준 시간대는 `교차로 15+16`에서 가장 대표성이 높았던 1시간 구간입니다.

{dataframe_to_table(selected_candidate_table[['최종 구간', '시작 시각', '종료 시각', '길이(분)']])}

## 2. `arrival_input_arena.csv`는 어떻게 쓰는가
- 이 파일은 5분 단위 평균 도착률을 담고 있습니다.
- `intersection_group`, `from_inter_id`, `turn_typ2to_inter` 조합별로 Create 모듈의 시간대별 도착 입력값으로 쓰면 됩니다.

## 3. `arrival_schedule_arena.csv`는 어떻게 쓰는가
- 이 파일은 선택된 병목 시간대 시작 시점을 0초로 두고, 차량이 실제로 몇 초에 들어왔는지를 기록한 파일입니다.
- 실제 도착 시각을 최대한 그대로 재현하고 싶을 때 Schedule 기반 입력으로 사용하면 됩니다.

## 4. 방향 분기 정보
어느 유입 방향에서 직진, 좌회전, 우회전이 얼마나 나오는지 정리한 표입니다.

{dataframe_to_table(top_movements_table)}

- `미상`은 원본 데이터에 회전방향이 기록되지 않은 차량으로, 전체의 약 43.5%입니다.
- Arena의 회전 확률로 쓸 때 `미상`을 어떻게 처리할지(예: 제외 후 재정규화)는 팀 논의가 필요합니다. (README "팀 논의 필요" 참고)

## 5. 차종 속성 정보
차량 엔티티에 차종 속성을 부여할 때 참고할 비율입니다.

{dataframe_to_table(top_vehicle_types_table)}

## 6. 신호 계획 정보
- `signal_plan_as_is.csv`에는 선택된 시간대 안에서 실제 신호 상태(SUMO 신호 문자열)가 언제 시작되고 끝나는지가 들어 있습니다.
- `offset_sec`는 각 분석 구간 시작 시점으로부터 몇 초 뒤에 해당 신호 상태가 시작되는지를 뜻합니다.
- 신호 문자열을 풀어 이동류별 녹/적 타이밍을 정리한 파일이 `signal_green_windows.csv`이고, 여기에 네트워크 데이터(net.xml)로 방향(직진/좌/우) 라벨까지 붙인 최종 파일이 `signal_green_windows_labeled.csv`입니다.
- Arena의 Hold(Wait for Signal)에 연결할 때는 `signal_green_windows_labeled.csv`의 `direction`과 `green_start_sec`/`green_end_sec`를 쓰면 됩니다.

## 7. 검증 기준 데이터
Arena 결과와 비교할 때 사용할 대표 기준값 예시입니다.

{dataframe_to_table(validation_preview_table)}

## 8. Arena 모델에 연결하는 추천 순서
- `arrival_input_arena.csv`: 시간대별 차량 생성률 입력
- `movement_ratio.csv`: 차량 진행 방향 분기 확률 입력 (단, `미상` 처리 방법은 팀 논의 필요)
- `vehicle_type_ratio.csv`: 차량 차종 속성 부여
- `signal_green_windows_labeled.csv`: 신호 현시 재현 (이동류별 녹색 구간 + 방향 라벨)
- `validation_targets.csv`: 속도, 지체, 대기행렬, 처리량 검증
"""

    (REPORTS_ROOT / "eda_summary.md").write_text(eda_summary, encoding="utf-8-sig")
    (REPORTS_ROOT / "arena_input_summary.md").write_text(arena_summary, encoding="utf-8-sig")

    log_stage(
        "figures_and_reports",
        figures=[relative_path(path) for path in sorted(FIGURES_ROOT.glob("*.png"))],
        reports=[relative_path(path) for path in sorted(REPORTS_ROOT.glob("*.md"))],
    )
