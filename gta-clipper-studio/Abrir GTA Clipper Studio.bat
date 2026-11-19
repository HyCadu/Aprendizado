@echo off
rem Abre o GTA CLIPPER STUDIO (sem janela preta). Na primeira vez instala o PySide6.
cd /d "%~dp0"

set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" (
  for /f "delims=" %%i in ('where python 2^>nul ^| findstr /v /i "WindowsApps"') do if not defined PYFOUND set "PYFOUND=%%i"
)
if defined PYFOUND set "PY=%PYFOUND%"
if not exist "%PY%" (
  echo Python nao encontrado. Instale em python.org marcando "Add python.exe to PATH".
  pause
  exit /b 1
)

"%PY%" -c "import PySide6" 2>nul
if errorlevel 1 (
  echo Instalando a interface grafica ^(PySide6^), so na primeira vez...
  "%PY%" -m pip install --disable-pip-version-check -r requirements.txt
  if errorlevel 1 (
    echo Falha ao instalar o PySide6. Confira a internet e tente de novo.
    pause
    exit /b 1
  )
)

set "PYW=%PY:python.exe=pythonw.exe%"
if exist "%PYW%" (
  start "" "%PYW%" main.py
) else (
  start "" "%PY%" main.py
)
