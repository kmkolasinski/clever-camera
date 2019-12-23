from pathlib import Path
from typing import List, Dict, Any, Optional

import yaml
from remi import App
import os


DAY_FORMAT = "%Y-%m-%d"
HOUR_FORMAT = "%H:%M:%S"
DATE_FORMAT = f"{DAY_FORMAT} {HOUR_FORMAT}"


class Config:
    APP_INSTANCE: App = None
    APP_USERNAME: Optional[str] = os.environ.get("APP_USERNAME")
    APP_PASSWORD: Optional[str] = os.environ.get("APP_PASSWORD")
    APP_PORT: int = 4000
    DATA_DIR = Path("data")
    MODELS_DIR = Path("models")
    STATIC_DATA_DIR = Path("app/static")
    SNAPSHOTS_DIR = DATA_DIR / Path("snapshots")
    CONFIG_PATH = Path("data/settings.yaml")
    CAMERA_SNAPSHOT_PREVIEW_SIZE = (1440, 1080)
    THUMBNAIL_SIZE = (224, 224)
    MINI_THUMBNAIL_SIZE = (128, 128)
    CAMERA_DEFAULT_IMAGE = STATIC_DATA_DIR / "images/placeholder.jpg"
    FONT_PATH = STATIC_DATA_DIR / "fonts/InputSans-Regular.ttf"
    LOGGER_HISTORY_SIZE = 5

    @staticmethod
    def list_models() -> List[str]:
        return list(p.name for p in Config.MODELS_DIR.glob("*"))

    @staticmethod
    def dump_config(config: Dict[str, Any]):
        """Dump application config (camera parameters etc) to settings.yml """
        with Config.CONFIG_PATH.open("w") as file:
            yaml.dump(config, file)

    @staticmethod
    def load_config() -> Optional[Dict[str, Any]]:
        if not Config.CONFIG_PATH.exists():
            return None
        with Config.CONFIG_PATH.open("r") as file:
            config = yaml.load(file, Loader=yaml.Loader)
        return config
