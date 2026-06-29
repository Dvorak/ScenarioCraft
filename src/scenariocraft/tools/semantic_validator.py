"""Compatibility module alias for semantic validation.

New code should import from `scenariocraft.validation`.
"""

from __future__ import annotations

import sys

from scenariocraft.validation import semantic as _semantic

sys.modules[__name__] = _semantic
