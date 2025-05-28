import os
import pandas as pd


def ingest_data(path: str) -> pd.DataFrame:
    if os.path.isfile(path):
        if path.lower().endswith(".csv"):
            return pd.read_csv(path)
        else:
            raise ValueError(f"File {path} is not a CSV file.")
    elif os.path.isdir(path):
        dfs = []
        for file in os.listdir(path):
            if file.lower().endswith(".csv"):
                full_path = os.path.join(path, file)
                dfs.append(pd.read_csv(full_path))
        if not dfs:
            raise FileNotFoundError("No CSV files found in directory.")
        return pd.concat(dfs, ignore_index=True)
    else:
        raise FileNotFoundError(f"Path {path} does not exist.")
