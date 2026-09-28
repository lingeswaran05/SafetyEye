import json
from pathlib import Path
from typing import Optional
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "dashboard" / "static" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOG_DIR / "violations.jsonl"


def read_logs(log_path: Optional[Path] = None) -> pd.DataFrame:
    """Reads violation records from JSONL log file into a Pandas DataFrame."""
    target_path = log_path or LOG_PATH
    if not target_path.exists():
        return pd.DataFrame()

    rows = []
    with open(target_path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                rows.append(json.loads(line_str))
            except json.JSONDecodeError:
                continue

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df


def export_csv(df: pd.DataFrame, out_path: Optional[Path] = None) -> Path:
    """Exports violations DataFrame to CSV format."""
    if out_path is None:
        out_path = LOG_DIR / "exported_violations.csv"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return out_path
