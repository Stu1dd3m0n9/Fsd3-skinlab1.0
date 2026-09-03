# Copyright (c) 2026 StoicDemon - MIT License, see LICENSE.
"""fsd3-skinlab entry point — works as module AND as script.

Module:  python -m src.main        (from fsd3-skinlab/)
Script:  python src/main.py        (from fsd3-skinlab/)
Double-click friendly via ../app.py.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))  # .../src
ROOT = os.path.dirname(HERE)  # .../fsd3-skinlab
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from src.studio import main  # package mode: relative imports resolve
except ImportError:
    from studio import main  # direct mode

if __name__ == "__main__":
    main()
