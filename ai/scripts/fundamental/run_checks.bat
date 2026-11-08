@echo off
setlocal
cd /d C:\verith\ai
chcp 65001 >nul

echo [1/4] Running fundamental tests...
C:\verith\.venv\Scripts\python.exe -m pytest tests\fundamental -v
if errorlevel 1 exit /b 1

echo.
echo [2/4] Checking Qwen endpoint...
C:\verith\.venv\Scripts\python.exe -m scripts.fundamental.check_qwen
if errorlevel 1 exit /b 1

echo.
echo [3/4] Writing sample payload...
C:\verith\.venv\Scripts\python.exe -m scripts.fundamental.make_sample_payload
if errorlevel 1 exit /b 1

echo.
echo [4/4] Running 10-company batch...
C:\verith\.venv\Scripts\python.exe -m scripts.fundamental.batch_demo
if errorlevel 1 exit /b 1

echo.
echo DONE. Summary:
echo C:\verith\ai\src\agents\fundamental\api_test\out\summary.md
endlocal
