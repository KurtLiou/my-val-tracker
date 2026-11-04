@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在打包成 VAL小戰績.exe（大約 1~3 分鐘）...
python -m pip install --upgrade pywebview pyinstaller
if errorlevel 1 goto fail
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "ValTracker" --icon icon.ico --add-data "static;static" app.py
if errorlevel 1 goto fail
copy /y "dist\ValTracker.exe" "ValTracker.exe" >nul
echo.
echo 完成！資料夾裡多了「ValTracker.exe」，雙擊就能開。
echo 想放桌面：對它按右鍵 → 傳送到 → 桌面（建立捷徑）。
pause
exit /b 0
:fail
echo.
echo [打包失敗] 請把上面的訊息截圖給 Claude。
pause
exit /b 1
