@echo off
REM Rebuilds dist\TaskGaugePro\TaskGaugePro.exe from source.
REM Uses the "TimeTracker" conda env, which has pyinstaller + pywebview installed.
REM WARNING: --noconfirm wipes and recreates the whole dist\TaskGaugePro\ folder,
REM including any data\ next to the exe. Re-copy data\ after every rebuild.
REM PATH is forced so TimeTracker's own DLLs (Library\bin) win over any other
REM conda install (e.g. miniconda3\Library\bin) that also ships libssl/libcrypto
REM under the same filename but a different version -- PyInstaller's dependency
REM scanner picks whichever copy PATH resolves first, silently bundling a
REM mismatched DLL that fails with "DLL load failed while importing _ssl" at runtime.
set "PATH=C:\Users\Mardavij\.conda\envs\TimeTracker;C:\Users\Mardavij\.conda\envs\TimeTracker\Library\bin;C:\Users\Mardavij\.conda\envs\TimeTracker\Scripts;%PATH%"

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
