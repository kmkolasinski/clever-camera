import threading
from datetime import datetime

import remi.gui as gui

from config.config import Config
from core.camera_widget import CameraWidget, EVENTS_SEQUENCE_SEPARATION
from core.history_widget import (
    load_day_history,
    string_to_datetime,
)
from core.widgets import HorizontalLine, SButton, EmailNotifierWidget


class AppSettingsWidget(gui.Container):
    def __init__(self, *args, **kwargs):
        super(AppSettingsWidget, self).__init__(*args, **kwargs)

        self.save_btn = SButton("Save settings", "fa-save", "btn btn-primary")
        self.save_btn.css_width = "300px"
        self.save_btn.css_margin = "5px auto"
        self.email_notifier_widget = EmailNotifierWidget(width="100%")
        self.camera_widget = CameraWidget(width="100%")

        cam_layout = gui.VBox()
        cam_layout.append(self.camera_widget)

        layout = gui.VBox(width="100%")
        layout.css_display = "block"
        layout.append(self.email_notifier_widget)
        layout.append(self.save_btn)

        self.append(HorizontalLine())
        self.append(cam_layout)
        self.append(layout)

        self.load_settings()
        # signals
        self.save_btn.onclick.do(self.save_settings)
        self.email_notifier_widget.on_send_message.do(self.send_test_notification)
        self.camera_widget.on_events_sequence_finished.do(self.maybe_send_notification)

        # autostarting camera thread
        if self.camera_widget.is_auto_start_enabled:
            print("Camera auto start enabled, starting monitoring ...")
            self.camera_widget.reload_camera_connection()
            self.camera_widget.start_monitoring()

    def send_test_notification(self, emitter=None):
        snapshot = self.camera_widget.latest_camera_snapshot
        snapshot.save("/tmp/snapshot.jpg")
        self.email_notifier_widget.send_notification_message(
            title="Test message",
            attachments=["/tmp/snapshot.jpg"],
            contents=["This is an example camera snapshot"],
            do_checks=False,
        )

    def maybe_send_notification(self, emitter=None):

        if self.email_notifier_widget.cannot_send_email():
            return False

        now = datetime.now()
        history = load_day_history(date=now)
        if len(history) == 0:
            return False

        # scan history for sequence of co-occurring events
        records_sequence = []
        last_record_date = string_to_datetime(history[0]["datetime"])
        for record in history:
            event_date = string_to_datetime(record["datetime"])
            dt = last_record_date - event_date
            if dt.total_seconds() < EVENTS_SEQUENCE_SEPARATION:
                records_sequence.append(record)
                last_record_date = event_date
            else:
                break

        if len(records_sequence) == 0:
            return False

        def send_email_thread_fn():
            labels = []
            for r in records_sequence:
                labels += r["labels"]

            start = string_to_datetime(records_sequence[0]["datetime"])
            end = string_to_datetime(records_sequence[-1]["datetime"])
            event_length = int((end - start).total_seconds())
            self.email_notifier_widget.send_notification_message(
                title=f"Detected labels {set(labels)}",
                attachments=[r["image_path"] for r in records_sequence],
                contents=[
                    f"Detected {len(records_sequence)} events of total "
                    f"time {event_length} seconds. Following labels "
                    f"have been detected {set(labels)}"
                ],
                do_checks=True,
            )

        send_email_thread = threading.Thread(target=send_email_thread_fn)
        send_email_thread.start()

    def save_settings(self, emitter=None):
        """
        Dump camera settings to YAML file
        """
        camera_config = self.camera_widget.get_settings()
        email_settings = self.email_notifier_widget.get_settings()
        Config.dump_config(
            {
                "camera_settings": camera_config,
                "email_notification_settings": email_settings,
            }
        )

    def load_settings(self) -> None:
        """
        Load camera settings form config
        """
        config = Config.load_config()
        if config is None:
            return
        self.camera_widget.set_settings(config["camera_settings"])
        self.email_notifier_widget.set_settings(config["email_notification_settings"])
