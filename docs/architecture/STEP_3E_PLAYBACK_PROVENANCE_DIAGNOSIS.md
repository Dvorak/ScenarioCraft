# Step 3E-2 Playback Provenance Diagnosis

## Scope

This diagnosis covers the current playback media provenance for:

- `outputs/web_demo/20260618_160524/playback.gif`
- `outputs/web_demo/20260618_160524/frames/frame_000001.png`
- `outputs/web_demo/20260618_160524/screen_shot_*.tga`

No production code or tests were changed for this diagnosis.

## Findings

### 1. Exact code path that creates `playback.gif`

The Web path is:

1. `src/scenariocraft/web/app.py`
   - `_generate_and_play(...)`
   - `_run_pipeline(...)`
   - `_build_xml(...)`
   - `_generate_preview(...)`, which writes `preview_2d.png`
   - `_run_playback(...)`
2. `src/scenariocraft/tools/esmini_tool.py`
   - `run_esmini_playback(...)`
   - `_run_esmini_capture(...)`, which runs esmini with `--capture_screen`
   - `_collect_capture_frames(output_dir, output_dir / "frames")`
   - `_encode_playback(frames, output_dir)`
   - `_encode_mp4_with_ffmpeg(...)`, then `_encode_gif_with_pillow(...)` if MP4 is not produced

The command recorded in `esmini_playback_result.json` was:

```text
/Users/zhang/ScenarioCraft-Agent/third_party/esmini/v3.3.0/extracted/esmini/bin/esmini --osc scenario.xosc --path /Users/zhang/ScenarioCraft-Agent/outputs/web_demo/20260618_160524 --headless --capture_screen --camera_mode top --fixed_timestep 0.05 --window 0 0 960 540 --log_level info --logfile_path esmini_capture_log.txt
```

### 2. Exact source artifact used for every GIF frame

`playback.gif` has exactly one GIF frame.

That single GIF frame came from:

```text
outputs/web_demo/20260618_160524/frames/frame_000001.png
```

`frames/frame_000001.png` is byte-identical to:

```text
outputs/web_demo/20260618_160524/preview_2d.png
```

Observed artifact facts:

```text
preview_2d.png             PNG 977x604 sha256 deda31ed2427c51cbbb2d5f9a784f84d0f964de4efa99534e728f68fcdd01103
frames/frame_000001.png    PNG 977x604 sha256 deda31ed2427c51cbbb2d5f9a784f84d0f964de4efa99534e728f68fcdd01103
playback.gif               GIF 977x604 frames=1
screen_shot_00000.tga      TGA 960x540
screen_shot_00162.tga      TGA 960x540
```

Therefore the GIF is a static preview-derived GIF, not an esmini-rendered animation.

### 3. Whether `frames/frame_000001.png` is produced by esmini or ScenarioCraft

`frames/frame_000001.png` is produced by ScenarioCraft's frame collection step, not by esmini.

The current collector only accepts:

```python
CAPTURE_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
```

It then scans the output directory for matching images and moves them into `frames/frame_%06d<suffix>`.

In this output directory, the esmini screenshots are `screen_shot_*.tga`, so they are ignored. The recognized image in the output root is `preview_2d.png`, so it is treated as the sole capture candidate and normalized to `frames/frame_000001.png`.

The later presence of both `preview_2d.png` and `frames/frame_000001.png` is consistent with the Web preview path regenerating `preview_2d.png` after the original preview image was moved, or with a later UI render ensuring the preview exists. The byte-identical hashes confirm that the frame is preview-derived.

### 4. Number of actual captured esmini frames

There are 163 actual esmini screenshot files:

```text
screen_shot_00000.tga
...
screen_shot_00162.tga
```

These are TGA files in the output root. They were not collected into `frames/` and were not encoded into `playback.gif`.

### 5. Whether the current esmini version / invocation supports multi-frame capture

Yes, in this environment esmini supports and produced multi-frame capture.

Evidence:

- `esmini_playback_result.json` records esmini `v3.3.0`.
- `esmini_capture_log.txt` contains `Activate continuous screen capture`.
- The output directory contains 163 `screen_shot_*.tga` files.

The current ScenarioCraft collector does not consume those frames because it ignores `.tga`.

### 6. Whether the current command line is sufficient for recording, or only captures a screenshot

The current command line is sufficient to produce a frame sequence in this environment. It is not merely taking a single screenshot.

However, the current command line plus current ScenarioCraft collector/encoder is not sufficient to produce an esmini-derived GIF or video, because the collector ignores esmini's TGA screenshot sequence.

The current implementation captures screenshots, not a native esmini video file. ScenarioCraft is responsible for collecting and encoding those screenshots.

### 7. Whether the GIF fallback behavior is intentional, accidental, or undocumented

The observed fallback is accidental and undocumented.

The intended behavior appears to be:

- run esmini with `--capture_screen`;
- collect captured frame images;
- encode MP4 if possible;
- otherwise encode GIF.

The observed behavior is:

- esmini captures 163 `.tga` frames;
- ScenarioCraft ignores all `.tga` frames;
- ScenarioCraft scans the broad output directory for `.png` or `.jpg`;
- `preview_2d.png` is accepted as if it were a capture frame;
- a one-frame GIF is produced from the 2D preview;
- `playback_generated` is set to `true`;
- `fallback_reason` is set to `null`.

This is not an intentional preview fallback. It is an artifact-provenance bug.

### 8. Why a single-frame GIF was presented as playback

The Web UI presents any `EsminiPlaybackResult` with:

```text
playback_generated == true
playback_path exists
```

as media under the `esmini Playback` tab.

Because `_encode_gif_with_pillow(...)` successfully encoded the one preview-derived PNG, `run_esmini_playback(...)` returned:

```json
{
  "playback_generated": true,
  "playback_path": "outputs/web_demo/20260618_160524/playback.gif",
  "fallback_reason": null
}
```

The UI has no media provenance field and no animation/frame-count check, so the static preview-derived GIF was displayed as esmini playback.

## Classification of Current Behavior

- A. Creates `playback.gif` from `preview_2d.png`: yes, for this artifact.
- B. Creates `playback.gif` from an esmini screenshot: no.
- C. Creates `playback.gif` from multiple esmini frames: no.
- D. Falls back to a static image when esmini capture is unavailable: not intentionally; the observed static result is accidental.
- E. Has a bug that drops all but one captured esmini frame: partially. The actual bug is broader: it ignores all captured `.tga` esmini frames and accidentally collects the preview PNG as the only frame.

## Runtime Motion Cross-Reference

The log shows the pedestrian event is initialized but does not start running:

```text
[0.000] pedestrian_starts_crossing initState -> initToStandbyTransition -> standbyState
[8.050] pedestrian_starts_crossing standbyState -> stopTransition -> completeState
```

There is no `pedestrian_starts_crossing ... -> runningState` transition in the captured log.

The esmini capture does contain visual media, but the checked first and last TGA files have the same hash in this run. Combined with the event log, this gives no visual evidence of pedestrian motion. The single preview-derived GIF also cannot verify runtime motion because it is not esmini-rendered and contains only one frame.

This confirms the existing Step 3E runtime issue should remain separate from media provenance: the trigger/event behavior still needs diagnosis or repair, but that fix is out of scope for Step 3E-2.

## Minimal Implementation Plan for Reliable Media Provenance

Add explicit media provenance to the playback result shape:

```yaml
playback_generated: bool
playback_kind:
  - esmini_gif
  - esmini_frame_sequence
  - esmini_single_frame
  - preview_fallback_gif
  - preview_static_image
  - unavailable
playback_source_path: str | None
playback_frame_count: int
playback_is_animated: bool
playback_fallback_reason: str | None
```

Recommended implementation steps:

1. Collect esmini capture output from a dedicated capture directory or from explicit esmini screenshot filename patterns, not by scanning the whole artifact root.
2. Exclude known ScenarioCraft artifacts such as `preview_2d.png`, `playback.gif`, `playback.mp4`, reports, specs, and logs from capture collection.
3. Support esmini's observed `.tga` screenshot output, either by adding `.tga` to accepted capture suffixes or by converting TGA frames to PNG before encoding.
4. Store the original capture source paths and normalized frame paths in result metadata.
5. Classify media by source and count:
   - multiple esmini frames encoded as GIF: `esmini_gif`;
   - multiple esmini frames retained without encoding: `esmini_frame_sequence`;
   - one esmini frame: `esmini_single_frame`;
   - preview-derived GIF: `preview_fallback_gif`;
   - preview image only: `preview_static_image`;
   - nothing usable: `unavailable`.
6. Require `playback_frame_count > 1` before claiming animated playback.
7. Update Web UI and reports to render labels from `playback_kind`, not from `playback_generated`.
8. Never label preview-derived media as `esmini playback`, `esmini video`, or `esmini rendered GIF`.

Accurate UI/report labels should be limited to:

- `2D Preview`
- `2D Preview Fallback`
- `esmini Screenshot`
- `esmini Frame Sequence`
- `esmini Rendered GIF`
- `esmini Playback Unavailable`

Focused tests to add during implementation:

- esmini TGA frame sequence is collected and encoded/classified.
- `preview_2d.png` is never collected as an esmini capture frame.
- one esmini frame is classified as `esmini_single_frame` and not animated playback.
- multiple esmini frames set `playback_is_animated = true`.
- preview fallback sets `playback_kind` to `preview_fallback_gif` or `preview_static_image` with a non-null fallback reason.
- Web/report labels use the provenance fields and do not call preview-derived media esmini playback.

## Bottom Line

The current output directory contains real esmini capture artifacts, but the published `playback.gif` is not made from them. It is a one-frame GIF sourced from the ScenarioCraft 2D preview. The current UI/report metadata cannot distinguish this, so it presents the static preview-derived GIF as playback.
