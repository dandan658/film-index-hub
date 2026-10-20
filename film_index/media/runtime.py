"""Reload media settings without spawning another server or application."""
from pathlib import Path
from threading import Lock, Timer

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


def watch_configuration():
    from film_index.media.config import Config
    from film_index.media.app.utils.commons import INSTANCES
    from film_index.media.app.scheduler import restart_scheduler
    from film_index.media.app.sync import restart_monitor
    guard = Lock()

    def reload():
        with guard:
            Config().init_config()
            for instance in list(INSTANCES.values()):
                if hasattr(instance, 'init_config'):
                    instance.init_config()
            restart_scheduler()
            restart_monitor()

    class SettingsEvents(FileSystemEventHandler):
        timer = None

        def on_any_event(self, event):
            path = getattr(event, 'dest_path', '') or event.src_path
            if event.is_directory or Path(path).name != 'config.yaml' or event.event_type not in ('modified', 'moved', 'created'):
                return
            if self.timer:
                self.timer.cancel()
            self.timer = Timer(.5, reload)
            self.timer.daemon = True
            self.timer.start()

    handler = SettingsEvents()
    observer = Observer(timeout=10)
    observer.schedule(handler, Config().get_config_path(), recursive=False)
    observer.start()

    def stop():
        if handler.timer:
            handler.timer.cancel()
        observer.stop()
        observer.join(timeout=3)

    return stop
