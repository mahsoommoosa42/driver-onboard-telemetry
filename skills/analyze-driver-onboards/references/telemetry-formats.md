# MoTeC and RaceChrono ingestion

## Support boundary
- Use the bundled Python 3 standard-library helper for explicitly mapped, numeric CSV exports from MoTeC i2 and RaceChrono. Inspect each export first; the helper checks supplied source names and units against the file.
- Treat bundled fixtures as synthetic export-shaped examples. They were NOT exported by i2 or RaceChrono and do not certify a vendor CSV revision.
- For MoTeC .ld/.ldx, request a CSV export through the user's installed i2. Do not rename the file or claim native binary decoding. The .ldx companion is not a substitute for signal data.
- For RaceChrono .rcz, use scripts/racechrono_rcz.py for the verified single-fragment GPS profile. Read references/racechrono-rcz.md for exact support, audit fields, real-data validation and CSV cross-checking. Native backups, resumed/multi-fragment sessions, other channel encodings, VBO, NMEA, GPX and older/locale-specific layouts require a separately verified adapter or CSV fallback. The CSV helper itself remains separate from the native reader.
- Prefer RaceChrono CSV v3 when available. Preserve all channel-description rows; inspect the actual header, units, source/device rows and delimiter.
- Obtain one contiguous lap and independently verify start/finish source timestamps. For session-wide exports, run a separate mapping with bounds for each lap. Do not equate a metadata count or the first/last record with a complete lap.
- If the exporter cannot provide units or an unambiguous time channel, stop normalization and resolve those facts.

## Commands
Run from this skill directory:
```bash
python scripts/telemetry.py inspect input.csv
python scripts/telemetry.py normalize input.csv --mapping mapping.json --out lap.json
python scripts/telemetry.py compare reference.json comparison.json --positions 0,500,1000,1500,2000 --alignment-evidence "Describe the actual shared-position verification" --out delta.json
```

The example positions are synthetic; replace them with validated track coordinates.

Create mapping JSON after inspecting the input. All row/column indexes are zero-based CSV record indexes. Use a separate mapping per input; examples live in assets/mock-data:
```json
{
  "format": "motec-i2-csv",
  "scope": "one-contiguous-lap",
  "source_time_bounds_s": [0, 100],
  "header_row": 4,
  "units_row": 5,
  "data_row": 6,
  "channels": {
    "time_s": {"column": 0, "name": "Time", "unit": "s"},
    "distance_m": {"column": 1, "name": "Distance", "unit": "m"},
    "speed_mps": {"column": 2, "name": "Ground Speed", "unit": "km/h"}
  }
}
```

Use format racechrono-csv for RaceChrono. Exact names and indexes vary. synthetic must be true only for generated test data. Optional delimiter defaults to comma; decimal-comma numbers are unsupported until explicitly converted with an audit trail. Optional max_gap_s sets a documented maximum permitted interpolation span; default is three times median export interval. Do not enlarge it simply to hide gaps.

## Channel semantics
- Choose elapsed/session time deliberately; Unix timestamps are allowed with explicit seconds bounds. Do not select lap time that resets within the chosen interval.
- Map GPS speed, wheel speed and estimated ground speed deliberately; record the source and do not silently substitute one for another.
- Keep brake pressure (bar/kPa/psi), brake position (%/fraction), and brake on/off distinct. Never map binary brake activity into a pressure channel.
- Keep accelerator pedal, requested throttle and actual throttle opening distinct in the audit explanation. Map only the selected meaningful channel; preserve the original export for other signals.
- Leave absent/blank/NaN non-time values missing. Infinity and missing timestamps fail. Do not fill gaps with zeros.
- Inspect custom channels before renaming. Do not infer units from value ranges. Add new canonical channels with documented meaning and tests as needed.

## Quality gates
Inspect warnings in normalized JSON before drawing conclusions. The helper records original channel names, units, source SHA-256, export cadence, missing-channel limitations and time gaps. Normalization does not itself certify lap validity or physical alignment.
Comparison requires strictly increasing, complete distance and caller-supplied evidence of a shared physical coordinate. It rejects extrapolation and intervals containing detected time gaps. No path-length scaling or GPS map matching is performed.
Finite export cadence does not establish native sensor cadence. RaceChrono exports can include resampled GPS and asynchronous OBD channels; i2 exports can also resample. Measure and record the original channel rate when available.
Synthetic pressure, throttle and speed are test signals, not a vehicle model. Do not infer driving advice or physically consistent braking dynamics from these fixtures.

## Sources and evidence level
Checked 21 October 2026:
- MoTeC official i2 product page: https://www.motec.com.au/products/I2 — documents CSV export capability. The retrieved official search excerpt did not establish a complete CSV schema.
- RaceChrono official iOS change log: https://racechrono.com/article/2025 — records CSV v3 with expanded column headers and historical fixes involving timestamps, duplicate elapsed-time/distance columns and export scope.
These sources establish export workflows, not fixture conformance. Validate an actual exported sample before promoting compatibility beyond the tested explicit mappings.
