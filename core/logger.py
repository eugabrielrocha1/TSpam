"""
CyberTG – Thread-safe Logger
Queues log messages for the GUI to consume.
"""
import queue
import csv
import os
from datetime import datetime

LOG_LEVELS = {
    "INFO":    "🔵",
    "SUCCESS": "🟢",
    "WARNING": "🟡",
    "ERROR":   "🔴",
}


class Logger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._queue = queue.Queue()
            cls._instance._history = []
        return cls._instance

    def log(self, message: str, level: str = "INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        icon = LOG_LEVELS.get(level, "⚪")
        entry = {
            "timestamp": ts,
            "level": level,
            "icon": icon,
            "message": message,
            "full": f"[{ts}] {icon} [{level}] {message}"
        }
        self._history.append(entry)
        self._queue.put(entry)

    def info(self, msg):
        self.log(msg, "INFO")

    def success(self, msg):
        self.log(msg, "SUCCESS")

    def warning(self, msg):
        self.log(msg, "WARNING")

    def error(self, msg):
        self.log(msg, "ERROR")

    def drain(self):
        """Drain all pending messages from the queue."""
        entries = []
        while not self._queue.empty():
            try:
                entries.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return entries

    def get_history(self):
        return list(self._history)

    def clear(self):
        self._history.clear()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def export_txt(self, filepath: str):
        with open(filepath, "w", encoding="utf-8") as f:
            for entry in self._history:
                f.write(entry["full"] + "\n")

    def export_csv(self, filepath: str):
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Level", "Message"])
            for entry in self._history:
                writer.writerow([entry["timestamp"], entry["level"], entry["message"]])


logger = Logger()
