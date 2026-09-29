@echo off
rem Builds a standalone BattleArena.exe (Python bundled) into dist\BattleArena\ -- run on Windows.
rem Requires Python 3 on PATH. Takes a few minutes; the folder is large because of the art.
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller websockets || (echo pip failed & pause & exit /b 1)
if exist dist\BattleArena rmdir /s /q dist\BattleArena
set ICON=
if exist icon.ico set ICON=--icon icon.ico
python -m PyInstaller --noconfirm --clean --windowed --name BattleArena %ICON% ^
  --collect-submodules websockets ^
  --add-data "html_hub;html_hub" --add-data "html_battle;html_battle" --add-data "html_overworld;html_overworld" ^
  --add-data "data\Portraits;data\Portraits" --add-data "data\Battlers;data\Battlers" ^
  --add-data "data\Bosses;data\Bosses" --add-data "data\Artwork;data\Artwork" ^
  launcher.py
if errorlevel 1 (echo BUILD FAILED & pause & exit /b 1)
rem Debug launcher next to the exe (windowed exe has no console; this passes --debug)
> dist\BattleArena\BattleArena-Debug.bat echo @start "" "%%~dp0BattleArena.exe" --debug
echo.
echo Done: dist\BattleArena\BattleArena.exe   (BattleArena-Debug.bat for debug tools)
echo Saves are kept in dist\BattleArena\saves. Copy your existing saves\save1.json there to keep your progress.
pause
