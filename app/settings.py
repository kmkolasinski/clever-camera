from pathlib import Path

import remi.gui as gui
import yaml
from remi import App

from camera_widget import CameraWidget
from gui import CustomButton

CONFIG_PATH = Path("resources/config.yaml")


class Settings(gui.Container):
    def __init__(self, app: App, *args):
        super(Settings, self).__init__(*args)
        self.app_instance = app
        self.saveSettings = CustomButton("Save Settings")
        self.saveSettings.set_size(300, 40)
        self.cameraWidget = CameraWidget(app)
        mainLayout = gui.VBox()

        buttonLayout = gui.HBox()
        buttonLayout.append(self.saveSettings)
        mainLayout.append(self.cameraWidget)
        self.append(mainLayout)
        self.append(buttonLayout)
        self.load_settings()
        # signals
        self.saveSettings.onclick.do(self.save_settings)

    def save_settings(self, emitter=None):
        camera_config = self.cameraWidget.get_settings()
        config = {"camera": camera_config}
        with CONFIG_PATH.open("w") as file:
            yaml.dump(config, file)

    def load_settings(self):
        if not CONFIG_PATH.exists():
            return False
        with CONFIG_PATH.open("r") as file:
            config = yaml.load(file, Loader=yaml.Loader)

        self.cameraWidget.set_settings(config["camera"])
