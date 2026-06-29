"""Compatibility module alias for timing metrics.

New code should import from `scenariocraft.metrics`.
"""

from __future__ import annotations

import sys

from scenariocraft.metrics import timing as _timing

sys.modules[__name__] = _timing
