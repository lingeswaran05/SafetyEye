"""
SafetyEye Application Entrypoint.
Launch using: streamlit run app.py or python run_dashboard.py
"""
import sys
from pathlib import Path

# Ensure root directory is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.app import main

if __name__ == "__main__":
    main()
