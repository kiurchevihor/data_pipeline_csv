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

```

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

```

## 🏁 How to Run

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

````

2. Run the pipeline with proper module resolution:

   ```bash
   PYTHONPATH=. python3 flows/pipeline.py
   ```

### ⚙️ IDE Setup (Optional)

If you're using an IDE like VS Code or PyCharm, set the `PYTHONPATH` so it resolves modules
correctly.

#### VS Code

Create a `.vscode/launch.json`:

json
{
  "configurations": [
    {
      "name": "Run Pipeline",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/flows/pipeline.py",
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      }
    }
  ]
}
```

#### PyCharm

- Go to **Run > Edit Configurations...**
- Add a Python configuration with:

  - Script: `flows/pipeline.py`
  - Working directory: the project root
  - Environment variable: `PYTHONPATH=.`

---
````
