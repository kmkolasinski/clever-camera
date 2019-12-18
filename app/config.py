from pathlib import Path
from remi import App


class Config:
    APP_INSTANCE: App = None
    DATA_DIRECTORY = Path("data")
    SNAPSHOTS_DIRECTORY = DATA_DIRECTORY / Path("snapshots")
    CONFIG_PATH = Path("resources/config.yaml")
    THUMBNAIL_SIZE = (224, 224)
    MINI_THUMBNAIL_SIZE = (128, 128)
    CAMERA_DEFAULT_IMAGE = "./resources/sample_snapshot.jpg"
