# -*- coding: utf-8 -*-
"""CLI end-to-end with fake capture: run main() for 8s then stop gracefully."""
import os
import sys
import time
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from realtime_translation.__main__ import main

stop_flag = threading.Event()


def stopper():
    stop_flag.wait(timeout=10)
    # simulate Ctrl+C on the main thread by raising in it via signal-free way:
    os._exit(0)  # hard fallback — should not be reached


def watchdog():
    # after 10s, dump & exit
    time.sleep(10)
    print("[watchdog] timeout reached — hardening exit", flush=True)
    os._exit(3)


threading.Thread(target=watchdog, daemon=True).start()

print("=== starting main (fake, no-tui, translate=off) ===", flush=True)
sys.argv = ["mt", "--fake", "--no-tui", "--translate", "off", "--output", "data"]
try:
    main()
except KeyboardInterrupt:
    print("KeyboardInterrupt caught by main handler — graceful", flush=True)
