from prefect import flow, task
import logging
from src.ingest import ingest_data
from src.transform import clean_data
from src.load import load_to_sqlite

CSV_PATH = "data/raw/products.csv"
DB_PATH = "data/processed/products.db"
TABLE_NAME = "products"


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@task
def ingest_task():
    logger.info(f"Ingesting data from {CSV_PATH}")
    return ingest_data(CSV_PATH)


@task
def transform_task(df):
    logger.info("Transforming data")
    return clean_data(df)


@task
def load_task(df):
    logger.info(f"Loading data into {DB_PATH} (table: {TABLE_NAME})")
    load_to_sqlite(df, DB_PATH, TABLE_NAME)


@flow(name="CSV Data Pipeline")
def run_pipeline():
    try:
        df_raw = ingest_task()
        df_clean = transform_task(df_raw)
        load_task(df_clean)
        logger.info("Pipeline completed successfully.")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise


if __name__ == "__main__":
    run_pipeline()
