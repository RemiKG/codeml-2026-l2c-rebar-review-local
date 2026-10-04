"""Local L2C drawing reconciliation. No remote inference or document upload."""
import os
for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "2"
__version__ = "0.1.0"
