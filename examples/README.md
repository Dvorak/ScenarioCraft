# Examples

This directory contains small natural-language request files for CLI examples.

They are user input samples, not scenario templates, generated artifacts, or
external reference scenarios.

Current examples mirror the five registered golden scenario families:

```text
pedestrian_occlusion.txt
lead_vehicle_braking.txt
cut_in.txt
crossing_vehicle.txt
oncoming_turn_across_path.txt
```

The Web app keeps its controlled-case prompt variants in application metadata,
not in this directory.

For example:

```bash
.venv/bin/python -m scenariocraft.main \
  --input examples/pedestrian_occlusion.txt \
  --out outputs/demo \
  --provider mock
```

Generated outputs are written under `outputs/`, which is gitignored.
