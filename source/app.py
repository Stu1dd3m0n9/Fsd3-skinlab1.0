# Copyright (c) 2026 StoicDemon - MIT License, see LICENSE.
"""Double-click / console launcher for FSD3 Skin Studio.

Run any of these from anywhere:
  python app.py
  python -m src.main   (from this folder)
  double-click app.py
Errors pop up in a dialog instead of a console that vanishes.
"""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))
sys.path.insert(0, HERE)


def main() -> int:
    try:
        from studio import main as run
    except ImportError:
        from src.studio import main as run
    try:
        run()
        return 0
    except Exception:
        tb = traceback.format_exc()
        try:
            with open(os.path.join(HERE, "studio_crash.log"), "a", encoding="utf-8") as fh:
                fh.write(tb + "\n")
        except OSError:
            pass
        try:
            import tkinter as tk
            from tkinter import messagebox
            r = tk.Tk()
            r.withdraw()
            messagebox.showerror("FSD3 Skin Studio crashed", tb[-2000:])
            r.destroy()
        except Exception:
            print(tb)
        return 1


if __name__ == "__main__":
    sys.exit(main())
