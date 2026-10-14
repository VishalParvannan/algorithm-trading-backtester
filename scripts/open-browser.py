"""Open the dashboard only after its local server is ready."""
import argparse
import json
import time
from urllib.request import urlopen
import webbrowser


def wait_ready(address, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(address + '/health', timeout=2) as response:
                health = json.load(response)
            if health.get('status') == 'ok' and health.get('engine_version'):
                return True
        except (OSError, ValueError):
            pass
        time.sleep(.5)
    return False


def launch(port):
    address = f'http://127.0.0.1:{port}'
    if not wait_ready(address):
        return 'The server did not become ready. Check the Backtest Lab window for its startup error.'
    if not webbrowser.open(address):
        return f'Could not open your browser automatically. Open {address} manually.'
    return None


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    options = parser.parse_args()
    error = launch(options.port)
    if error:
        try:
            import tkinter
            from tkinter import messagebox
            root = tkinter.Tk(); root.withdraw()
            messagebox.showerror('Backtest Lab', error)
            root.destroy()
        except Exception:
            pass
