"""Compatibility module alias for scenario building.

New code should import from `scenariocraft.build`.
"""

from __future__ import annotations

import sys

from scenariocraft.build import scenario_builder as _scenario_builder

sys.modules[__name__] = _scenario_builder
