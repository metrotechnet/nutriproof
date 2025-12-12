@echo off
:: Ground Truth Processing Scripts
:: Choose which processing script to run

echo.
echo ============================================
echo  Ground Truth Processing Scripts
echo ============================================
echo.
echo Choose an option:
echo.
echo 1. Full OCR Processing (processes all PDFs from scratch)
echo 2. Update Existing Tables (updates Temps/Visite in existing table files)
echo 3. Exit
echo.
set /p choice="Enter your choice (1-3): "

if "%choice%"=="1" goto full_processing
if "%choice%"=="2" goto update_tables
if "%choice%"=="3" goto exit
goto invalid_choice

:full_processing
echo.
echo ============================================
echo  Starting Full OCR Processing...
echo ============================================
echo.
echo This will:
echo - Find all PDF files in D:\Nutriss\ground_truth
echo - Process OCR on all pages
echo - Extract Temps and Visite fields
echo - Create table_page_xx.json files
echo.
pause
python ground_truth_processor.py
goto end

:update_tables
echo.
echo ============================================
echo  Starting Table Update...
echo ============================================
echo.
echo This will:
echo - Find existing table_page_xx.json files
echo - Re-extract Temps and Visite fields
echo - Update the table files with new values
echo.
pause
python update_ground_truth_tables.py
goto end

:invalid_choice
echo.
echo Invalid choice. Please enter 1, 2, or 3.
echo.
pause
goto start

:exit
echo Exiting...
goto end

:end
echo.
echo Processing completed!
pause