"""Filesystem watcher helper (moved to vibe.services).

Copy of the original watcher implementation.
"""
from typing import Callable
import threading


def start_watcher(path: str, on_change: Callable[[str], None]):
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class Handler(FileSystemEventHandler):
            def on_modified(self, event):
                if not event.is_directory:
                    on_change(event.src_path)

        observer = Observer()
        handler = Handler()
        observer.schedule(handler, path=path, recursive=True)
        observer.start()

        def stop():
            observer.stop()
            observer.join()

        return stop
    except Exception:
        def stop_noop():
            return None

        return stop_noop
