# Native RaceChrono GPS reader

## Use

Run from this skill directory (Python 3 standard library only):

```bash
python scripts/racechrono_rcz.py session.rcz --out-dir analysis/native
python scripts/racechrono_rcz.py session.rcz --out-dir analysis/native --verify-csv session_v3.csv
python -m unittest discover -s scripts -p test_racechrono_rcz.py -v
```

Outputs: decoded.json (metadata, laps, samples and audit), native_gps_samples.csv, laps.csv, audit.json, and optional csv_verification.json. The original archive is read only. Output directories are reproducible intermediate analysis; persist requested deliverables through the normal file workflow. A failed CSV verification returns exit status 2 and records discrepancies. A successful decode alone is not validation of driving claims or track alignment.

## Verified support boundary

This independently written reader supports a root single-session ZIP containing session.json and sessionfragment.json, both metadata version 1; channel filenames channel_1_DEVICE_0_ID_ENCODING; and a primary GPS device declared as type 1 in fragment metadata. Device 100 is not assumed: the ID comes from primaryGpsDeviceIndex. It preserves native sample timestamps and does not resample. It retains original complete/incomplete lap bounds, invalid flags and resume metadata. isInvalid=false is not evidence that a lap was clear of traffic or officially valid.

Primary GPS channels decoded:

| ID | Meaning | Stored encoding | Decode |
|---|---|---|---|
| 1 | Unix timestamp | signed int64 little endian | milliseconds; keep integer precision |
| 2 | Session cumulative path distance | signed int64 little endian | /1000 metres |
| 3 | Latitude, longitude | consecutive signed int32 pair, encoding suffix 1 | each /6,000,000 degrees |
| 4 | GPS speed | signed int32 little endian | /1000 m/s |
| 5 | Altitude | signed int32 little endian | /1000 metres |
| 6 | Bearing | signed int32 little endian | /1000 degrees |
| 30003 | GPS fix type | signed int32 little endian | raw enum, not a scale |
| 30007 | Reported GPS accuracy | signed int32 little endian | /1000 metres |

INT32_MAX (2147483647) is missing data, never a real measurement or a zero. A partially missing coordinate pair is entirely missing. Optional absent channels stay absent. Unknown channel IDs and non-primary devices are inventoried and explicitly marked not decoded: do not guess their physical meaning or units. Timestamp, distance, position and speed are required by this profile.

Reject incompatible metadata/encodings, resumed/multi-fragment sessions, nested backups, unknown stream prefixes, duplicate members/channels, unequal array lengths, non-increasing timestamps, distance resets, malformed arrays and unsafe/oversized archives. Do not widen these gates just to accept a new file; inspect the new profile and verify it against an official export before expanding support. No archive members are extracted to disk.

Native controls/ECU/IMU streams, float64 channels and RaceChrono calculated signals are not yet decoded. In particular, do not manufacture throttle, brake pressure, gear, steering, lean angle or G channels from GPS. CSV calculated channels may be analyzed with their actual labels but are not equivalent to recorded sensors.

## Audit and interpretation

- Use firstTimestamp for session elapsed time, not timeCreated (app/session creation may precede GPS recording).
- Audit includes source SHA-256, channel IDs/encodings/scales, native interval distribution summary, metadata agreement and missing-update intervals. A span over 1.5 times median native interval is flagged; do not automatically interpolate through it.
- Geometry cross-check compares consecutive decoded coordinates' haversine distance with native cumulative-distance increments. Close agreement validates decoding consistency, not absolute position accuracy, racing line fidelity or timing precision.
- Cumulative path distance is not a common coordinate across different laps. Define shared physical gates/landmarks or validate a common track projection before comparing. Never stretch laps to the same length or assign corners by normalized elapsed time.
- No official corner numbering/layout is present in a trackId-only archive. Obtain a verified map or use explicitly provisional named map regions. Do not silently equate detected speed minima with C1/C2/etc.
- At roughly 1 Hz, short-corner minima, braking onset and kerb impacts are poorly resolved. Linear interpolation may estimate gate crossings but does not add temporal resolution. Carry source spans/position uncertainty into segment comparisons; combine adjacent corners if necessary. Gate-shift sensitivity alone is not an absolute GPS-error bound.

## Cross-check with RaceChrono CSV v3

Read all three header rows: channel name, unit, source/device. Select DEVICE: gps speed, not the identically named calc speed. Compare original native Unix-millisecond timestamps present in the CSV; do not treat intervening interpolated export rows as independent observations. Verify missing values too. Require matching units, device and timestamp ordering.

The helper records all absent native ticks and fails missing ticks inside CSV coverage. An export may omit the first native tick or cover only a chosen interval; verification applies only to the overlapping interval. Require adequate coverage before claiming session-wide agreement. Coordinate tolerance is 5.1e-8 degrees because the tested CSV rounds to seven decimal places. Other channels use explicit small absolute tolerances, not broad percentage fitting.

## Validation and sources

Validated 21 October 2026 on two actual single-fragment GPS sessions: 1,665 and 2,177 native samples; all first/last timestamp, first-position, final-distance and completed-lap-count checks agreed. Native cadence was approximately 1 Hz. One 3-second GPS gap occurred in the first session and was flagged. Distance-step geometry differed by less than 1 mm; this is an internal consistency check only.

The second session was cross-checked against its RaceChrono Pro v10.2.4 CSV Format 3 export: 45,682 CSV rows, 2,176 shared native ticks (only the first native tick precedes export coverage). Speed, path distance, altitude, bearing, accuracy and fix type agreed exactly at every shared nonmissing tick; all 322 missing bearing values agreed. Latitude/longitude differed by at most 3.34e-8 degrees, consistent with CSV rounding. Its 20 Hz export cadence did not change its approximately 1 Hz native GPS rate. The first session has structural/geometry validation but no independent CSV cross-check. Private user inputs are not bundled with the skill.

Synthetic regression tests cover signed coordinates, non-100 GPS IDs, missing values, duplicate column names/source selection, clock origin, incomplete laps, incorrect values, mismatched/truncated arrays, timestamp/distance discontinuities, unsupported streams/encodings/resumes, unknown channel inventory and ZIP handling. These tests do not establish other native profiles' compatibility.

Research references (not a universal official RCZ specification):
- RaceChrono developer's channel ID list: https://racechrono.com/forum/d/2659-2659
- RaceChrono developer's monitor protocol includes signed degree-times-6,000,000 coordinates and invalid sentinel: https://github.com/aollin/racechrono-ble-diy-device
- Independent format research, inspected at commit 75d61d48e4b2bea99a9e85aba5975229a205d4c7: https://github.com/timliudev/track-log-studio/blob/75d61d48e4b2bea99a9e85aba5975229a205d4c7/docs/specs/RCZ-FORMAT-SPEC.md — corroborated device/source handling and storage scales; implementation written independently and confirmed against the user's official CSV.
- RaceChrono identifies RCZ as internal storage rather than a stable public specification: https://racechrono.com/forum/d/1522-1522

Expand compatibility only with new evidence and tests; retain these narrow claims until other real profiles are validated.
