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

Private telemetry, onboard videos and personal project notes are not included.

## License

Copyright 2026 Moosa Mahsoom. Contributors retain copyright in their respective contributions.

Unless a file states otherwise, this repository's skill instructions, Python utilities, documentation, tests and synthetic fixtures are licensed under the [Apache License, Version 2.0](LICENSE) (`Apache-2.0`).

You may use, modify and redistribute the project, including in commercial or closed-source products and plugins, subject to that license. You do not have to publish your modifications or contribute them back.

When redistributing the project or a derived skill/plugin, include a copy of `LICENSE`, prominently identify changed files, and retain applicable copyright, patent, trademark and attribution notices in distributed source. If a distribution includes a `NOTICE` file, preserve its applicable attribution notices as required by the license. When packaging only `skills/analyze-driver-onboards`, copy the root `LICENSE` and this copyright/licensing notice into the package.

The license includes a limited contributor patent grant and a patent-litigation termination clause; it does not protect against claims from non-contributing patent holders or license vendor software. It grants no trademark rights beyond the limited attribution uses stated in the license. The software is provided without warranties, as specified in `LICENSE`. This summary does not replace the license terms.

The license covers the repository contents, not private telemetry or onboard recordings processed with the tools. Bundled synthetic fixtures are independently generated examples, not vendor-provided datasets.

## Contributing

Bug reports, documentation improvements, parser fixes and tests are welcome. Fork the repository, make a focused change and open a pull request explaining the problem, the resulting behavior and how you validated it. Run the test command in [Use](#use) for code changes and add regression coverage when fixing parser or analysis behavior.

Unless explicitly stated otherwise, contributions intentionally submitted for inclusion are offered under Apache-2.0, as described in section 5 of `LICENSE`. Submit only material you have the right to contribute; identify third-party material and preserve its original license and attribution. Contributions do not transfer copyright ownership to the maintainer.

Prefer minimal synthetic fixtures for reproducible bugs. Label synthetic data clearly, document units and format assumptions, and report compatibility limits. Do not include private telemetry, onboard footage or personal information without the necessary permission.
