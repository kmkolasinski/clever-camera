import json
import os
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Union, Tuple, Optional
from io import StringIO, BytesIO
from PIL import Image
import zipfile
from natsort import natsorted
from remi import gui

from config import Config
from gui import (
    PILImage,
    StaticPILImageWidget,
    CustomButton,
    HorizontalLine,
    Header,
    PILImageWidget,
    CustomFormWidget,
    SMALL_BUTTON_STYLE,
)

DAY_FORMAT = "%Y-%m-%d"


def append_snapshots_history(
    image: PILImage,
    labels: List[str],
    class_filter: str,
    camera_name: str,
    image_change: float,
):
    now = datetime.now()
    date = now.strftime(DAY_FORMAT)
    hour = now.strftime("%H:%M:%S")
    saveDir = Config.SNAPSHOTS_DIRECTORY / str(date)
    saveDir.mkdir(exist_ok=True, parents=True)

    thumbnail = image.copy()
    thumbnail.thumbnail(Config.THUMBNAIL_SIZE)
    thumbnail_path = f"{saveDir}/thumbnail-{hour}.jpg"
    image_path = f"{saveDir}/image-{hour}.jpg"

    thumbnail.save(thumbnail_path)
    image.save(image_path)

    data = {
        "datetime": now.strftime(f"{DAY_FORMAT} %H:%M:%S"),
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

        self.imagePath = None
        self.imageThumbnailWidget = StaticPILImageWidget(None)
        self.labelsLabel = gui.Label("")
        self.dateLabel = gui.Label("")
        self.downloadImageButton = CustomButton("Download")
        self.imageThumbnailWidget.set_size(*Config.MINI_THUMBNAIL_SIZE)
        self.selectSnapshotCheckBox = gui.CheckBox()

        self.labelsLabel.css_width = "20%"
        self.dateLabel.css_width = "20%"

        hl = gui.HBox()
        hl.append(self.selectSnapshotCheckBox)
        hl.append(self.imageThumbnailWidget)
        hl.append(self.labelsLabel)
        hl.append(self.dateLabel)
        hl.append(self.downloadImageButton)
        self.layout = hl
        self.append(hl)

        # signals
        self.downloadImageButton.onclick.do(self.on_download_image)
        self.imageThumbnailWidget.onclick.do(self.on_download_image)
        self.selectSnapshotCheckBox.onclick.do(self.checkbox_toggled)

    @staticmethod
    def from_config(config: Dict[str, Any]) -> "HistoryRecordWidget":
        widget = HistoryRecordWidget()
        thumbnail = Image.open(config["thumbnail_path"])
        widget.imageThumbnailWidget.set_image(thumbnail)
        widget.labelsLabel.set_text(", ".join(config["labels"]))
        widget.dateLabel.set_text(config["datetime"])
        widget.imagePath = config["image_path"]
        return widget

    def on_download_image(self, emitter):
        Config.APP_INSTANCE.execute_javascript(
            f'window.location = "/{id(self)}/direct_download"'
        )

    def direct_download(self):
        with open(self.imagePath, "r+b") as f:
            content = f.read()
            headers = {
                "Content-type": "image/jpeg",
                "Content-Disposition": 'attachment; filename="%s"'
                % os.path.basename(self.imagePath),
            }
            return [content, headers]

    def is_selected(self) -> bool:
        return self.selectSnapshotCheckBox.get_value()

    def set_selected(self, toggle: bool):
        self.selectSnapshotCheckBox.set_value(toggle)

    def checkbox_toggled(self, emitter: gui.CheckBox):
        is_selected = not emitter.get_value()
        emitter.set_value(is_selected)
        self.layout.css_background_color = "#8bc34a7a" if is_selected else "#fff"
        self.layout.redraw()


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
        self.labelsList = gui.ListView()
        self.container.append(self.historyList)

        self.reloadHistoryButton = CustomButton("Search")
        todays_date = datetime.now().strftime(DAY_FORMAT)
        self.searchFromDay = gui.Date(todays_date)
        self.searchToDay = gui.Date(todays_date)
        self.filterByLabel = gui.TextInput()
        self.filterByLabel.set_text("*")
        self.searchInfoLabel = gui.Label("Search info ...")
        self.downloadSelectedImagesButton = CustomButton("Download selected")
        self.selectAllImagesButton = CustomButton("Select All")
        self.deSelectAllImagesButton = CustomButton("Deselect All")

        searchFormWidget = CustomFormWidget()
        searchFormWidget.css_width = "50%"
        searchFormWidget.add_field_with_label(
            "select_from_day", "Search from", self.searchFromDay
        )
        searchFormWidget.add_field_with_label(
            "select_to_day", "Search to", self.searchToDay
        )
        searchFormWidget.add_field_with_label(
            "search_by_label", "Filter by label", self.filterByLabel
        )
        searchFormWidget.add_field_with_label("reload", "", self.reloadHistoryButton)

        formLayout = gui.VBox()
        formLayout.append(searchFormWidget)

        selectionLayout = gui.HBox()
        selectionLayout.style.update({"display": "inline-flex", "margin": "5px"})

        selectionLayout.append(self.downloadSelectedImagesButton)
        selectionLayout.append(self.selectAllImagesButton)
        selectionLayout.append(self.deSelectAllImagesButton)

        self.append(HorizontalLine())
        self.append(formLayout)
        self.append(selectionLayout)
        self.append(self.searchInfoLabel)
        self.append(HorizontalLine())
        self.append(self.labelsList)
        self.append(HorizontalLine())
        self.append(HorizontalLine())
        self.append(self.container)
        self.append(HorizontalLine())

        # signals:
        self.reloadHistoryButton.onclick.do(self.reload_history)
        self.downloadSelectedImagesButton.onclick.do(self.on_download_images)
        self.selectAllImagesButton.onclick.do(self.select_all_images)
        self.deSelectAllImagesButton.onclick.do(self.deselect_all_images)

    def reload_history(self, emitter=None, search_button=None):
        self.historyList.empty()
        self.labelsList.empty()

        widgets, labels, msg = load_history_widgets(
            start_date=self.searchFromDay.get_value(),
            end_date=self.searchToDay.get_value(),
            labels_filter=self.filterByLabel.get_text(),
        )
        if widgets is None:
            self.searchInfoLabel.set_text(f"Error: {msg}")
            return False

        search_label = None if search_button is None else search_button.label

        num_images = 0
        for widget in widgets:
            image_labels = [w.strip() for w in widget.labelsLabel.get_text().split(",")]
            if search_label is None or search_label in image_labels:
                self.historyList.append(widget)
                self.historyList.append(HorizontalLine())
                num_images += 1

        self.searchInfoLabel.set_text(
            f"Found {num_images} events. Search label: '{search_label}'"
        )

        labels_counts = Counter(labels)
        for label in natsorted(labels_counts):
            labelButton = gui.Button(f"{label} ({labels_counts[label]})")
            labelButton.set_style(SMALL_BUTTON_STYLE)
            labelButton.label = label  # python magic
            labelButton.onclick.do(self.reload_history, labelButton)
            self.labelsList.append(labelButton)

    def selected_images(self) -> List[str]:
        imagesToPack = []
        for name, widget in self.historyList.children.items():
            if type(widget) == HistoryRecordWidget and widget.is_selected():
                imagesToPack.append(widget.imagePath)
        return imagesToPack

    def select_all_images(self, emitter=None) -> None:
        for name, widget in self.historyList.children.items():
            if type(widget) == HistoryRecordWidget:
                widget.set_selected(True)

    def deselect_all_images(self, emitter=None) -> None:
        for name, widget in self.historyList.children.items():
            if type(widget) == HistoryRecordWidget:
                widget.set_selected(False)

    def on_download_images(self, emitter):
        if not self.selected_images():
            return

        Config.APP_INSTANCE.execute_javascript(
            f'window.location = "/{id(self)}/direct_download_selected"'
        )

    def direct_download_selected(self):

        imagesToPack = self.selected_images()
        start_date = self.searchFromDay.get_value()
        end_date = self.searchToDay.get_value()
        zipName = f"snapshots-{start_date}-{end_date}.zip"
        zipBytes = BytesIO()
        zipFile = zipfile.ZipFile(zipBytes, "w")
        for image in imagesToPack:
            imageBytes = open(image, "r+b").read()
            imageName = Path(image).name
            zipFile.writestr(imageName, imageBytes)
        zipFile.close()

        headers = {
            "Content-type": "application/zip",
            "Content-Disposition": f'attachment; filename="{zipName}"',
        }
        return [zipBytes.getvalue(), headers]


def load_history_widgets(
    start_date: str, end_date: str, labels_filter: str, max_days: int = 30
) -> Tuple[Optional[List[HistoryRecordWidget]], List[str], str]:

    start_date = datetime.strptime(start_date, DAY_FORMAT)
    end_date = datetime.strptime(end_date, DAY_FORMAT)
    labels_filter = labels_filter.strip().lower()
    if end_date < start_date:
        return None, [], "End date cannot be smaller than start day"

    widgets = []
    labels = []
    search_day = start_date
    add_one_day = timedelta(days=1)
    while search_day <= end_date:
        folder = Config.SNAPSHOTS_DIRECTORY / search_day.strftime(DAY_FORMAT)
        if not folder.is_dir():
            search_day += add_one_day
            continue

        day_config_path = Path(folder) / "history.json"
        if not day_config_path.exists():
            search_day += add_one_day
            continue

        with day_config_path.open("r") as file:
            day_history_list = json.load(file)

        for event in day_history_list:
            event_labels = event["labels"]
            if labels_filter in ["*", ""] + event_labels:
                widget = HistoryRecordWidget.from_config(event)
                widgets.append(widget)
                labels += event_labels
        search_day += add_one_day

    return widgets[::-1], labels, ""
