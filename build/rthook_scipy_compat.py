# PyInstaller runtime hook — injected by the bootloader BEFORE any imports.
# Fixes scipy.inf / scipy.float_ etc. removed in scipy 1.11,
# which msaf.pymf depends on.
import sys

def _patch_scipy():
    try:
        import scipy
        import numpy as _np
        if not hasattr(scipy, "inf"):      scipy.inf      = _np.inf
        if not hasattr(scipy, "float_"):   scipy.float_   = _np.float64
        if not hasattr(scipy, "int_"):     scipy.int_     = _np.int_
        if not hasattr(scipy, "complex_"): scipy.complex_ = _np.complex128
        if not hasattr(scipy, "bool_"):    scipy.bool_    = _np.bool_
    except Exception:
        pass

_patch_scipy()
