"""Build the wheel and check it ships every module and data file.

CI's install job runs an editable checkout, which imports from the source
tree, so it can't notice a file missing from the built package (the bug
where an unanchored `report.*` in .gitignore dropped checker/report.py).
This builds the real wheel and compares it against the tracked files.

    pixi run check-wheel
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    """Build, compare, and report; nonzero exit on any missing file."""
    tracked = subprocess.run(
        ["git", "ls-files", "checker"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    with tempfile.TemporaryDirectory() as out:
        subprocess.run(["hatchling", "build", "-t", "wheel", "-d", out], cwd=ROOT, check=True,
                       capture_output=True)
        [wheel] = Path(out).glob("*.whl")
        shipped = set(zipfile.ZipFile(wheel).namelist())
    missing = sorted(f for f in tracked if f not in shipped)
    if missing:
        print(f"{wheel.name} is missing {len(missing)} tracked file(s):", *missing, sep="\n  ")
        return 1
    print(f"{wheel.name}: all {len(tracked)} tracked files under checker/ are in the wheel")
    return 0


if __name__ == "__main__":
    sys.exit(main())
