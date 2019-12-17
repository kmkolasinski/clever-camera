import remi.gui as gui
from remi import start, App

from config import Config
from gui import BUTTON_STYLE
from history_widget import HistoryWidget
from settings import Settings

# custom css
my_css_head = """
            <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css">
            """
# custom js
my_js_head = """
            <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.3.1/jquery.min.js"></script>
            <script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/js/bootstrap.min.js"></script>
            """


class MyApp(App):
    def __init__(self, *args):
        super(MyApp, self).__init__(*args)

    def setup_styles(self):
        self.page.children["head"].add_child("mycss", my_css_head)
        self.page.children["head"].add_child("myjs", my_js_head)

    def main(self):
        # self.setup_styles()
        tb = gui.TabBox(width="100%")
        history = HistoryWidget()
        settings = Settings(self)
        tb.add_tab(history, "History", None)
        tb.add_tab(settings, "Settings", None)
        Config.APP_INSTANCE = self
        return tb


if __name__ == "__main__":
    start(
        MyApp,
        title="MyCleverCamera",
        address="0.0.0.0",
        debug=True,
        port=4000,
        start_browser=False,
        enable_file_cache=True,
    )
