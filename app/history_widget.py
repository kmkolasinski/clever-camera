import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from PIL import Image
from natsort import natsorted
from remi import gui

from gui import PILImage, PILImageViewerWidget, CustomButton, HorizontalLine, Header

DATA_DIRECTORY = Path("data")
SNAPSHOTS_DIRECTORY = DATA_DIRECTORY / Path("snapshots")


def append_snapshots_history(
    image: PILImage,
    labels: List[str],
    class_filter: str,
    camera_name: str,
    image_change: float,
):
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    hour = now.strftime("%H:%M:%S")
    saveDir = SNAPSHOTS_DIRECTORY / str(date)
    saveDir.mkdir(exist_ok=True, parents=True)

    thumbnail = image.copy()
    thumbnail.thumbnail((224, 224))
    thumbnail_path = f"{saveDir}/thumbnail-{hour}.jpg"
    image_path = f"{saveDir}/image-{hour}.jpg"

    thumbnail.save(thumbnail_path)
    image.save(image_path)

    data = {
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "thumbnail_path": thumbnail_path,
        "image_path": image_path,
        "labels": labels,
        "class_filter": class_filter,
        "camera_name": camera_name,
        "image_change": image_change,
    }
    history_file = Path(f"{saveDir}/history.json")
    if history_file.exists():
        with history_file.open("r") as file:
            history = json.load(file)
    else:
        history = []

    history.append(data)
    with history_file.open("w") as file:
        json.dump(history, file, indent=2)
    print("History updated")


class HistoryRecordWidget(gui.Container):
    def __init__(self, *args):
        super(HistoryRecordWidget, self).__init__(*args)

        self.imageThumbnailWidget = PILImageViewerWidget(
            "./resources/sample_snapshot.jpg"
        )
        self.imageThumbnailWidget.load("./resources/sample_snapshot.jpg")
        self.labelsLabel = gui.Label("")
        self.dateLabel = gui.Label("")
        self.imageThumbnailWidget.set_size(224, 224)

        hl = gui.HBox()
        hl.append(self.imageThumbnailWidget)
        hl.append(self.dateLabel)
        hl.append(self.labelsLabel)

        self.append(hl)

    @staticmethod
    def from_config(config: Dict[str, Any]) -> "HistoryRecordWidget":
        widget = HistoryRecordWidget()
        thumbnail = Image.open(config["thumbnail_path"])
        widget.imageThumbnailWidget.set_image(thumbnail)
        widget.labelsLabel.set_text(", ".join(config["labels"]))
        widget.dateLabel.set_text(config["datetime"])
        return widget


class HistoryWidget(gui.Container):
    def __init__(self, *args):
        super(HistoryWidget, self).__init__(*args)
        self.css_width = "100%"
        self.container = gui.Container()
        self.container.style.update(
            {"display": "block", "overflow": "auto", "margin": "5px"}
        )
        self.container.set_layout_orientation(gui.Container.LAYOUT_VERTICAL)
        self.historyList = gui.ListView()
        self.container.append(self.historyList)
        self.reloadHistoryButton = CustomButton("Reload")

        hlayout = gui.HBox()
        hlayout.append(self.reloadHistoryButton)

        self.append(hlayout)
        self.append(Header("History"))
        self.append(HorizontalLine())
        self.append(self.container)

        # signals:
        self.reloadHistoryButton.onclick.do(self.reload_history)

    def reload_history(self, emitter=None):
        self.historyList.empty()
        widgets = load_history_widgets()
        for widget in widgets:
            self.historyList.append(widget)
            self.historyList.append(HorizontalLine())


def load_history_widgets():
    widgets = []
    folders = natsorted(SNAPSHOTS_DIRECTORY.glob("*"))
    for folder in folders:
        if not folder.is_dir():
            continue
        with (Path(folder) / "history.json").open("r") as file:
            day_history_list = json.load(file)[::-1]
        for day_config in day_history_list:
            widget = HistoryRecordWidget.from_config(day_config)
            widgets.append(widget)
    return widgets
