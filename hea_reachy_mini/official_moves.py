"""Motion-enabled cue mappings from the bundled reviewed expression catalog."""

from .config import CUE_SET_VERSION
from .expression_catalog import OFFICIAL_EMOTIONS_DATASET, motion_move_by_cue

# Backward-compatible exports used by the current lab executor/tests. The
# catalog, not this module, is the source of truth.
OFFICIAL_MOVE_BY_CUE = motion_move_by_cue(CUE_SET_VERSION)
REQUIRED_OFFICIAL_MOVES = frozenset(OFFICIAL_MOVE_BY_CUE.values())
