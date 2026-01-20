@echo off
echo ========================================
echo  Postbank FinTS Client - API Update Mode
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

:: Check if API_URL is set
findstr /C:"API_URL=" ".env" >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: API_URL not found in .env
    echo Please add your API settings to .env
    pause
    exit /b 1
)

echo Starting FinTS client in API update mode...
echo TAN challenges will be sent via Telegram.
echo.
uv run python -m fintts_postbank.main --update-api
echo.
pause
