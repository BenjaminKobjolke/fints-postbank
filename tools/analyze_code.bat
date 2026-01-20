@echo off
d:
cd "d:\GIT\BenjaminKobjolke\cli-code-analyzer"

call venv\Scripts\python.exe main.py --language python --path "D:\GIT\BenjaminKobjolke\fints-postbank" --verbosity minimal --output "D:\GIT\BenjaminKobjolke\fints-postbank\code_analysis_results" --maxamountoferrors 50 --rules "D:\GIT\BenjaminKobjolke\fints-postbank\code_analysis_rules.json"

cd %~dp0
pause
