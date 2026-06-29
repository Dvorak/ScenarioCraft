"""Compatibility module alias for ASAM QC runtime adapter.

New code should import from `scenariocraft.runtime`.
"""

from __future__ import annotations

import sys

from scenariocraft.runtime import asam_qc as _asam_qc

sys.modules[__name__] = _asam_qc
