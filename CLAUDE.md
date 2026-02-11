# Package Management

This project uses **uv** as its package manager (not pip). Use `uv pip install` for all package operations.

## Bot Library Repos

The bot libraries are local dependencies. If changes need to be made to the bots, edit them directly at:

- **Telegram bot:** `D:\GIT\BenjaminKobjolke\telegram-bot`
- **XMPP bot:** `D:\GIT\BenjaminKobjolke\xmpp-bot`

After editing, reinstall into the project venv:

```bash
uv pip install -e "D:\GIT\BenjaminKobjolke\telegram-bot" -e "D:\GIT\BenjaminKobjolke\xmpp-bot"
```

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
