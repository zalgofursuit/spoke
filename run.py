#!/usr/bin/env python3
"""Spoke: blog your ride. Run this file to open the posting GUI."""
import importlib, importlib.util, subprocess, sys

NEEDED = {"jinja2": "jinja2", "PIL": "pillow"}  # import name -> pip name
missing = [pip for mod, pip in NEEDED.items() if importlib.util.find_spec(mod) is None]
if missing:
    print("First run: installing " + ", ".join(missing) + "...")
    for extra in ([], ["--user"], ["--break-system-packages"]):
        if subprocess.call([sys.executable, "-m", "pip", "install", *missing, *extra]) == 0:
            break
    importlib.invalidate_caches()
if importlib.util.find_spec("jinja2") is None:
    sys.exit("Could not install Jinja2. Run:  python -m pip install jinja2 pillow")
if importlib.util.find_spec("PIL") is None:
    print("Note: Pillow isn't installed, so thumbnails will use the full-size images.\n"
          "      Fix with:  python -m pip install pillow")

from spoke.server import main

if __name__ == "__main__":
    main()
