from prefect import flow, task
from src.ingest import ingest_data
from src.transform import clean_data
from src.load import load_to_sqlite

CSV_PATH = "data/raw/products.csv"
DB_PATH = "data/processed/products.db"
TABLE_NAME = "products"


@task
def ingest_task():
    return ingest_data(CSV_PATH)


@task
def transform_task(df):
    return clean_data(df)


@task
def load_task(df):
    load_to_sqlite(df, DB_PATH, TABLE_NAME)


@flow(name="CSV Data Pipeline")
def run_pipeline():
    df_raw = ingest_task()
    df_clean = transform_task(df_raw)
    load_task(df_clean)


if __name__ == "__main__":
    run_pipeline()
