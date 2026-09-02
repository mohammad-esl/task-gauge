"""Entry point: wires up the single-instance lock, TimerApi, and the
pywebview window pointed at the static frontend."""
import os
import sys
import time

import webview

import single_instance
from timer_api import TimerApi

FROZEN = getattr(sys, "frozen", False)

# DATA_DIR always points at data/ under the project root (D:\category2_Self_Development\Timer_app\data),
# never a copy next to the built exe in dist\. dist\TaskGaugePro\ is rebuilt/wiped on every
# build.bat run, so any data\ living there is disposable; the project-root data\ is the
# single persistent store both the dev run and the built exe read from and write to.
PROJECT_ROOT = "D:\\category2_Self_Development\\Timer_app"
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

if FROZEN:
    # Built exe: bundled read-only assets (static/) are unpacked under sys._MEIPASS.
    STATIC_DIR = os.path.join(sys._MEIPASS, "static")
else:
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    STATIC_DIR = os.path.join(SRC_DIR, "..", "static")

LOCK_FILE = os.path.join(DATA_DIR, "timer.lock")
ICON_FILE = os.path.join(STATIC_DIR, "assets", "icon.ico")


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    if not single_instance.acquire(LOCK_FILE):
        sys.exit(0)

    try:
        api = TimerApi(DATA_DIR, static_dir=STATIC_DIR)
        window = webview.create_window(
            'Task Gauge Pro',
            url=os.path.join(STATIC_DIR, "index.html"),
            js_api=api,
            width=780,
            height=740,
            resizable=False,
        )

        def save_on_close():
            # Without this, closing the window loses whatever time has
            # accumulated on the active session(s) since the last save
            # (category switch, day rollover, or the 5-minute autosave).
            now = time.time()
            api._finalize_active_session(now)
            api._finalize_second_session(now)
            api.save_config()

        window.events.closing += save_on_close

        webview.start(gui='edgechromium', icon=ICON_FILE if os.path.isfile(ICON_FILE) else None)
    finally:
        single_instance.release(LOCK_FILE)


if __name__ == '__main__':
    main()
