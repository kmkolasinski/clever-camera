import remi.gui as gui
from remi import start, App

from history_widget import HistoryWidget
from settings import Settings


class MyApp(App):
    def __init__(self, *args):
        super(MyApp, self).__init__(*args)

    def main(self):
        tb = gui.TabBox(width="100%")
        history = HistoryWidget()
        settings = Settings()
        tb.add_tab(history, "History", None)
        tb.add_tab(settings, "Settings", None)
        return tb


if __name__ == "__main__":
    start(
        MyApp,
        title="MyCleverCamera",
        address="0.0.0.0",
        debug=True,
        port=4000,
        start_browser=False,
    )
