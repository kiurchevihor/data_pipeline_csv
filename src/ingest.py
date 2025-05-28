import pandas as pd
from pathlib import Path


def ingest_csv(file_path: str) -> pd.DataFrame:
    df = pd.read_csv(file_path)
    return df
