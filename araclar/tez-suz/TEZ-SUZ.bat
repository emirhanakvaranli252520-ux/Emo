@echo off
chcp 65001 >nul
echo ============================================
echo  HUKUK TEZLERINI SUZ (tezler.parquet)
echo ============================================
where py >nul 2>nul
if errorlevel 1 (
  echo Python bulunamadi. https://www.python.org adresinden Python 3.12 kurun ve tekrar deneyin.
  pause
  exit /b 1
)
py -m pip install --quiet duckdb==1.4.1
if "%~1"=="" (
  py "%~dp0tez_suz.py"
) else (
  py "%~dp0tez_suz.py" "%~1"
)
echo.
pause
