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

:: Check if any .env config exists (.env or .env.<name>)
set "ENV_FOUND=0"
if exist ".env" set "ENV_FOUND=1"
for %%f in (.env.*) do (
    if /I not "%%f"==".env.example" set "ENV_FOUND=1"
)
if "%ENV_FOUND%"=="0" (
    echo ERROR: No .env file found
    echo Please copy .env.example to .env ^(or .env.name^) and fill in your credentials
    pause
    exit /b 1
)

echo Starting FinTS client...
echo.
uv run python -m fintts_postbank.main %*
echo.
pause
