# Tool Setup

ScenarioCraft can run without external simulators, but esmini and ASAM QC are
recommended for full local reproduction.

## Setup Helper

```bash
.venv/bin/python -m scenariocraft.tooling.setup_tools
```

The helper installs or locates optional tools and prints the exports for the
current shell.

## esmini

```bash
.venv/bin/python -m scenariocraft.tooling.install_esmini --package bin
```

Copy the `export ESMINI_BIN=...` line printed by the installer into the shell
where you run ScenarioCraft.

Verify:

```bash
"$ESMINI_BIN" --help
```

On macOS, ScenarioCraft uses visible windowed capture for visual media. Headless
capture is avoided because it produced invalid capture artifacts during local
diagnosis.

## ASAM QC

```bash
.venv/bin/python -m scenariocraft.tooling.install_asamqc
```

Copy the `export ASAM_QC_OPENSCENARIOXML_BIN=...` line printed by the installer
into the shell where you run ScenarioCraft.

Verify:

```bash
"$ASAM_QC_OPENSCENARIOXML_BIN" --help
```

If ASAM QC is unavailable, scenario generation still runs and reports QC as
unavailable.
