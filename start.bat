@echo off
echo ========================================
echo  Postbank FinTS Client
echo ========================================
echo.

:: Check if uv is installed
where uv >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: uv is not installed or not in PATH
    echo Please install uv first: https://docs.astral.sh/uv/getting-started/installation/
    pause
    exit /b 1
)

:: Check if .env exists
if not exist ".env" (
    echo ERROR: .env file not found
    echo Please copy .env.example to .env and fill in your credentials
    pause
    exit /b 1
)

echo Starting FinTS client...
echo.
uv run python -m fintts_postbank.main
echo.
pause
