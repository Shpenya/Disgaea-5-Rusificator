@echo off
chcp 65001 >nul
rem Russian localization for Disgaea 5: adds the "Russian" mod to D5 Mod Kit (uses the kit's own Python)
rem the kit: the parent folder (D5ModKit\Disgaea5-Russian), or one more up (the zip unpacked into its own folder)
set "KIT=%~dp0.."
if exist "%KIT%\d5lib\modsys.py" goto found
set "KIT=%~dp0..\.."
if exist "%KIT%\d5lib\modsys.py" goto found
echo.
echo D5 Mod Kit не найден рядом с этой папкой (%~dp0).
:ask
echo.
set "KIT="
set /p "KIT=Перетащите сюда папку D5 Mod Kit (или файл Start D5 Mod Kit.bat из неё) и нажмите Enter: "
if not defined KIT goto ask
set "KIT=%KIT:"=%"
if exist "%KIT%\d5lib\modsys.py" goto found
rem a file from the kit folder was dropped: take its folder
for %%I in ("%KIT%") do set "KIT=%%~dpI."
if exist "%KIT%\d5lib\modsys.py" goto found
echo Это не папка D5 Mod Kit: в ней нет d5lib\modsys.py. Нужна папка, где лежит Start D5 Mod Kit.bat.
goto ask
:found
set "PY=%KIT%\runtime\python.exe"
if exist "%PY%" goto run
rem a kit without its runtime folder (run from source) uses an installed Python
where python >nul 2>nul || (echo. & echo В папке кита нет runtime\python.exe. Скачайте D5 Mod Kit со страницы релизов: & echo https://github.com/eraser4521/D5ModKit/releases/latest & echo. & pause & exit /b 1)
set "PY=python"
:run
"%PY%" -X utf8 "%~dp0setup.py" "%KIT%"
echo.
pause
