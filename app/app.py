import remi.gui as gui
from remi import start, App
from config import Config
from history_widget import HistoryWidget
from settings import Settings


class CleverCameraApp(App):
    def __init__(self, *args):
        super(CleverCameraApp, self).__init__(*args)

    def main(self):
        tabs = gui.TabBox(width="100%")
        history = HistoryWidget()
        settings = Settings(self)
        tabs.add_tab(history, "History", None)
        tabs.add_tab(settings, "Settings", None)
        Config.APP_INSTANCE = self
        return tabs


if __name__ == "__main__":
    start(
        CleverCameraApp,
        title="Clever-Camera",
        address="0.0.0.0",
        debug=True,
        port=4000,
        start_browser=False,
        enable_file_cache=True,
    )
