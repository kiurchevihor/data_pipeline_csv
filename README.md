# data_pipeline_csv

A simple yet complete data engineering pipeline in Python. It reads CSV data, processes it, stores it in SQLite, and is orchestrated using Prefect.

# 🛠 CSV Data Pipeline with SQLite and Prefect

This is a simple but complete Data Engineering pipeline built with Python. It includes:

- ✅ CSV ingestion
- ✅ Data transformation
- ✅ Loading into SQLite
- ✅ Orchestrated with Prefect
- ✅ Optional analysis in Jupyter

## 📦 Project Structure

## 🏁 How to Run

data/
├── raw/ # Raw CSV files
└── processed/ # Cleaned/transformed CSVs

src/
├── ingest.py
├── transform.py
├── load.py
└── utils.py

flows/
└── pipeline.py # Prefect Flow

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
