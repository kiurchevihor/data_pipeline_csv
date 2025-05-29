# api.py - Исправленная версия без проблем с импортами
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
import sqlite3
import pandas as pd
import os
from datetime import datetime
import uuid
from pathlib import Path

app = FastAPI(title="ETL Pipeline API", version="1.0.0")

# Хранилище статусов запусков pipeline
pipeline_runs: Dict[str, Dict] = {}

# Models для API


class PipelineConfig(BaseModel):
    csv_path: str = "data/raw/products.csv"
    db_path: str = "data/processed/products.db"
    table_name: str = "products"


class PipelineRunRequest(BaseModel):
    config: Optional[PipelineConfig] = None
    run_name: Optional[str] = None

# Функции ETL pipeline (встроенные в api.py)


def ingest_data_local(path: str) -> pd.DataFrame:
    """Локальная версия функции ingest_data"""
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


def clean_data_local(df: pd.DataFrame) -> pd.DataFrame:
    """Локальная версия функции clean_data"""
    df_cleaned = df.dropna()
    return df_cleaned


def load_to_sqlite_local(df: pd.DataFrame, db_path: str, table_name: str):
    """Локальная версия функции load_to_sqlite"""
    # Создаем директорию если не существует
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    df.to_sql(table_name, conn, if_exists='replace', index=False)
    conn.close()

# Функция для запуска pipeline в фоне


async def run_pipeline_async(run_id: str, config: PipelineConfig):
    try:
        pipeline_runs[run_id]["status"] = "running"
        pipeline_runs[run_id]["message"] = "Ingesting data..."

        # Шаг 1: Инжест данных
        df_raw = ingest_data_local(config.csv_path)
        pipeline_runs[run_id]["message"] = f"Loaded {len(df_raw)} rows. Cleaning data..."

        # Шаг 2: Очистка данных
        df_clean = clean_data_local(df_raw)
        pipeline_runs[run_id]["message"] = f"Cleaned data: {len(df_clean)} rows remain. Loading to database..."

        # Шаг 3: Загрузка в БД
        load_to_sqlite_local(df_clean, config.db_path, config.table_name)

        pipeline_runs[run_id]["status"] = "completed"
        pipeline_runs[run_id]["message"] = f"Successfully processed {len(df_clean)} rows"
        pipeline_runs[run_id]["end_time"] = datetime.now()
        pipeline_runs[run_id]["records_processed"] = len(df_clean)

    except Exception as e:
        pipeline_runs[run_id]["status"] = "failed"
        pipeline_runs[run_id]["error_message"] = str(e)
        pipeline_runs[run_id]["message"] = f"Failed: {str(e)}"
        pipeline_runs[run_id]["end_time"] = datetime.now()

# API Endpoints


@app.post("/api/pipeline/run")
async def run_pipeline_endpoint(
    request: PipelineRunRequest,
    background_tasks: BackgroundTasks
):
    """Запустить ETL pipeline"""
    run_id = str(uuid.uuid4())
    config = request.config or PipelineConfig()

    # Проверяем существование исходного файла
    if not os.path.exists(config.csv_path):
        raise HTTPException(
            status_code=400,
            detail=f"Source file not found: {config.csv_path}"
        )

    pipeline_runs[run_id] = {
        "run_id": run_id,
        "status": "pending",
        "start_time": datetime.now(),
        "end_time": None,
        "error_message": None,
        "message": "Pipeline queued",
        "config": config.dict(),
        "run_name": request.run_name or f"Run {run_id[:8]}",
        "records_processed": 0
    }

    background_tasks.add_task(run_pipeline_async, run_id, config)

    return {
        "run_id": run_id,
        "status": "started",
        "message": "Pipeline started successfully"
    }


@app.get("/api/pipeline/status/{run_id}")
async def get_pipeline_status(run_id: str):
    """Получить статус запуска pipeline"""
    if run_id not in pipeline_runs:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    return pipeline_runs[run_id]


@app.get("/api/pipeline/runs")
async def get_all_runs():
    """Получить все запуски pipeline"""
    return sorted(
        pipeline_runs.values(),
        key=lambda x: x['start_time'],
        reverse=True
    )


@app.delete("/api/pipeline/runs")
async def clear_runs():
    """Очистить историю запусков"""
    global pipeline_runs
    pipeline_runs = {}
    return {"message": "Pipeline runs history cleared"}


@app.get("/api/data/preview")
async def preview_data(
    db_path: str = "data/processed/products.db",
    table_name: str = "products",
    limit: int = 10
):
    """Предварительный просмотр данных из БД"""
    try:
        if not os.path.exists(db_path):
            raise HTTPException(
                status_code=404, detail=f"Database not found: {db_path}")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Проверяем существование таблицы
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(
                status_code=404, detail=f"Table '{table_name}' not found")

        cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
        rows = cursor.fetchall()

        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [column[1] for column in cursor.fetchall()]

        conn.close()

        data = [dict(zip(columns, row)) for row in rows]
        return {"data": data, "columns": columns, "count": len(data)}

    except sqlite3.Error as e:
        raise HTTPException(
            status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/data/stats")
async def get_data_stats(
    db_path: str = "data/processed/products.db",
    table_name: str = "products"
):
    """Получить статистику по данным"""
    try:
        if not os.path.exists(db_path):
            raise HTTPException(
                status_code=404, detail=f"Database not found: {db_path}")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Проверяем существование таблицы
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(
                status_code=404, detail=f"Table '{table_name}' not found")

        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        total_records = cursor.fetchone()[0]

        cursor.execute(f"PRAGMA table_info({table_name})")
        columns_info = cursor.fetchall()
        columns = [column[1] for column in columns_info]

        conn.close()

        return {
            "total_records": total_records,
            "columns_count": len(columns),
            "columns": columns,
            "table_name": table_name,
            "database_path": db_path
        }

    except sqlite3.Error as e:
        raise HTTPException(
            status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/files/list")
async def list_csv_files(directory: str = "data/raw"):
    """Получить список CSV файлов в директории"""
    try:
        if not os.path.exists(directory):
            return {"files": [], "message": f"Directory {directory} does not exist"}

        csv_files = []
        for file in os.listdir(directory):
            if file.lower().endswith('.csv'):
                file_path = os.path.join(directory, file)
                file_size = os.path.getsize(file_path)
                csv_files.append({
                    "name": file,
                    "path": file_path,
                    "size_bytes": file_size,
                    "size_mb": round(file_size / (1024 * 1024), 2)
                })

        return {"files": csv_files, "directory": directory}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing files: {str(e)}")

# Web Interface (упрощенный HTML)


@app.get("/", response_class=HTMLResponse)
async def web_interface():
    """Главная страница веб-интерфейса"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ETL Pipeline Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css" rel="stylesheet">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/axios/0.24.0/axios.min.js"></script>
    </head>
    <body class="bg-gray-100">
        <div class="container mx-auto px-4 py-8">
            <h1 class="text-3xl font-bold text-center mb-8 text-blue-600">ETL Pipeline Dashboard</h1>
            
            <!-- Status Bar -->
            <div id="statusBar" class="mb-4 p-3 rounded hidden">
                <div id="statusMessage"></div>
            </div>
            
            <!-- Pipeline Controls -->
            <div class="bg-white rounded-lg shadow-md p-6 mb-6">
                <h2 class="text-xl font-semibold mb-4">Pipeline Control</h2>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                    <div>
                        <label class="block text-sm font-medium mb-1">CSV Path:</label>
                        <input type="text" id="csvPath" 
                               value="data/raw/products.csv" 
                               class="w-full border border-gray-300 rounded px-3 py-2">
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-1">DB Path:</label>
                        <input type="text" id="dbPath" 
                               value="data/processed/products.db" 
                               class="w-full border border-gray-300 rounded px-3 py-2">
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-1">Table Name:</label>
                        <input type="text" id="tableName" 
                               value="products" 
                               class="w-full border border-gray-300 rounded px-3 py-2">
                    </div>
                </div>
                <div class="flex gap-2">
                    <button onclick="runPipeline()" 
                            class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded">
                        🚀 Run Pipeline
                    </button>
                    <button onclick="listFiles()" 
                            class="bg-gray-500 hover:bg-gray-700 text-white font-bold py-2 px-4 rounded">
                        📁 List Files
                    </button>
                </div>
            </div>
            
            <!-- Pipeline Status -->
            <div class="bg-white rounded-lg shadow-md p-6 mb-6">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-xl font-semibold">Pipeline Runs</h2>
                    <div class="flex gap-2">
                        <button onclick="refreshRuns()" 
                                class="bg-green-500 hover:bg-green-700 text-white font-bold py-2 px-4 rounded">
                            🔄 Refresh
                        </button>
                        <button onclick="clearRuns()" 
                                class="bg-red-500 hover:bg-red-700 text-white font-bold py-2 px-4 rounded">
                            🗑️ Clear History
                        </button>
                    </div>
                </div>
                <div id="pipelineRuns" class="space-y-2">
                    <div class="text-gray-500 text-center py-4">No pipeline runs yet</div>
                </div>
            </div>
            
            <!-- Data Preview -->
            <div class="bg-white rounded-lg shadow-md p-6">
                <h2 class="text-xl font-semibold mb-4">Data Explorer</h2>
                <div class="mb-4 flex gap-2">
                    <button onclick="loadDataPreview()" 
                            class="bg-purple-500 hover:bg-purple-700 text-white font-bold py-2 px-4 rounded">
                        📊 Load Data
                    </button>
                    <button onclick="loadDataStats()" 
                            class="bg-yellow-500 hover:bg-yellow-700 text-white font-bold py-2 px-4 rounded">
                        📈 Show Stats
                    </button>
                </div>
                <div id="dataContainer" class="text-gray-500">
                    Click "Load Data" or "Show Stats" to explore your data
                </div>
            </div>
        </div>

        <script>
            function showStatus(message, isError = false) {
                const statusBar = document.getElementById('statusBar');
                const statusMessage = document.getElementById('statusMessage');
                
                statusBar.className = `mb-4 p-3 rounded ${isError ? 'bg-red-100 border border-red-400 text-red-700' : 'bg-green-100 border border-green-400 text-green-700'}`;
                statusMessage.textContent = message;
                statusBar.classList.remove('hidden');
                
                setTimeout(() => {
                    statusBar.classList.add('hidden');
                }, 5000);
            }
            
            async function runPipeline() {
                const config = {
                    csv_path: document.getElementById('csvPath').value,
                    db_path: document.getElementById('dbPath').value,
                    table_name: document.getElementById('tableName').value
                };
                
                try {
                    const response = await axios.post('/api/pipeline/run', {
                        config: config,
                        run_name: `Manual Run ${new Date().toLocaleString()}`
                    });
                    
                    showStatus(`Pipeline started successfully! Run ID: ${response.data.run_id}`);
                    refreshRuns();
                } catch (error) {
                    showStatus('Error starting pipeline: ' + (error.response?.data?.detail || error.message), true);
                }
            }
            
            async function refreshRuns() {
                try {
                    const response = await axios.get('/api/pipeline/runs');
                    const runs = response.data;
                    
                    const container = document.getElementById('pipelineRuns');
                    
                    if (runs.length === 0) {
                        container.innerHTML = '<div class="text-gray-500 text-center py-4">No pipeline runs yet</div>';
                        return;
                    }
                    
                    container.innerHTML = '';
                    
                    runs.forEach(run => {
                        const statusColors = {
                            'pending': 'bg-yellow-100 border-yellow-300 text-yellow-800',
                            'running': 'bg-blue-100 border-blue-300 text-blue-800',
                            'completed': 'bg-green-100 border-green-300 text-green-800',
                            'failed': 'bg-red-100 border-red-300 text-red-800'
                        };
                        
                        const statusEmojis = {
                            'pending': '⏳',
                            'running': '🔄',
                            'completed': '✅',
                            'failed': '❌'
                        };
                        
                        const colorClass = statusColors[run.status] || 'bg-gray-100 border-gray-300 text-gray-800';
                        
                        const runElement = document.createElement('div');
                        runElement.className = `p-4 rounded border ${colorClass}`;
                        runElement.innerHTML = `
                            <div class="flex justify-between items-start">
                                <div class="flex-1">
                                    <div class="font-semibold">
                                        ${statusEmojis[run.status]} ${run.run_name || run.run_id}
                                    </div>
                                    <div class="text-sm mt-1">${run.message || run.status.toUpperCase()}</div>
                                    ${run.records_processed ? `<div class="text-xs mt-1">Records: ${run.records_processed}</div>` : ''}
                                </div>
                                <div class="text-xs text-gray-600 ml-4">
                                    ${new Date(run.start_time).toLocaleString()}
                                    ${run.end_time ? `<br>Duration: ${Math.round((new Date(run.end_time) - new Date(run.start_time))/1000)}s` : ''}
                                </div>
                            </div>
                            ${run.error_message ? `<div class="text-red-600 text-sm mt-2 bg-red-50 p-2 rounded">${run.error_message}</div>` : ''}
                        `;
                        container.appendChild(runElement);
                    });
                } catch (error) {
                    console.error('Error loading runs:', error);
                }
            }
            
            async function clearRuns() {
                if (confirm('Are you sure you want to clear all pipeline runs history?')) {
                    try {
                        await axios.delete('/api/pipeline/runs');
                        showStatus('Pipeline runs history cleared');
                        refreshRuns();
                    } catch (error) {
                        showStatus('Error clearing runs: ' + (error.response?.data?.detail || error.message), true);
                    }
                }
            }
            
            async function listFiles() {
                try {
                    const response = await axios.get('/api/files/list');
                    const files = response.data.files;
                    
                    if (files.length === 0) {
                        showStatus('No CSV files found in data/raw directory', true);
                    } else {
                        const fileList = files.map(f => `${f.name} (${f.size_mb} MB)`).join(', ');
                        showStatus(`Found ${files.length} CSV files: ${fileList}`);
                    }
                } catch (error) {
                    showStatus('Error listing files: ' + (error.response?.data?.detail || error.message), true);
                }
            }
            
            async function loadDataPreview() {
                const dbPath = document.getElementById('dbPath').value;
                const tableName = document.getElementById('tableName').value;
                
                try {
                    const response = await axios.get(`/api/data/preview?db_path=${encodeURIComponent(dbPath)}&table_name=${encodeURIComponent(tableName)}`);
                    const data = response.data;
                    
                    if (data.data.length === 0) {
                        document.getElementById('dataContainer').innerHTML = 
                            '<div class="text-gray-500">No data found in the table</div>';
                        return;
                    }
                    
                    let html = '<div class="overflow-x-auto"><table class="min-w-full bg-white border border-gray-300">';
                    
                    // Headers
                    html += '<thead class="bg-gray-50"><tr>';
                    data.columns.forEach(col => {
                        html += `<th class="px-4 py-2 border-b text-left font-semibold">${col}</th>`;
                    });
                    html += '</tr></thead>';
                    
                    // Data rows
                    html += '<tbody>';
                    data.data.forEach((row, index) => {
                        html += `<tr class="${index % 2 === 0 ? 'bg-white' : 'bg-gray-50'} hover:bg-blue-50">`;
                        data.columns.forEach(col => {
                            html += `<td class="px-4 py-2 border-b text-sm">${row[col] || ''}</td>`;
                        });
                        html += '</tr>';
                    });
                    html += '</tbody></table></div>';
                    html += `<div class="mt-2 text-sm text-gray-600">Showing ${data.count} rows</div>`;
                    
                    document.getElementById('dataContainer').innerHTML = html;
                } catch (error) {
                    document.getElementById('dataContainer').innerHTML = 
                        `<div class="text-red-600">Error loading data: ${error.response?.data?.detail || error.message}</div>`;
                }
            }
            
            async function loadDataStats() {
                const dbPath = document.getElementById('dbPath').value;
                const tableName = document.getElementById('tableName').value;
                
                try {
                    const response = await axios.get(`/api/data/stats?db_path=${encodeURIComponent(dbPath)}&table_name=${encodeURIComponent(tableName)}`);
                    const stats = response.data;
                    
                    const html = `
                        <div class="bg-gray-50 p-6 rounded-lg">
                            <h3 class="font-semibold text-lg mb-4">📊 Database Statistics</h3>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div class="bg-white p-4 rounded shadow-sm">
                                    <div class="text-2xl font-bold text-blue-600">${stats.total_records.toLocaleString()}</div>
                                    <div class="text-sm text-gray-600">Total Records</div>
                                </div>
                                <div class="bg-white p-4 rounded shadow-sm">
                                    <div class="text-2xl font-bold text-green-600">${stats.columns_count}</div>
                                    <div class="text-sm text-gray-600">Columns</div>
                                </div>
                            </div>
                            <div class="mt-4">
                                <h4 class="font-medium mb-2">Column Names:</h4>
                                <div class="flex flex-wrap gap-2">
                                    ${stats.columns.map(col => `<span class="bg-blue-100 text-blue-800 px-2 py-1 rounded text-sm">${col}</span>`).join('')}
                                </div>
                            </div>
                            <div class="mt-4 text-sm text-gray-600">
                                <strong>Table:</strong> ${stats.table_name}<br>
                                <strong>Database:</strong> ${stats.database_path}
                            </div>
                        </div>
                    `;
                    
                    document.getElementById('dataContainer').innerHTML = html;
                } catch (error) {
                    document.getElementById('dataContainer').innerHTML = 
                        `<div class="text-red-600">Error loading stats: ${error.response?.data?.detail || error.message}</div>`;
                }
            }
            
            // Автоматическое обновление статусов каждые 3 секунды
            setInterval(refreshRuns, 3000);
            
            // Загрузка данных при загрузке страницы
            window.onload = function() {
                refreshRuns();
            };
        </script>
    </body>
    </html>
    """

# Создание тестовых данных


@app.on_event("startup")
async def startup_event():
    """Создание необходимых директорий и тестовых данных"""
    # Создаем директории
    Path("data/raw").mkdir(parents=True, exist_ok=True)
    Path("data/processed").mkdir(parents=True, exist_ok=True)

    # Создаем тестовый CSV если его нет
    test_csv_path = "data/raw/products.csv"
    if not os.path.exists(test_csv_path):
        test_data = pd.DataFrame({
            'id': range(1, 101),
            'name': [f'Product {i}' for i in range(1, 101)],
            'price': [round(10 + (i * 0.5), 2) for i in range(1, 101)],
            'category': ['Electronics' if i % 3 == 0 else 'Books' if i % 3 == 1 else 'Clothing' for i in range(1, 101)],
            'in_stock': [True if i % 2 == 0 else False for i in range(1, 101)]
        })
        test_data.to_csv(test_csv_path, index=False)
        print(f"Created test data: {test_csv_path}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
