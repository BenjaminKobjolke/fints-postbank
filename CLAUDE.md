# Code Analysis Workflow

After implementing new features, run the following code quality checks:

## Step 1: Run Code Analysis

Detect code quality issues:

```bash
powershell -Command "cd 'D:\GIT\BenjaminKobjolke\fints-postbank\tools'; cmd /c '.\analyze_code.bat'"
```

## Step 2: Auto-fix Ruff Issues

Automatically fix ruff linting issues:

```bash
powershell -Command "cd 'D:\GIT\BenjaminKobjolke\fints-postbank\tools'; cmd /c '.\fix_ruff_issues.bat'"
```

## Step 3: Fix Remaining Issues

Review and manually fix any remaining issues reported by the analyzer that couldn't be auto-fixed.
