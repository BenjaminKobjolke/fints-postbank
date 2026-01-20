@echo off
d:
cd "d:\GIT\BenjaminKobjolke\cli-code-analyzer"

call venv\Scripts\python.exe ruff_fixer.py --path "D:\GIT\BenjaminKobjolke\fints-postbank" --rules "D:\GIT\BenjaminKobjolke\fints-postbank\code_analysis_rules.json" --dry-run

cd %~dp0
pause
