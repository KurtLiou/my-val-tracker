@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -c "import webview" 2>nul
if errorlevel 1 (
  echo 還沒安裝 pywebview，請先雙擊「1_install.bat」。
  pause
  exit /b 1
)
start "" pythonw app.py %*
