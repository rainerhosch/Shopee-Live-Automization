@echo off
echo ==============================================
echo Starting Shopee Live Bot...
echo ==============================================

:: Activating virtual environment
call .venv\Scripts\activate

:: Open Default Browser
echo Membuka browser ke http://127.0.0.1:8000...
start http://127.0.0.1:8000

:: Run Uvicorn Server
echo Menjalankan Uvicorn server...
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000