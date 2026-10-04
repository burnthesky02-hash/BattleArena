@echo off
title Battle Arena - Pull Updates
cd /d "%~dp0"

where git >nul 2>nul
if errorlevel 1 (
    echo Git is not installed or not on PATH. Install it from https://git-scm.com/download/win
    echo.
    pause
    exit /b 1
)

if not exist ".git" (
    echo This folder is not a git repository yet.
    echo Run "git init" and add your remote first, or clone the repo with "git clone".
    echo.
    pause
    exit /b 1
)

echo Current branch:
git branch --show-current
echo.
echo Pulling the latest changes...
echo.
git pull
if errorlevel 1 (
    echo.
    echo Pull failed. If you have local edits that conflict, commit or stash them first:
    echo     git stash
    echo     git pull
    echo     git stash pop
) else (
    echo.
    echo Done. You are up to date.
)
echo.
pause
