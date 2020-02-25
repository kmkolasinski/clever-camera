import threading
from datetime import datetime
import psutil
import remi.gui as gui
import core.widgets as wg
import multiprocessing
import os

LABEL_WIDTH = "15%"
UPDATE_FREQUENCY_SEC = 30


class SystemResourcesWidget(gui.VBox):
    def __init__(self, *args, **kwargs):
        super(SystemResourcesWidget, self).__init__(*args, **kwargs)
        self.ssh_tunnel_thread = None
        self.http_tunnel_thread = None
        self.last_update = datetime.now()
        self.refresh_btn = wg.SButton("Refresh", "fa-sync-alt", "btn-primary")
        self.open_ssh_tunnel_btn = wg.SButton("Open SSH tunnel", "fa-wifi", "btn-primary")
        self.open_http_tunnel_btn = wg.SButton("Open HTTP tunnel", "fa-wifi", "btn-primary")

        self.others = wg.SettingsWidget("Other parameters", LABEL_WIDTH)
        self.others.add_text_field(f"boot_time", f"Boot time")
        self.append(self.others)
        self.append(self.others.settings)

        self.cpu_usage = wg.SettingsWidget("CPU usage", LABEL_WIDTH)
        for cpu in range(psutil.cpu_count()):
            self.cpu_usage.add_progress_bar(f"cpu-{cpu}", f"CPU-{cpu+1}")
        self.append(self.cpu_usage)  # add title
        self.append(self.cpu_usage.settings)  # add progress bars

        self.ram_usage = wg.SettingsWidget("Memory usage", LABEL_WIDTH)
        self.ram_usage.add_progress_bar(f"ram", f"RAM [%]")
        self.append(self.ram_usage)
        self.append(self.ram_usage.settings)

        self.disk_usage = wg.SettingsWidget("Disk usage", LABEL_WIDTH)
        self.disk_usage.add_progress_bar(f"disk", f"Disk usage [%]")
        self.append(self.disk_usage)
        self.append(self.disk_usage.settings)
        self.append(self.refresh_btn)
        self.append(self.open_ssh_tunnel_btn)
        self.append(self.open_http_tunnel_btn)

        self.refresh_btn.onclick.do(self.update_thread_fn)
        self.open_ssh_tunnel_btn.onclick.do(self.open_ssh_tunnel)
        self.open_http_tunnel_btn.onclick.do(self.open_http_tunnel)

    def update_thread_fn(self, emitter=None):
        cpu_usage = psutil.cpu_percent(interval=1, percpu=True)
        for cpu, usage in enumerate(cpu_usage):
            self.cpu_usage[f"cpu-{cpu}"].set_value(usage)

        self.ram_usage["ram"].set_value(psutil.virtual_memory().percent)
        self.disk_usage["disk"].set_value(psutil.disk_usage("/").percent)
        secs = psutil.boot_time()
        boot_date = datetime.fromtimestamp(secs)
        dt = datetime.now() - boot_date
        boot_time = boot_date.strftime("%Y-%m-%d %H:%M:%S")
        self.others["boot_time"].set_value(f"{boot_time} (since {dt.days} days)")

    def update(self):
        delta = datetime.now() - self.last_update
        if delta.total_seconds() > UPDATE_FREQUENCY_SEC:
            camera_thread = threading.Thread(target=self.update_thread_fn)
            camera_thread.start()
            self.last_update = datetime.now()

    def open_ssh_tunnel(self, emitter=None):
        if self.ssh_tunnel_thread is not None:
            return False

        def thread_fn():
            cmd = "ngrok tcp 22"
            os.system(cmd)

        print("Starting ssh tunnel ... ")
        self.ssh_tunnel_thread = multiprocessing.Process(target=thread_fn)
        self.ssh_tunnel_thread.start()

    def open_http_tunnel(self, emitter=None):
        if self.http_tunnel_thread is not None:
            return False

        def thread_fn():
            cmd = "ngrok http 4000"
            os.system(cmd)

        print("Starting http tunnel ... ")
        self.http_tunnel_thread = multiprocessing.Process(target=thread_fn)
        self.http_tunnel_thread.start()
