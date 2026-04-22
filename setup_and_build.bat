@echo off
chcp 65001 >nul
echo ===================================================
echo   Antarus PO Finder -- Ustanovka i sborka EXE
echo ===================================================
echo.

:: --- 1. Python ---
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python ne nayden.
    echo Ustanovite Python 3.10+ s https://python.org/downloads/
    echo Vazno: pri ustanovke postavte galochku "Add Python to PATH"
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] %PYVER%

:: --- 2. Zavisimosti ---
echo.
echo [*] Ustanavlivaem zavisimosti...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet --upgrade-strategy only-if-needed
if errorlevel 1 (
    echo [ERROR] Ne udalos ustanovit zavisimosti.
    pause
    exit /b 1
)
echo [OK] Zavisimosti ustanovleny.

:: --- 3. Ikonka ---
echo.
echo [*] Generiruem ikonku...
python make_assets.py
if errorlevel 1 (
    echo [ERROR] Ne udalos sozdat ikonku.
    pause
    exit /b 1
)

:: --- 4. Sborka EXE ---
echo.
echo [*] Sobiraem EXE (2-3 minuty)...
python -c "import PyInstaller.__main__; PyInstaller.__main__.run(['--onefile','--windowed','--name','Antarus_PO_Finder','--icon','assets/icon.ico','--add-data','assets;assets','--hidden-import','PySide6.QtSvg','--hidden-import','PySide6.QtSvgWidgets','--hidden-import','PySide6.QtXml','--collect-submodules','app','main.py'])"

if errorlevel 1 (
    echo [ERROR] Sborka zavershilas s oshibkoy.
    pause
    exit /b 1
)

:: --- 5. Proverka i kopirovaniye ---
if not exist "dist\Antarus_PO_Finder.exe" (
    echo [ERROR] EXE ne naydyen v dist\ -- sborka ne udalas.
    pause
    exit /b 1
)

copy /y "dist\Antarus_PO_Finder.exe" "Antarus_PO_Finder.exe" >nul
echo.
echo ===================================================
echo   Gotovo! EXE: Antarus_PO_Finder.exe
echo ===================================================
echo.
pause
