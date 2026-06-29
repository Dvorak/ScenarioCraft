"""Compatibility module alias for 2D preview rendering.

New code should import from `scenariocraft.presentation`.
"""

from __future__ import annotations

import sys

from scenariocraft.presentation import preview_2d as _preview_2d

sys.modules[__name__] = _preview_2d
