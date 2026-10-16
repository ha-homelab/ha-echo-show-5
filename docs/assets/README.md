# Documentation diagrams

These SVGs are editable repository source, not screenshots or automatically updated measurements. They use native SVG shapes and text, include accessible titles/descriptions, and require no external images, fonts or scripts. English labels are the canonical diagram text; translated entry READMEs link to the same diagrams.

## Service and installation diagrams

- [Architecture](architecture.svg): device, HA, service roles and administration boundaries.
- [Voice paths](voice-paths.svg): local activation plus three selectable assistant paths, with explicit cloud processing.
- [Installation paths](installation-paths.svg): stock conversion versus existing-Android updates and recovery.

## Process and recorded results

- [Process and installed result](process-and-results.svg): the six-stage conversion journey, current APK/UI revisions, two activation phrases and localization scope.
- [Startup recovery](startup-recovery.svg): why authenticated HA startup can precede MQTT readiness, how temporary subscription failures retry, and why permission rejection stays blocked.
- [Validation counts](validation-checks.svg): 109 Node display tests, 37 Python display tests, 31 Android-builder host tests and nine JVM tests. The 48 synthetic desktop renders are separate visual checks. Counts are not coverage percentages or performance measurements.

The [process and results page](../wiki/Process-and-results.md) supplies a text equivalent for the new diagrams. The surrounding [wiki](../wiki/Home.md) provides detailed procedures; [Validation and evidence](../wiki/Validation.md) is authoritative for dated per-device acceptance. Do not infer a physical packet route, measured latency or physical wake-word recognition from a logical service arrow or an installed version.

## Editing and verification

Keep the SVG `viewBox`, accessible `<title>` and `<desc>`, `role="img"` and `aria-labelledby` references valid. Explain differences using text and structure as well as color. Use explicit line breaks, adequate contrast and native shapes; avoid scripts, external resources and embedded HTML.

After editing, render every affected SVG in a browser and inspect the complete image for clipping, overlap and legibility. Run the offline link and SVG-structure check from the repository root:

```bash
python3 scripts/check_docs.py
```

The check does not replace visual inspection or verify external links. Store rendered review images privately; the public assets remain editable SVG source. Keep explanatory prose and versioned evidence consistent when implementation or deployment changes.
