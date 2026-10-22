# Race Telemetry

A reusable agent skill for evidence-led driver onboard and race telemetry analysis.

## Contents

- `skills/analyze-driver-onboards/SKILL.md`: analysis workflow and reporting rules.
- `scripts/telemetry.py`: CSV inspection, explicit channel/unit mapping and physical-position delta calculations.
- `scripts/racechrono_rcz.py`: native RaceChrono single-fragment GPS reader.
- `assets/mock-data`: clearly labelled synthetic MoTeC-shaped and RaceChrono-shaped CSV fixtures.

Script and asset paths above are relative to `skills/analyze-driver-onboards`.

## Use

Copy `skills/analyze-driver-onboards` into your agent’s skill directory, or read its SKILL.md and run the standalone Python utilities. Python 3 is required. Read the format reference before processing a new export.

```sh
cd skills/analyze-driver-onboards
python scripts/telemetry.py --help
python scripts/racechrono_rcz.py session.rcz --out-dir analysis/native
python -m unittest discover -s scripts -p 'test_*.py' -v
```

## Supported scope and limits

CSV channels require explicit mapping and unit validation. Native RCZ decoding supports the verified single-session, single-fragment GPS profile described in `references/racechrono-rcz.md`; unsupported profiles are rejected. Native MoTeC `.ld/.ldx` parsing is not implemented. Synthetic fixtures do not establish vendor compatibility.

Video synchronization and interpretation are agent-guided workflows, not an automatic video-analysis service. Low-rate GPS cannot establish precise pedal inputs or racing lines. Compare common physical landmarks and report uncertainty.

Private telemetry, onboard videos and personal project notes are not included. No open-source license has yet been selected.
