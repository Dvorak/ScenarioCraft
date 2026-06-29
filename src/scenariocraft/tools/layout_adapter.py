"""Compatibility module alias for layout adaptation.

New code should import from `scenariocraft.build`.
"""

from __future__ import annotations

import sys

from scenariocraft.build import layout_adapter as _layout_adapter

sys.modules[__name__] = _layout_adapter
