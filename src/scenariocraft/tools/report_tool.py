"""Compatibility module alias for validation report rendering.

New code should import from `scenariocraft.presentation`.
"""

from __future__ import annotations

import sys

from scenariocraft.presentation import report as _report

sys.modules[__name__] = _report
