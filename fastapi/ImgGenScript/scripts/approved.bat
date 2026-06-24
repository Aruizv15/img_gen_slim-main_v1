@echo off
cd /d "%~dp0\.."

REM ---- Configuration ----
set SCRIPT_NAME=scripts\approved.py
set VENV_NAME=.venv
set VENV_ACTIVATE=%VENV_NAME%\Scripts\activate.bat

REM --- 1. Check that the Python script exists ---
IF not EXIST "%SCRIPT_NAME%" (
    echo ERROR: File "%SCRIPT_NAME%" not found in this folder.
    echo Make sure the Python script is in the same directory as this .bat file.
    goto :error_end
)

REM --- 2. Look for virtual environment or create it if missing ---
IF EXIST "%VENV_ACTIVATE%" (
    echo Virtual environment "%VENV_NAME%" found.
) else (
    echo Virtual environment "%VENV_NAME%" not found. Creating it...
    python -m venv "%VENV_NAME%"
    IF errorlevel 1 (
        echo ERROR: Failed to create the virtual environment "%VENV_NAME%".
        echo Make sure Python is in your PATH and you have permissions.
        goto :error_end
    )
    IF NOT EXIST "%VENV_ACTIVATE%" (
        echo ERROR: Failed to create the virtual environment "%VENV_NAME%". The activation directory or file was not created.
        goto :error_end
    )
    echo Virtual environment "%VENV_NAME%" created successfully.
)

REM --- 3. Activate the virtual environment ---
call "%VENV_ACTIVATE%"
if errorlevel 1 (
    echo ERROR: Failed to activate the virtual environment "%VENV_NAME%".
    goto :error_end
)
echo Virtual environment activated.

REM --- 4. Run the script ---
echo Running the application...
python "%SCRIPT_NAME%"
IF ERRORLEVEL 1 (
    echo ERROR: Python script finished with errors.
    goto :error_end
)

goto :success_end

REM --- Error handling and exit ---

:error_end
echo.
echo =======================================================
echo !!! The script has finished with an ERROR. !!!
echo =======================================================
echo.
pause
goto :eof

:success_end
echo.
echo =======================================================
echo !!! The script has finished successfully. !!!
echo =======================================================
echo.
pause
goto :eof