"""Entry point: wires up the single-instance lock, TimerApi, and the
pywebview window pointed at the static frontend."""
import os
import sys

import webview

import single_instance
from timer_api import TimerApi

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
STATIC_DIR = os.path.join(BASE_DIR, "..", "static")
LOCK_FILE = os.path.join(DATA_DIR, "timer.lock")


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
        webview.start(gui='edgechromium')
    finally:
        single_instance.release(LOCK_FILE)


if __name__ == '__main__':
    main()
