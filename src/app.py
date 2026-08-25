"""Entry point: wires up the single-instance lock, TimerApi, and the
pywebview window pointed at the static frontend."""
import os
import sys

import webview

import single_instance
from timer_api import TimerApi

FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    # Built exe: bundled read-only assets (static/) are unpacked under
    # sys._MEIPASS, but data must live next to the exe so it persists
    # across runs instead of vanishing with the temp bundle dir.
    EXE_DIR = os.path.dirname(sys.executable)
    STATIC_DIR = os.path.join(sys._MEIPASS, "static")
    DATA_DIR = os.path.join(EXE_DIR, "data")
else:
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    STATIC_DIR = os.path.join(SRC_DIR, "..", "static")
    DATA_DIR = os.path.join(SRC_DIR, "..", "data")

LOCK_FILE = os.path.join(DATA_DIR, "timer.lock")
ICON_FILE = os.path.join(STATIC_DIR, "assets", "icon.ico")


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    if not single_instance.acquire(LOCK_FILE):
        sys.exit(0)

    try:
        api = TimerApi(DATA_DIR)
        window = webview.create_window(
            'Task Gauge Pro',
            url=os.path.join(STATIC_DIR, "index.html"),
            js_api=api,
            width=780,
            height=740,
            resizable=False,
        )
        webview.start(gui='edgechromium', icon=ICON_FILE if os.path.isfile(ICON_FILE) else None)
    finally:
        single_instance.release(LOCK_FILE)


if __name__ == '__main__':
    main()
