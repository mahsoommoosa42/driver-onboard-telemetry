---
name: analyze-driver-onboards
description: Analyze motorsport driver onboard videos and race telemetry, compare drivers or laps, synchronize footage, measure physical-position lap deltas, generate comparison videos, and turn findings into testable driving improvements. Use for track or simulator lap analysis, MoTeC i2 CSV, RaceChrono RCZ and CSV exports, corner-by-corner comparisons, and race pace or stint analysis. Do not confuse onboards with boats or apply competitive driving coaching to public roads.
---

# Driver Onboards and Race Telemetry

## Establish evidence
- Check available project notes for the relevant track/session/project, prior corrections, and open practice goals. Treat historical claims as dated, not current measurements. Read references/prior-lessons.md when continuing prior comparisons.
- Inventory actual accessible files before claiming analysis: driver labels, source video, session/lap identity, car/setup, track/layout, conditions, tyres, timing source, available channels and units. Ask only for missing facts that block valid conclusions.
- Support video-only, telemetry-only and combined inputs. Do not require a logger when landmarks suffice for approximate timing.
- Inspect timestamps, frame presentation times, variable frame rate, cuts, playback speed, missing data, logger sample rate, channel meaning, distance resets and duplicate samples. Preserve raw inputs; document transformations.
- Treat export formats and software APIs as unknown until inspected. Verify current official documentation when implementing adapters. Never claim to have watched inaccessible footage.

## MoTeC and RaceChrono
Read references/telemetry-formats.md before ingesting these formats. Use scripts/telemetry.py to inspect CSV records, normalize explicitly mapped channels and units, and compute deltas only after validating common physical positions. Inspect every warning before interpreting results.
For RaceChrono .rcz, use scripts/racechrono_rcz.py and read references/racechrono-rcz.md. It decodes the verified single-fragment native GPS profile directly, preserving original cadence and lap boundaries. Do not request CSV for an already supported RCZ. When an official CSV v3 is also supplied, cross-check it with --verify-csv; preserve the source/device header row so GPS and calculated speed are not confused. Inspect all audit warnings. Unsupported backup/resume/encoding profiles need a separately verified adapter or CSV fallback. Native MoTeC .ld/.ldx decoding remains unimplemented. Never claim mock-data tests establish vendor-native compatibility.
Use scripts/generate_mock_data.py to reproduce the four synthetic fixtures under assets/mock-data. They include known segment deltas at different export rates. Label all test results SYNTHETIC; do not turn their invented control signals into real driving advice.

## Synchronize before interpreting
1. Identify the same physical start/finish crossing for each lap. Distinguish current-lap elapsed timer from completed lap time, session clock and live delta.
2. Estimate video-to-lap time offsets from several independent observations, including early, middle and late lap. For a true elapsed timer, offset = source video timestamp minus displayed lap elapsed time.
3. Cross-check timer alignment against physical landmarks and telemetry. Quantify disagreement and display latency. Do not silently choose one conflicting clock.
4. Check end-of-lap duration and drift. Use a documented clock mapping only when evidence supports it; investigate cuts and discontinuities separately.
5. Record an alignment table with source, lap, anchor, video timestamp, lap timestamp, offset and uncertainty. Recompute all derived results after a correction and explicitly withdraw superseded findings.

## Compare physical positions
- Define reference and comparison driver. Use delta = comparison elapsed time minus reference elapsed time at the SAME physical track position; positive means comparison is behind.
- Use matched landmarks or validated common-track distance. Independent cumulative path distances are not automatically equivalent when racing lines differ. Check GPS/map matching around adjacent track sections and start/finish.
- Never equate equal elapsed time, normalized lap percentage, or proportional lap-time interpolation with equal physical position.
- For landmarks k, compute cumulative delta[k] = t_comparison[k] - t_reference[k]. Segment loss[k] = delta[k] - delta[k-1]. Verify segment sum equals finish delta minus start delta.
- Preserve anchor observations, interpolation method and uncertainty. Interpolate only inside valid coverage, never across cuts, missing sections or unmatched laps.
- Use video-only landmarks for approximate segment timing when clearly visible. Do not invent exact corner allocations from whole-lap gaps or another driver's own-reference delta overlay.
- Match precision to evidence. Low-rate GPS cannot resolve fine pedal transients; high-rate interpolation does not create measurements. Report uncertain small differences as unresolved.
- Distinguish completed lap, recorded best and theoretical best. Label theoretical sectors and account for incompatible conditions; never imply an optimal lap was actually driven.

## Interpret driving and race context
- Inspect entry, rotation/apex and exit as one linked sequence. Tie observations to source timestamps or distance, measured delta and confidence.
- Separate observed input, measured vehicle response, user report and causal hypothesis. Do not infer brake pressure, throttle position, steering angle or grip limit solely from speed, sound or a single view.
- Distinguish the initiating event from recovery and downstream loss. Evaluate corrections for timing and proportionality; do not praise dramatic saves by default.
- Account for car, setup, power, tyre, fuel, traffic, tow, flags, weather and familiarity before attributing differences to driver technique. Mark unknown confounders.
- For race/stint work, validate event/session identity and lap completeness; document clean-lap rules and exclusions, compare appropriate tyre ages and race laps, and show traffic/pit/neutralization context. Do not invent fuel corrections or fill missing laps as measured pace.
- Give at most three ranked improvements: evidence, likely mechanism, one safe track/simulator drill, measurable success criterion, and the channel or observation needed to confirm it. Avoid unsupported exact braking markers or setup prescriptions.

## Deliver
Lead with the strongest supported result and material uncertainty. Scale detail to the request:
- Input and synchronization summary.
- Corner/segment table: location, both elapsed times, segment gain/loss, observed difference, confidence, next test.
- Distance-aligned speed/delta and available input plots; label units, sign convention, reference and gaps.
- Requested comparison video: default to start-line synchronized, real-time side by side so true time gaps remain visible. Label driver/lap and clocks. If position-synchronized or slowed footage is useful, label time warping explicitly; never use it as evidence of real-time lead.
- Prefer Driver 1 left audio / comparison right audio for comparisons when both sources have audio; label channels. Handle missing audio explicitly. Inspect start/mid/end frames, duration and audible channels before delivery.
- Save requested artifacts through the available file persistence workflow. Include an audit table and reproducible analysis code for substantial quantitative work.
- Save meaningful findings, corrections and practice criteria in the relevant project notes. Keep measured facts separate from hypotheses and proposed goals. Never claim persistence succeeded without a successful write.

## Completion standard
Do not call an analysis validated unless source identities and alignment were checked, deltas reconcile within documented tolerance, causal claims fit available evidence, and output files were inspected. If raw material is absent, provide a scoped workflow and request a representative onboard/export; explicitly state that real-data validation remains pending.
