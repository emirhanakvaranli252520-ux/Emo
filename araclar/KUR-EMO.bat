@echo off
chcp 65001 >nul
setlocal EnableExtensions
title Emo - Turk Hukuku Uzmani - Kurulum

echo ==============================================================
echo  EMO KURULUMU (Windows)
echo  Bu dosyanin bulundugu klasore "Emo" klasoru olarak kurulur.
echo ==============================================================
echo.

set "KOK=%~dp0"
set "EMO=%KOK%Emo"
set "DAL=claude/turkish-law-ai-expert-q0m9dh"
set "REPO=https://github.com/emirhanakvaranli252520-ux/Emo.git"
set "MUTALAA=mutalaamcp @ git+https://github.com/hburaktasyurek/MutalaaMCP@54f4f8ed5f8558f94e6ea0aa01660452aa88f523"

rem ---------------------------------------------------------------- 1. Git ve Python
echo [1/7] Git ve Python kontrol ediliyor...
where git >nul 2>nul
if errorlevel 1 (
  echo   Git kuruluyor...
  winget install -e --id Git.Git --accept-source-agreements --accept-package-agreements
  echo   Git kuruldu. Bu pencereyi kapatip KUR-EMO.bat dosyasini YENIDEN calistirin.
  pause
  exit /b 0
)
where py >nul 2>nul
if errorlevel 1 (
  echo   Python 3.12 kuruluyor...
  winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
  echo   Python kuruldu. Bilgisayari yeniden baslatip KUR-EMO.bat dosyasini YENIDEN calistirin.
  pause
  exit /b 0
)
py -3.12 -c "import sys" >nul 2>nul
if errorlevel 1 (
  echo   [!] Python 3.12 bulunamadi. Mutalaa icin Python 3.12 veya ustu gerekir.
  echo       winget install -e --id Python.Python.3.12  komutuyla kurup tekrar deneyin.
  pause
  exit /b 1
)
set "PY=py -3.12"
echo   Tamam.

rem ---------------------------------------------------------------- 2. Repo
echo.
echo [2/7] Emo deposu indiriliyor...
if exist "%EMO%\.git" (
  git -C "%EMO%" fetch origin %DAL%
  git -C "%EMO%" checkout %DAL%
  git -C "%EMO%" pull --ff-only origin %DAL%
) else (
  echo   GitHub giris penceresi acilirsa hesabinizla giris yapin.
  git clone --branch %DAL% "%REPO%" "%EMO%"
)
if not exist "%EMO%\.claude-plugin\plugin.json" (
  echo   [!] Depo indirilemedi. GitHub erisiminizi kontrol edip tekrar deneyin.
  pause
  exit /b 1
)
echo   Tamam: %EMO%

rem ---------------------------------------------------------------- 3. Python paketleri
echo.
echo [3/7] Arama kutuphaneleri kuruluyor ^(birkac dakika^)...
%PY% -m pip install --quiet --upgrade pip
%PY% -m pip install --quiet -r "%EMO%\skills\ictihat-korpusu\scripts\requirements.txt"
%PY% -m pip install --quiet -r "%EMO%\skills\ictihat-arsivi\scripts\requirements.txt"
echo   Tamam.

rem ---------------------------------------------------------------- 4. Mutalaa
echo.
echo [4/7] Mutalaa ^(resmi mevzuat ve karar kaynagi^) kuruluyor...
%PY% -m pip install --quiet "%MUTALAA%"
where mutalaamcp >nul 2>nul
if errorlevel 1 (
  for /f "delims=" %%S in ('%PY% -c "import sysconfig;print(sysconfig.get_path('scripts'))"') do set "PYSCRIPTS=%%S"
  echo   [!] mutalaamcp komutu PATH icinde degil.
  echo       Su klasoru PATH'e ekleyin ve Claude'u yeniden baslatin:
  echo       %PYSCRIPTS%
  echo       ^(Windows arama: "ortam degiskenleri" ^> Path ^> Yeni^)
) else (
  echo   Tamam.
)

rem ---------------------------------------------------------------- 5. Korpus ve arsiv
echo.
echo [5/7] Ictihat verileri
echo   - Korpus: 11 milyon karar, kunye kontrolu icin ^(yaklasik 5,5 GB, SHA-256 dogrulamali^)
choice /C EH /M "  Korpus simdi indirilsin mi? (E/H)"
if errorlevel 2 goto arsiv
%PY% "%EMO%\skills\ictihat-korpusu\scripts\korpus.py" indir
%PY% "%EMO%\skills\ictihat-korpusu\scripts\korpus.py" indeks
%PY% "%EMO%\skills\ictihat-korpusu\scripts\korpus.py" denetle
:arsiv
echo   - Arsiv: 700 bin karar, anlamsal arama icin ^(yaklasik 5 GB indirme^)
choice /C EH /M "  Arsiv simdi indirilsin mi? (E/H)"
if errorlevel 2 goto tez
%PY% "%EMO%\skills\ictihat-arsivi\scripts\indir.py"

rem ---------------------------------------------------------------- 6. Tez suzme
:tez
echo.
echo [6/7] Tez suzme
set "TEZ="
if exist "%USERPROFILE%\Downloads\tezler.parquet" set "TEZ=%USERPROFILE%\Downloads\tezler.parquet"
if exist "%KOK%tezler.parquet" set "TEZ=%KOK%tezler.parquet"
if defined TEZ (
  echo   Bulundu: %TEZ%
  %PY% "%EMO%\araclar\tez-suz\tez_suz.py" "%TEZ%"
) else (
  echo   tezler.parquet bulunamadi; bu adim atlandi.
)

rem ---------------------------------------------------------------- 7. Plugin
echo.
echo [7/7] Emo eklentisi
where claude >nul 2>nul
if errorlevel 1 goto elle
claude plugin marketplace add "%EMO%"
claude plugin install emo@emo-hukuk
echo   Tamam. Claude'u yeniden baslatin.
goto son
:elle
echo   Claude komut satiri bulunamadi. Claude masaustu uygulamasinda Code sekmesinde
echo   yeni bir oturum acip su iki komutu sirayla yazin:
echo     /plugin marketplace add %EMO%
echo     /plugin install emo@emo-hukuk

:son
echo.
echo ==============================================================
echo  KURULUM BITTI
echo  Calisma klasoru : %EMO%
echo  Dava klasorleri : %EMO%\davalar
echo  Ilk deneme      : Claude Code'da  /emo:dava-ac deneme
echo ==============================================================
pause
endlocal
