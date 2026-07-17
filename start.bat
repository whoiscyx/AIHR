@echo off
setlocal

REM Change to the directory of this script so it works from any cwd
cd /d "%~dp0"

REM Create the virtual environment if it does not exist yet
if not exist ".venv\Scripts\activate.bat" (
    echo [setup] Creating virtual environment in .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [error] Could not create .venv. Please install Python 3.10+ and make sure 'python' is on PATH.
        pause
        exit /b 1
    )
)

REM Activate the virtual environment
call .venv\Scripts\activate.bat

REM Install dependencies only if fastapi is missing inside the venv
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo [setup] Installing dependencies from requirements.txt ...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
)

echo Starting service ... (first model load may be slow)
echo Open your browser at: http://127.0.0.1:8000
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
