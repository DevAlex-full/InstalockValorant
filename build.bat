@echo off
title InstalockValorant — Build
color 0A

echo.
echo  ==========================================
echo   InstalockValorant — Build para .EXE
echo  ==========================================
echo.

:: Verifica se Python esta instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERRO] Python nao encontrado!
    echo.
    echo  Baixe e instale em: https://www.python.org/downloads/
    echo  IMPORTANTE: Marque "Add Python to PATH" durante a instalacao!
    echo.
    pause
    exit /b 1
)

echo  [1/4] Python encontrado. Instalando dependencias...
echo.
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo  [ERRO] Falha ao instalar dependencias.
    pause
    exit /b 1
)

echo  [2/4] Instalando PyInstaller e gerando icone .ico...
pip install pyinstaller --quiet
python assets\make_ico.py
if not exist "assets\instalock_logo.ico" (
    echo  [AVISO] Falha ao gerar .ico — o .exe ficara sem icone personalizado.
)

echo  [3/4] Compilando .exe (pode demorar 1-2 minutos)...
echo.

cd src

python -m PyInstaller ^
  --onefile ^
  --windowed ^
  --name "InstalockValorant" ^
  --icon "../assets/instalock_logo.ico" ^
  --add-data "../requirements.txt;." ^
  --add-data "../assets/instalock_logo.png;." ^
  --add-data "../assets/instalock_logo.ico;." ^
  --hidden-import "pynput.keyboard._win32" ^
  --hidden-import "pynput.mouse._win32" ^
  --collect-all "customtkinter" ^
  --collect-all "pynput" ^
  --collect-all "valclient" ^
  main.py

cd ..

:: Move o exe para pasta raiz
if exist "src\dist\InstalockValorant.exe" (
    move /Y "src\dist\InstalockValorant.exe" "InstalockValorant.exe" >nul
    echo.
    echo  ==========================================
    echo   [OK] Build concluido com sucesso!
    echo   Arquivo: InstalockValorant.exe
    echo  ==========================================
    echo.
    echo  Pode distribuir o .exe — nao precisa de Python instalado.
    echo.
) else (
    echo  [ERRO] Build falhou. Verifique os erros acima.
)

:: Limpa arquivos temporarios
if exist "src\dist" rmdir /s /q "src\dist"
if exist "src\build" rmdir /s /q "src\build"
if exist "src\InstalockValorant.spec" del "src\InstalockValorant.spec"

echo  [4/4] Limpeza feita.
echo.
pause