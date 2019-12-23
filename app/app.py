from pathlib import Path

import remi.gui as gui
from remi import start, App
from config.config import Config
import config.styles as css
from core.history_widget import HistoryWidget
from core.settings_widget import AppSettingsWidget


class CleverCameraApp(App):
    def __init__(self, *args):
        resources_path = Path(Path(__file__).absolute().parent) / "static"
        super(CleverCameraApp, self).__init__(
            *args, static_file_path={"static": resources_path}
        )

    def main(self):
        # Keep application instance in the global shared variable
        Config.APP_INSTANCE = self
        # add bootstrap
        self.page.children["head"].add_child("additional_head_data", css.HTML_HEAD)

        tabs = gui.TabBox(width="95%")
        css.apply_styles(tabs, css.APP_TABS_CSS)

        history = HistoryWidget()
        settings = AppSettingsWidget(width="100%")
        tabs.add_tab(history, "Events history", None)
        tabs.add_tab(settings, "Settings", None)
        tabs.select_by_index(1)
        return tabs


if __name__ == "__main__":
    start(
        CleverCameraApp,
        title="Clever-Camera",
        address="0.0.0.0",
        username=Config.APP_USERNAME,
        password=Config.APP_PASSWORD,
        debug=True,
        port=Config.APP_PORT,
        start_browser=False,
        enable_file_cache=True,
    )
