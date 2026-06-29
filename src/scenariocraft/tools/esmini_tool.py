"""Compatibility module alias for esmini runtime adapter.

New code should import from `scenariocraft.runtime`.
"""

from __future__ import annotations

import sys

from scenariocraft.runtime import esmini as _esmini

sys.modules[__name__] = _esmini
