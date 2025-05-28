import pandas as pd
from pathlib import Path


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna()
    return df
