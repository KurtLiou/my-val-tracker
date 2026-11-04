@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在安裝 App 視窗需要的套件 pywebview（只要做一次）...
echo.
python -m pip install --upgrade pywebview
if errorlevel 1 (
  echo.
  echo [安裝失敗] 請把上面的訊息截圖給 Claude。
  pause
  exit /b 1
)
echo.
echo 安裝完成！之後雙擊「2_start.bat」就能開 App。
pause
