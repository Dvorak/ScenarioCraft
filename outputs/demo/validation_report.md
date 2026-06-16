# scenarioCraft Validation Report

## Input Scenario Intent

A rainy urban pedestrian occlusion scenario where the ego vehicle approaches a parked van and a pedestrian suddenly crosses from behind it.


## Generated ScenarioSpec

- Scenario name: `rainy_pedestrian_occlusion`
- Scenario type: `pedestrian_occlusion`
- Road: `urban_straight`, 1 lane(s) per direction, 50 kph speed limit
- Weather: rain=`True`, road condition=`wet`
- Actors: `ego`/ego, `parked_van`/occluder, `pedestrian`/crossing_actor
- Trigger: `relative_distance` from `ego` to `parked_van` at 18 m
- Intended criticality: `near_miss`, target min TTC 1.5 s

## Generated Artifacts

- `scenario_spec.json`
- `scenario.xosc`
- `qc_config.xml`
- `qc_report.json`
- `qc_result.xqar`, if ASAM QC runs
- `esmini_log.txt`
- `validation_report.md`

## ASAM Quality Check

- Command: `qc_openscenario -c outputs/demo/qc_config.xml`
- Config path: `outputs/demo/qc_config.xml`
- Result path: `outputs/demo/qc_result.xqar`
- Return code: `0`
- Passed: `True`

stderr:
```text
2026-06-15 21:16:25,017 - Initializing checks
2026-06-15 21:16:25,020 - Executing valid_xml_document check
2026-06-15 21:16:25,020 - - It is an xml document.
2026-06-15 21:16:25,021 - Executing root_tag_is_openscenario check
2026-06-15 21:16:25,021 - - Root tag is 'OpenSCENARIO'
2026-06-15 21:16:25,021 - Executing fileheader_is_present check
2026-06-15 21:16:25,022 - - Root tag contains FileHeader -> OK
2026-06-15 21:16:25,022 - Executing version_is_defined check
2026-06-15 21:16:25,022 - Executing valid_schema check
2026-06-15 21:16:25,028 - - XML is valid.
2026-06-15 21:16:25,029 - Executing uniquely_resolvable_entity_references check
2026-06-15 21:16:25,030 - Executing resolvable_signal_id_in_traffic_signal_state_action check
2026-06-15 21:16:25,030 - Executing resolvable_traffic_signal_controller_by_traffic_signal_controller_ref check
2026-06-15 21:16:25,030 - Executing valid_actor_reference_in_private_actions check
2026-06-15 21:16:25,031 - Executing resolvable_entity_references check
2026-06-15 21:16:25,031 - Executing resolvable_variable_reference check
2026-06-15 21:16:25,031 - Executing resolvable_storyboard_element_reference check
2026-06-15 21:16:25,031 - Executing unique_element_names_on_same_level check
2026-06-15 21:16:25,032 - Executing valid_parameter_declaration_in_catalogs check
2026-06-15 21:16:25,032 - Executing allowed_operators check
2026-06-15 21:16:25,032 - Executing non_negative_transition_time_in_light_state_action check
2026-06-15 21:16:25,033 - Executing positive_duration_in_phase check
2026-06-15 21:16:25,034 - Done
```

## esmini Execution / Playback

esmini was not found. Scenario playback/execution check was skipped.

## Semantic Validation

Overall result: `passed`

- [x] `ego_vehicle_exists`: Ego vehicle is defined.
- [x] `occluding_vehicle_exists`: Occluding vehicle is defined.
- [x] `pedestrian_exists`: Pedestrian crossing actor is defined.
- [x] `rainy_wet_weather`: Rainy wet weather is defined.
- [x] `trigger_defined`: Trigger condition is defined.
- [x] `ego_speed_plausible`: Ego speed is plausible for the road speed limit.
- [x] `pedestrian_speed_plausible`: Pedestrian speed is plausible.
- [x] `intended_criticality_defined`: Intended criticality is defined.
- [x] `trigger_actor_references_exist`: Trigger source and target actors exist.

## Known Limitations

- The OpenSCENARIO XML builder used `scenariogeneration`.
- No CARLA, CAMEL, Streamlit, OpenAI provider, local LLM provider, Docker setup, or repair loop is included in this version.
- External ASAM QC and esmini checks are optional and may be skipped when the tools are unavailable.

## Repair Suggestions

- No automated repair loop is implemented in this version.
