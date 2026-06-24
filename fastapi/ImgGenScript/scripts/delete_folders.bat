@echo off
cd /d "%~dp0\.."

REM ---- Configuration ----
set SCRIPT_NAME=scripts\delete_folders.py
set VENV_NAME=.venv
set VENV_ACTIVATE=%VENV_NAME%\Scripts\activate.bat

echo.
echo =======================================================
echo    OVOD fullbody/portrait Folder Cleaner
echo    Script: %SCRIPT_NAME%
echo =======================================================
echo.

REM --- 1. Check that the Python script exists ---
if not exist "%SCRIPT_NAME%" (
    echo ERROR: File "%SCRIPT_NAME%" not found in this folder.
    echo Make sure the Python script is in the same directory as this .bat file.
    goto :error_end
)

REM --- 2. Look for virtual environment or create it if missing ---
if exist "%VENV_ACTIVATE%" (
    echo Virtual environment "%VENV_NAME%" found.
) else (
    echo Virtual environment "%VENV_NAME%" not found. Creating it...
    python -m venv "%VENV_NAME%"
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        echo Please ensure Python is installed and available in PATH.
        goto :error_end
    )
    echo Virtual environment created successfully.
)

REM --- 3. Activate the virtual environment ---
call "%VENV_ACTIVATE%"
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    goto :error_end
)
echo Virtual environment activated.

REM --- 4. Run the cleaning script ---
echo.
echo Running %SCRIPT_NAME% ...
echo -------------------------------------------------------
python "%SCRIPT_NAME%"
if errorlevel 1 (
    echo.
    echo ERROR: Python script finished with errors.
    goto :error_end
)

goto :success_end

REM ===============================================================
:error_end
echo.
echo =======================================================
echo    ERROR: Process finished with errors.
echo =======================================================
echo.
pause
exit /b 1

:success_end
echo.
echo =======================================================
echo    SUCCESS: fullbody and portrait folders deleted successfully!
echo =======================================================
echo.
pause
exit /b 0