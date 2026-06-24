@echo off
REM Change to the directory where this .bat script is located
cd /d "%~dp0"

REM Define the name of the virtual environment
set VENV_NAME=.venv
set VENV_PATH=%VENV_NAME%\Scripts\activate.bat

REM --- 1. Look for the virtual environment and create it if it doesn't exist ---
IF EXIST "%VENV_PATH%" (
    echo Virtual environment "%VENV_NAME%" found.
) ELSE (
    echo Virtual environment "%VENV_NAME%" not found. Creating...
    python -m venv %VENV_NAME%
    IF ERRORLEVEL 1 (
        echo ERROR: Failed to create the virtual environment "%VENV_NAME%".
        echo Make sure Python is in your PATH and you have permissions.
        goto :error_end
    )
    IF NOT EXIST "%VENV_PATH%" (
        echo ERROR: Failed to create the virtual environment "%VENV_NAME%". The activation directory or file was not created.
        goto :error_end
    )
    echo Virtual environment "%VENV_NAME%" created successfully.
)

REM --- 2. Activate the virtual environment ---
call "%VENV_PATH%"
IF ERRORLEVEL 1 (
    echo ERROR: Failed to activate the virtual environment "%VENV_NAME%".
    goto :error_end
)
echo Virtual environment activated.

REM --- 3. Install requirements if the file exists ---
IF EXIST "requirements.txt" (
    echo Installing/Verifying dependencies from requirements.txt...
    pip install -r requirements.txt
    IF ERRORLEVEL 1 (
        echo ERROR: Failed to install dependencies from requirements.txt.
        goto :error_end
    )
    echo Dependencies installed/verified.
) ELSE (
    echo Warning: requirements.txt not found. Skipping dependency installation.
)

REM --- 4. Run the main script ---
echo Running the application...
python main.py
IF ERRORLEVEL 1 (
    echo ERROR: Failed to run 'python main.py'.
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