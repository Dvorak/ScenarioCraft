# Repository Layout

ScenarioCraft keeps user-facing examples, road assets, source code, and tests
separate so generated artifacts do not mix with versioned project files.

## Main Paths

```text
assets/roads/
  Road assets used by generated OpenSCENARIO/OpenDRIVE examples.

docs/
  User and contributor documentation.

examples/
  Small natural-language request files for CLI examples.

scenariocraft/
  Python package source.

tests/
  Unit and workflow tests.

outputs/
  Generated artifacts from Web and CLI runs. This directory is gitignored.
```

## Examples

`examples/` contains request text, not generated scenarios. Running the CLI with
an example writes artifacts to `outputs/`.

## Tool Caches

Optional tools such as esmini may create local caches when installed through the
setup helper. These caches are implementation details and are not required to
understand the public project layout.
