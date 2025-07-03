@echo off
REM === Activate virtual environment if any ===
IF EXIST venv\Scripts\activate.bat (
    CALL venv\Scripts\activate.bat
)

REM === Run the backend server ===
python backend\main.py

REM === Optionally open browser (uncomment to use) ===
:: START "" http://localhost:5000

PAUSE
