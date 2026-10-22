#!/usr/bin/env python3
"""Read a verified RaceChrono single-fragment GPS RCZ profile, without resampling.

Standard library only. See references/racechrono-rcz.md for scope and evidence.
This is an independently written reader, not an official RaceChrono SDK.
"""
import argparse
import csv
import hashlib
import json
import math
import re
import statistics
import struct
import zipfile
from pathlib import Path, PurePosixPath

PROFILE = "racechrono-rcz-v1-single-fragment-gps-1"
MISSING_I32 = 2147483647
CHANNEL_RE = re.compile(r"channel_(\d+)_(\d+)_(\d+)_(\d+)_(\d+)$")
# channel ID: canonical name, storage encoding, divisor, unit
CHANNELS = {
    1: ("timestamp_ms", 1, 1, "unix ms"),
    2: ("distance_m", 1, 1000, "m"),
    3: ("position", 1, 6000000, "deg"),
    4: ("speed_mps", 0, 1000, "m/s"),
    5: ("altitude_m", 0, 1000, "m"),
    6: ("bearing_deg", 0, 1000, "deg"),
    30003: ("fix_type", 0, 1, "count"),
    30007: ("accuracy_m", 0, 1000, "m"),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def haversine_m(a, b):
    """Independent geometry check, not a claim about GPS accuracy."""
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dl = math.radians(b[0] - a[0])
    dn = math.radians(b[1] - a[1])
    v = math.sin(dl / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dn / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(min(1, max(0, v))))


def lap_number(laps, timestamp_ms):
    """Half-open intervals; an unfinished lap has no claimed lap time."""
    for lap in reversed(laps):
        if timestamp_ms >= lap["startTimestamp"]:
            end = lap.get("finishTimestamp")
            return lap["number"] if end is None or timestamp_ms < end else None
    return None


def read_rcz(path, max_uncompressed_bytes=256 * 1024 * 1024):
    path = Path(path)
    warnings = []
    with zipfile.ZipFile(path) as z:
        entries = z.infolist()
        names = [e.filename for e in entries]
        require(len(names) == len(set(names)), "Duplicate ZIP member names")
        require(sum(e.file_size for e in entries) <= max_uncompressed_bytes,
                "Archive exceeds uncompressed size limit")
        for e in entries:
            p = PurePosixPath(e.filename)
            require(not p.is_absolute() and ".." not in p.parts and "\\" not in e.filename,
                    "Unsafe archive path")
            require(not e.flag_bits & 1, "Encrypted archives are unsupported")
        require("session.json" in names and "sessionfragment.json" in names,
                "Supported profile requires root session.json and sessionfragment.json; backups need a separate adapter")
        require(not any("/" in n.rstrip("/") for n in names),
                "Nested or multi-fragment archive unsupported; export a single session/fragment or CSV")
        require(not any(n.startswith("sessionfragment") and n != "sessionfragment.json" for n in names),
                "Multiple session fragments are unsupported")
        meta = json.loads(z.read("session.json"))
        fragment = json.loads(z.read("sessionfragment.json"))
        require(meta.get("version") == 1 and fragment.get("version") == 1,
                "Unsupported metadata version")
        devices = [d.get("selector", {}) for d in fragment.get("devices2", [])]
        if not devices:
            devices = fragment.get("devices", {}).get("items", [])
        primary = fragment.get("primaryGpsDeviceIndex")
        require(isinstance(primary, int) and not isinstance(primary, bool), "Missing primary GPS device ID")
        selected = [d for d in devices if d.get("id") == primary]
        require(len(selected) == 1 and selected[0].get("type") == 1,
                "Primary device must be uniquely identified as GPS in sessionfragment.json")
        laps = meta.get("laps", [])
        require(isinstance(laps, list), "Invalid laps metadata")
        prior_start = -math.inf
        prior_finish = -math.inf
        seen_numbers = set()
        for i, lap in enumerate(laps):
            require(lap.get("sessionResume", 0) == 0, "Resumed sessions require a multi-fragment adapter")
            start, finish, number = lap.get("startTimestamp"), lap.get("finishTimestamp"), lap.get("number")
            require(isinstance(start, int) and start > prior_start, "Lap starts must increase")
            require(isinstance(number, int) and number not in seen_numbers, "Invalid or duplicate lap number")
            require(start >= prior_finish, "Overlapping lap intervals")
            require(finish is None or isinstance(finish, int) and finish > start, "Invalid lap finish")
            require(finish is not None or i == len(laps) - 1, "Only final lap may be incomplete")
            seen_numbers.add(number)
            prior_start, prior_finish = start, finish or start

        inventory, decoded, provenance = [], {}, {}
        seen_channels = set()
        for name in names:
            if not name.startswith("channel"):
                continue
            match = CHANNEL_RE.fullmatch(name)
            require(match is not None, f"Unsupported channel filename: {name}")
            serial, device, fragment_id, channel, encoding = map(int, match.groups())
            require(serial == 1 and fragment_id == 0,
                    f"Unsupported channel stream/fragment in {name}; no streams will be silently merged")
            key = (device, channel)
            require(key not in seen_channels, f"Duplicate device/channel {key}")
            seen_channels.add(key)
            info = {"file": name, "device_id": device, "channel_id": channel,
                    "encoding": encoding, "bytes": z.getinfo(name).file_size,
                    "decoded": device == primary and channel in CHANNELS}
            inventory.append(info)
            if not info["decoded"]:
                continue
            canonical, expected_encoding, divisor, unit = CHANNELS[channel]
            require(encoding == expected_encoding, f"Unsupported encoding for verified channel {channel}")
            raw = z.read(name)  # zipfile checks CRC; never extract paths from the archive.
            width = 8 if encoding == 1 else 4
            require(len(raw) > 0 and len(raw) % width == 0, f"Invalid channel byte length: {name}")
            if channel == 3:
                pairs = list(struct.iter_unpack("<ii", raw))
                values = [(None, None) if MISSING_I32 in p else (p[0] / divisor, p[1] / divisor) for p in pairs]
                require(all(p[0] is None or -90 <= p[0] <= 90 and -180 <= p[1] <= 180 for p in values),
                        "Decoded coordinates outside degree ranges")
            else:
                raw_values = [v[0] for v in struct.iter_unpack("<q" if encoding == 1 else "<i", raw)]
                if encoding == 1:
                    require(all(0 <= v < 2**63 - 1 for v in raw_values), "Invalid timestamp/distance integer")
                values = [None if encoding == 0 and v == MISSING_I32 else v if divisor == 1 else v / divisor
                          for v in raw_values]
            decoded[canonical] = values
            provenance[canonical] = {**info, "divisor": divisor, "unit": unit,
                                     "byte_order": "little", "samples": len(values)}

    require(all(k in decoded for k in ("timestamp_ms", "distance_m", "position", "speed_mps")),
            "Profile requires timestamp, cumulative distance, position and speed")
    ts = decoded["timestamp_ms"]
    n = len(ts)
    require(n >= 2 and all(len(v) == n for v in decoded.values()), "Primary GPS channel lengths differ or too short")
    dt = [(b-a)/1000 for a, b in zip(ts, ts[1:])]
    require(min(dt) > 0, "GPS timestamps repeat or go backwards; no silent sorting")
    distance = decoded["distance_m"]
    require(all(b >= a for a, b in zip(distance, distance[1:])), "Cumulative distance resets/backtracks")
    require(all(v is None or v >= 0 for v in decoded["speed_mps"]), "Negative GPS speed")
    require(all(v is None or v >= 0 for v in decoded.get("accuracy_m", [])), "Negative GPS accuracy")
    require(all(v is None or 0 <= v <= 360 for v in decoded.get("bearing_deg", [])), "Invalid bearing")
    first, latest = meta.get("firstTimestamp"), meta.get("latestTimestamp")
    require(isinstance(first, int) and isinstance(latest, int) and first <= ts[0] < ts[-1] <= latest,
            "Primary GPS timestamps fall outside session bounds")
    for lap in laps:
        require(first <= lap["startTimestamp"] <= latest, "Lap starts outside session")
        require(lap.get("finishTimestamp", latest) <= latest, "Lap ends outside session")
    median_dt = statistics.median(dt)
    # Two nominal periods signal at least one missing update; don't bridge automatically.
    gap_limit = 1.5 * median_dt
    gaps = [{"start_ms": ts[i], "end_ms": ts[i+1], "duration_s": v}
            for i, v in enumerate(dt) if v > gap_limit]
    if gaps:
        warnings.append("Missing-update spans detected; do not interpolate through the listed gaps.")
    if median_dt >= .5:
        warnings.append("Low-rate GPS: interpolation adds no measurements and cannot resolve pedal transients or kerb impacts.")
    unknown = [c for c in inventory if not c["decoded"]]
    if unknown:
        warnings.append("Some channels/devices are inventoried but not decoded; this output is primary GPS only.")
    warnings.append("RaceChrono calculated CSV channels are not native recorded signals; they are not fabricated here.")
    checks = {
        "first_timestamp_matches": ts[0] == first,
        "last_timestamp_matches": ts[-1] == latest,
        "final_distance_matches": abs(distance[-1] - meta.get("lengthDistance", -1000)/1000) < .0001,
        "first_position_matches": decoded["position"][0] == (meta.get("firstPositionLatitude", math.inf)/6e6,
                                                            meta.get("firstPositionLongitude", math.inf)/6e6),
        "complete_lap_count_matches": sum("finishTimestamp" in l for l in laps) == meta.get("lapCount"),
    }
    if not all(checks.values()):
        warnings.append("One or more metadata cross-checks differ; review audit before using this session.")
    geometry_errors = []
    for i, (a, b) in enumerate(zip(decoded["position"], decoded["position"][1:])):
        if a[0] is not None and b[0] is not None:
            geometry_errors.append(abs(haversine_m(a, b) - (distance[i+1] - distance[i])))
    samples = []
    for i, ms in enumerate(ts):
        sample = {k: v[i] for k, v in decoded.items() if k != "position"}
        sample.update(latitude_deg=decoded["position"][i][0], longitude_deg=decoded["position"][i][1],
                      elapsed_time_s=(ms-first)/1000, lap_number=lap_number(laps, ms))
        samples.append(sample)
    lap_output = [{**lap, "lap_time_s": (lap["finishTimestamp"]-lap["startTimestamp"])/1000
                   if "finishTimestamp" in lap else None} for lap in laps]
    return {"profile": PROFILE, "metadata": meta, "fragment": fragment, "laps": lap_output,
            "samples": samples, "audit": {
                "source_name": path.name, "source_sha256": sha256(path), "primary_gps_device_id": primary,
                "sample_count": n, "median_interval_s": median_dt, "median_rate_hz": 1/median_dt,
                "maximum_interval_s": max(dt), "gap_threshold_s": gap_limit, "gaps": gaps,
                "metadata_checks": checks, "channel_provenance": provenance, "channel_inventory": inventory,
                "geometry_step_error_m": {"count": len(geometry_errors),
                    "median": statistics.median(geometry_errors) if geometry_errors else None,
                    "maximum": max(geometry_errors) if geometry_errors else None},
                "warnings": warnings,
                "scope": "Native primary GPS samples only; single root session, metadata v1, stream 1, fragment 0."
            }}


CSV_FIELDS = {
    "distance_m": ("distance_traveled", "m", False, 1e-5),
    "latitude_deg": ("latitude", "deg", True, 5.1e-8),
    "longitude_deg": ("longitude", "deg", True, 5.1e-8),
    "speed_mps": ("speed", "m/s", True, 1e-6),
    "altitude_m": ("altitude", "m", True, 1e-6),
    "bearing_deg": ("bearing", "deg", True, 1e-6),
    "accuracy_m": ("accuracy", "m", True, 1e-6),
    "fix_type": ("fix_type", "", True, 1e-6),
}


def verify_csv(decoded, path):
    """Compare original GPS ticks only, using all three CSV v3 header rows."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    require(any(r[:2] == ["Format", "3"] for r in rows[:10]), "Verification requires RaceChrono CSV Format 3")
    h = next((i for i, r in enumerate(rows[:30]) if r and r[0] == "timestamp"), None)
    require(h is not None and h+3 < len(rows), "CSV v3 channel header missing")
    names, units, sources = rows[h:h+3]
    require(len(names) == len(units) == len(sources) and units[0] == "unix time", "Invalid v3 header/unit/source rows")
    source = f"{decoded['audit']['primary_gps_device_id']}: gps"
    columns, results = {}, {}
    for key, (name, unit, gps, tolerance) in CSV_FIELDS.items():
        if key not in decoded["samples"][0]:
            continue
        hits = [i for i, n in enumerate(names) if n == name and units[i] == unit and
                (sources[i].strip() == source if gps else sources[i].strip() == "")]
        require(len(hits) == 1, f"Missing or ambiguous GPS CSV column for {key}; source/device labels matter")
        columns[key] = hits[0]
        results[key] = {"column": hits[0], "source": sources[hits[0]], "unit": unit,
                        "tolerance": tolerance, "compared": 0, "both_missing": 0,
                        "missing_mismatch": 0, "outside_tolerance": 0, "max_absolute_error": 0}
    native = {s["timestamp_ms"]: s for s in decoded["samples"]}
    seen, times = set(), []
    for row in rows[h+3:]:
        if not row or all(not v.strip() for v in row):
            continue
        require(len(row) == len(names), "Ragged CSV row")
        t = float(row[0])
        require(math.isfinite(t), "Nonfinite CSV timestamp")
        require(not times or t > times[-1], "CSV timestamps repeat or go backwards")
        times.append(t)
        ms = round(t * 1000)
        if abs(t * 1000-ms) > .001 or ms not in native:
            continue
        require(ms not in seen, "Duplicate native tick in CSV")
        seen.add(ms)
        s = native[ms]
        for key, index in columns.items():
            a = s[key]
            b = float(row[index]) if row[index].strip() else None
            require(b is None or math.isfinite(b), f"Nonfinite {key} in CSV")
            result = results[key]
            if a is None or b is None:
                result["both_missing" if a is None and b is None else "missing_mismatch"] += 1
            else:
                error = abs(a-b)
                result["compared"] += 1
                result["max_absolute_error"] = max(result["max_absolute_error"], error)
                result["outside_tolerance"] += error > result["tolerance"]
    require(len(seen) >= 2, "Too few shared native timestamps; check session identity/export scope")
    absent = sorted(set(native) - seen)
    inside = [t for t in absent if times[0]*1000 <= t <= times[-1]*1000]
    passed = not inside and all(v["outside_tolerance"] == v["missing_mismatch"] == 0 for v in results.values())
    return {"passed": passed, "native_sha256": decoded["audit"]["source_sha256"],
            "csv_sha256": sha256(path), "csv_source_name": Path(path).name,
            "csv_rows": len(times), "csv_median_interval_s": statistics.median(b-a for a,b in zip(times,times[1:])),
            "native_sample_count": len(native), "matched_native_timestamps": len(seen),
            "unmatched_native_timestamps_ms": absent, "missing_ticks_inside_csv_coverage_ms": inside,
            "channels": results,
            "method": "Exact Unix-millisecond native tick intersections; source-labelled GPS columns, no resampling. CSV coordinate tolerance follows seven-decimal-degree rounding. Scope is the overlapping exported interval."}


def write_outputs(result, output_dir):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "decoded.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    (out / "audit.json").write_text(json.dumps(result["audit"], indent=2, allow_nan=False)+"\n")
    with (out / "native_gps_samples.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(result["samples"][0]))
        writer.writeheader()
        writer.writerows(result["samples"])
    fields = ["number", "startTimestamp", "finishTimestamp", "lap_time_s", "isInvalid", "sessionResume"]
    with (out / "laps.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(result["laps"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rcz", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--verify-csv", type=Path, help="Optional official CSV v3 export of the same session")
    args = parser.parse_args()
    try:
        result = read_rcz(args.rcz)
        verification = verify_csv(result, args.verify_csv) if args.verify_csv else None
        write_outputs(result, args.out_dir)
        if verification is not None:
            (args.out_dir / "csv_verification.json").write_text(json.dumps(verification, indent=2)+"\n")
        print(json.dumps({"profile": PROFILE, "samples": len(result["samples"]),
                          "complete_laps": sum(l["lap_time_s"] is not None for l in result["laps"]),
                          "warnings": result["audit"]["warnings"],
                          "csv_verified": verification["passed"] if verification else None,
                          "output_dir": str(args.out_dir)}))
        return 0 if verification is None or verification["passed"] else 2
    except (ValueError, OSError, zipfile.BadZipFile, KeyError, TypeError, struct.error) as e:
        parser.exit(2, f"RCZ rejected: {e}\n")


if __name__ == "__main__":
    raise SystemExit(main())
