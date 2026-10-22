#!/usr/bin/env python3
"""Explicit, auditable CSV ingestion; no native binary decoding or automatic map matching."""
import argparse
import bisect
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path

UNITS = {
    "time_s": {"s": 1, "ms": .001},
    "distance_m": {"m": 1, "km": 1000},
    "speed_mps": {"m/s": 1, "km/h": 1/3.6, "mph": .44704},
    "throttle_pct": {"%": 1, "fraction": 100},
    "brake_position_pct": {"%": 1, "fraction": 100},
    "brake_pressure_bar": {"bar": 1, "kPa": .01, "psi": .0689475729},
    "steering_deg": {"deg": 1, "rad": 180/math.pi},
    "rpm": {"rpm": 1},
    "gear": {"count": 1},
    "latitude_deg": {"deg": 1},
    "longitude_deg": {"deg": 1},
}
MISSING = {"", "na", "n/a", "null", "nan"}

def finite(value, label):
    try:
        n = float(value)
    except (ValueError, TypeError) as e:
        raise ValueError(f"{label}: expected number") from e
    if not math.isfinite(n):
        raise ValueError(f"{label}: non-finite value")
    return n

def load_csv(path, mapping):
    path = Path(path)
    if path.suffix.lower() != ".csv":
        raise ValueError("This helper accepts CSV only. Use racechrono_rcz.py for supported native RCZ; export .ld/.ldx through MoTeC i2.")
    if mapping.get("format") not in {"motec-i2-csv", "racechrono-csv"}:
        raise ValueError("Select an explicit supported format profile")
    if mapping.get("scope") != "one-contiguous-lap":
        raise ValueError("Select one contiguous lap using verified source-time bounds")
    rows = list(csv.reader(path.read_text(encoding="utf-8-sig").splitlines(),
                           delimiter=mapping.get("delimiter", ",")))
    h, u, d = [mapping.get(k) for k in ("header_row", "units_row", "data_row")]
    if any(not isinstance(x, int) or isinstance(x, bool) or x < 0 for x in (h, u, d)):
        raise ValueError("Row indexes must be nonnegative zero-based integers")
    if not h < u < d < len(rows):
        raise ValueError("Require header_row < units_row < data_row inside CSV")
    headers, units = rows[h], rows[u]
    channels = mapping["channels"]
    if "time_s" not in channels:
        raise ValueError("A verified time channel is required")
    selected, audit, used = {}, {}, set()
    for target, spec in channels.items():
        if target not in UNITS:
            raise ValueError(f"Unsupported target channel: {target}")
        idx = spec["column"]
        if not isinstance(idx, int) or isinstance(idx, bool) or idx < 0 or idx >= len(headers):
            raise ValueError(f"{target}: invalid column")
        if idx in used:
            raise ValueError("Do not map one physical channel to different semantics")
        used.add(idx)
        if headers[idx].strip() != spec["name"]:
            raise ValueError(f"{target}: source header changed")
        if idx >= len(units) or units[idx].strip() != spec["unit"]:
            raise ValueError(f"{target}: source unit changed or missing")
        if spec["unit"] not in UNITS[target]:
            raise ValueError(f"{target}: unsupported unit {spec['unit']}")
        selected[target] = (idx, UNITS[target][spec["unit"]])
        audit[target] = dict(spec)
    bounds = mapping.get("source_time_bounds_s")
    if not isinstance(bounds, list) or len(bounds) != 2:
        raise ValueError("Supply verified start/finish source_time_bounds_s")
    start, finish = [finite(v, "lap bound") for v in bounds]
    if finish <= start:
        raise ValueError("Lap bounds must increase")
    samples = []
    for number, row in enumerate(rows[d:], d + 1):
        if not row or all(not c.strip() for c in row):
            continue
        if len(row) != len(headers):
            raise ValueError(f"CSV record {number}: ragged row or unexpected footer")
        sample = {}
        for target, (idx, scale) in selected.items():
            raw = row[idx].strip()
            if raw.lower() in MISSING:
                if target == "time_s":
                    raise ValueError(f"CSV record {number}: missing time")
                sample[target] = None
            else:
                sample[target] = finite(raw, f"record {number} {target}") * scale
        if start - 1e-7 <= sample["time_s"] <= finish + 1e-7:
            sample["time_s"] -= start
            samples.append(sample)
    if len(samples) < 2:
        raise ValueError("Need at least two in-bound samples")
    ts = [s["time_s"] for s in samples]
    dt = [b-a for a,b in zip(ts, ts[1:])]
    if any(x <= 0 for x in dt):
        raise ValueError("Duplicate or backwards timestamps; repair source, do not silently sort")
    median_dt = statistics.median(dt)
    gap_limit = finite(mapping.get("max_gap_s", median_dt*3), "max_gap_s")
    if gap_limit <= 0:
        raise ValueError("max_gap_s must be positive")
    gaps = [[ts[i], ts[i+1]] for i,x in enumerate(dt) if x > gap_limit + 1e-8]
    warnings = ["Row rate is export cadence, not proof of original sensor sample rate."]
    if gaps:
        warnings.append("Gaps detected; interpolation across these spans is prohibited.")
    if abs(ts[0]) > 1e-6 or abs(ts[-1]-(finish-start)) > 1e-6:
        warnings.append("Lap boundaries lack exact samples; lap totals remain unverified.")
    if "brake_pressure_bar" not in selected:
        warnings.append("No measured brake pressure; do not diagnose pressure technique.")
    if "distance_m" in selected:
        ds = [s["distance_m"] for s in samples]
        if any(x is None for x in ds) or any(b <= a for a,b in zip(ds,ds[1:])):
            warnings.append("Distance missing, stopped or reset; unsuitable for time-at-distance.")
    if 1/median_dt < 5:
        warnings.append("Low-rate data; do not resolve fine pedal transitions.")
    return {
        "format": mapping["format"], "source_file": path.name,
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "synthetic": bool(mapping.get("synthetic", False)),
        "scope": mapping["scope"], "source_time_bounds_s": bounds,
        "mapping": audit, "sample_count": len(samples),
        "export_cadence_hz": 1/median_dt, "max_gap_s": gap_limit,
        "gaps_s": gaps, "warnings": warnings, "samples": samples,
    }

def time_at_distance(data, distance):
    samples = data["samples"]
    ds = [s.get("distance_m") for s in samples]
    if any(x is None or not math.isfinite(x) for x in ds):
        raise ValueError("A complete distance channel is required")
    if any(b <= a for a,b in zip(ds,ds[1:])):
        raise ValueError("Distance must strictly increase within the selected lap")
    idx = bisect.bisect_left(ds, distance)
    if idx < len(ds) and abs(ds[idx]-distance) < 1e-8:
        return samples[idx]["time_s"]
    if idx == 0 or idx == len(ds):
        raise ValueError("Requested position is outside coverage; no extrapolation")
    left, right = samples[idx-1], samples[idx]
    if right["time_s"] - left["time_s"] > data["max_gap_s"] + 1e-8:
        raise ValueError("Requested position crosses a data gap")
    weight = (distance-ds[idx-1])/(ds[idx]-ds[idx-1])
    return left["time_s"] + weight*(right["time_s"]-left["time_s"])

def compare(reference, comparison, positions, alignment_evidence):
    if not isinstance(alignment_evidence, str) or not alignment_evidence.strip():
        raise ValueError("Document evidence that distances identify the same physical positions")
    if len(positions) < 2 or any(not math.isfinite(x) for x in positions):
        raise ValueError("Need at least two finite positions")
    if any(b <= a for a,b in zip(positions,positions[1:])):
        raise ValueError("Positions must strictly increase")
    result = []
    previous = None
    for p in positions:
        rt, ct = time_at_distance(reference,p), time_at_distance(comparison,p)
        delta = ct-rt
        result.append({"distance_m": p, "reference_elapsed_s": rt,
                       "comparison_elapsed_s": ct, "delta_s": delta,
                       "segment_loss_s": None if previous is None else delta-previous})
        previous = delta
    # Even if requested anchors fall exactly on samples, do not imply a gap-free interval.
    for data, key in ((reference,"reference_elapsed_s"),(comparison,"comparison_elapsed_s")):
        first, last = result[0][key], result[-1][key]
        if any(a < last and b > first for a,b in data["gaps_s"]):
            raise ValueError("Comparison interval contains a data gap; select separate valid spans")
    total = result[-1]["delta_s"]-result[0]["delta_s"]
    return {"sign": "positive = comparison loses time",
            "alignment_evidence": alignment_evidence,
            "synthetic": reference["synthetic"] or comparison["synthetic"],
            "anchors": result, "interval_loss_s": total,
            "reconciliation_error_s": sum(r["segment_loss_s"] or 0 for r in result)-total,
            "limitations": ["Caller-supplied physical alignment is not independently verified by this script.",
                           "Linear interpolation within covered samples; export cadence is not measurement accuracy."]}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("csv")
    inspect.add_argument("--delimiter", default=",")
    norm = sub.add_parser("normalize")
    norm.add_argument("csv"); norm.add_argument("--mapping", required=True); norm.add_argument("--out", required=True)
    comp = sub.add_parser("compare")
    comp.add_argument("reference"); comp.add_argument("comparison")
    comp.add_argument("--positions", required=True, help="comma-separated metres")
    comp.add_argument("--alignment-evidence", required=True)
    comp.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            p = Path(args.csv)
            if p.suffix.lower() != ".csv":
                raise ValueError("CSV only; export native formats first")
            rows = list(csv.reader(p.read_text(encoding="utf-8-sig").splitlines(), delimiter=args.delimiter))
            print(json.dumps({"csv_records_zero_based": list(enumerate(rows[:25]))}, indent=2))
            return
        if args.command == "normalize":
            data = load_csv(args.csv, json.loads(Path(args.mapping).read_text()))
        else:
            data = compare(json.loads(Path(args.reference).read_text()),
                           json.loads(Path(args.comparison).read_text()),
                           [float(x) for x in args.positions.split(",")],
                           args.alignment_evidence)
        Path(args.out).write_text(json.dumps(data, indent=2, allow_nan=False)+"\n")
        print(json.dumps({k:v for k,v in data.items() if k not in {"samples","mapping"}}, indent=2))
    except (ValueError, KeyError, OSError, IndexError) as e:
        parser.exit(2, f"Error: {e}\n")

if __name__ == "__main__":
    main()
