"""
Launcher script to run SafetyEye Dashboard via Python.
Execute: python run_dashboard.py
"""
import subprocess
import sys
from pathlib import Path


def main() -> int:
    app_file = Path(__file__).resolve().parent / "app.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_file)]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
