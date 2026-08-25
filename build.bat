@echo off
REM Rebuilds dist\TaskGaugePro\TaskGaugePro.exe from source.
REM Uses the "TimeTracker" conda env, which has pyinstaller + pywebview installed.
REM After rebuilding, your data\ folder next to the exe is untouched.

"C:\Users\Mardavij\.conda\envs\TimeTracker\Scripts\pyinstaller.exe" ^
  --name "TaskGaugePro" ^
  --onedir ^
  --windowed ^
  --icon "d:\category2_Self_Development\Timer_app\static\assets\icon.ico" ^
  --add-data "d:\category2_Self_Development\Timer_app\static;static" ^
  --distpath "dist" ^
  --workpath "build" ^
  --specpath "build" ^
  --noconfirm ^
  src\app.py
