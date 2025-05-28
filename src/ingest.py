from pathlib import Path
import pandas as pd
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def ingest_data(path: str) -> pd.DataFrame:
    path = Path(path)

    if path.is_file():
        if path.suffix.lower() == ".csv":
            try:
                logger.info(f"Reading file: {path}")
                return pd.read_csv(path)
            except Exception as e:
                logger.error(f"Failed to read file {path}: {e}")
                raise
        else:
            raise ValueError(f"File {path} is not a CSV file.")

    elif path.is_dir():
        dfs = []
        for file in path.iterdir():
            if file.is_file() and not file.name.startswith('.') and file.suffix.lower() == ".csv":
                try:
                    logger.info(f"Reading file: {file}")
                    dfs.append(pd.read_csv(file))
                except Exception as e:
                    logger.warning(
                        f"Skipping file {file} due to read error: {e}")
        if not dfs:
            raise FileNotFoundError(
                f"No readable CSV files found in directory {path}")
        return pd.concat(dfs, ignore_index=True)

    else:
        raise FileNotFoundError(
            f"Path {path} does not exist or is not accessible.")
