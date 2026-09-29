@echo off
rem Battle Arena - double-click to play. Opens the game in its own window.
cd /d "%~dp0"
where python >nul 2>nul || (echo Python was not found. Install Python 3 from python.org and tick "Add to PATH". & pause & exit /b 1)
python -c "import websockets" 2>nul || python -m pip install websockets
where pythonw >nul 2>nul && (start "" pythonw launcher.py %*) || (start "" python launcher.py %*)
