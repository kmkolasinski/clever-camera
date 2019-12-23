import json
import os
import zipfile
from collections import Counter
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Union

from PIL import Image
from remi import gui

import config.styles as css
from config.config import Config, DAY_FORMAT, HOUR_FORMAT, DATE_FORMAT
from core.widgets import (
    PILImage,
    StaticPILImageWidget,
    HorizontalLine,
    CustomFormWidget,
    ToggleButton,
    HourlyToggleHistogram,
    SButton,
)


class HistoryEventWidget(gui.Container):
    def __init__(self, *args):
        super(HistoryEventWidget, self).__init__(*args)
        self.css_margin = "5px auto"
        self.add_class("border border-secondary")
        self.image_path: Optional[str] = None
        self.image_thumbnail = StaticPILImageWidget(None)
        self.labels_lbl = gui.Label("")
        self.event_date_lbl = gui.Label("")
        self.camera_name_lbl = gui.Label("")
        self.roi_name_lbl = gui.Label("")
        self.download_image_btn = SButton(
            "", "fa-file-download", styles={"padding": "5px 10px"}
        )
        self.select_checkbox = gui.CheckBox()

        self.image_thumbnail.set_size(*Config.MINI_THUMBNAIL_SIZE)
        self.image_thumbnail.css_margin = "1px"
        self.labels_lbl.css_width = "20%"
        self.event_date_lbl.css_width = "20%"

        hl = gui.HBox()
        hl.append(self.select_checkbox)
        hl.append(self.image_thumbnail)
        hl.append(self.labels_lbl)
        hl.append(self.event_date_lbl)
        hl.append(self.camera_name_lbl)
        hl.append(self.roi_name_lbl)
        hl.append(self.download_image_btn)
        self.layout = hl
        self.append(hl)

        # signals
        self.download_image_btn.onclick.do(self.on_download_image)
        self.image_thumbnail.onclick.do(self.on_download_image)
        self.select_checkbox.onclick.do(self.checkbox_toggled)

    @staticmethod
    def from_config(config: Dict[str, Any]) -> "HistoryEventWidget":
        widget = HistoryEventWidget()
        thumbnail = Image.open(config["thumbnail_path"])
        widget.image_thumbnail.set_image(thumbnail)
        widget.labels_lbl.set_text(", ".join(config["labels"]))
        widget.event_date_lbl.set_text(config["datetime"])
        widget.camera_name_lbl.set_text(config["camera_name"])
        widget.roi_name_lbl.set_text(config["roi_name"])
        widget.image_path = config["image_path"]
        return widget

    def on_download_image(self, emitter):
        Config.APP_INSTANCE.execute_javascript(
            f'window.location = "/{id(self)}/direct_download"'
        )

    def direct_download(self):
        with open(self.image_path, "r+b") as f:
            content = f.read()
            headers = {
                "Content-type": "image/jpeg",
                "Content-Disposition": 'attachment; filename="%s"'
                % os.path.basename(self.image_path),
            }
            return [content, headers]

    def is_selected(self) -> bool:
        return self.select_checkbox.get_value()

    def set_selected(self, toggle: bool):
        self.select_checkbox.set_value(toggle)

    @property
    def labels(self) -> List[str]:
        return [l.strip() for l in self.labels_lbl.get_text().split(",")]

    @property
    def roi_name(self) -> str:
        return self.roi_name_lbl.get_text()

    @property
    def event_date(self) -> datetime:
        return datetime.strptime(self.event_date_lbl.get_text(), DATE_FORMAT)

    def checkbox_toggled(self, emitter: gui.CheckBox):
        is_selected = not emitter.get_value()
        emitter.set_value(is_selected)
        self.layout.redraw()


class HistoryWidget(gui.Container):
    def __init__(self, *args):
        super(HistoryWidget, self).__init__(*args)
        self.css_width = "100%"
        self.container = gui.Container()
        self.container.set_layout_orientation(gui.Container.LAYOUT_VERTICAL)
        self.events_hist_list = gui.ListView()
        self.unique_labels_list = gui.ListView()
        self.unique_rois_list = gui.ListView()

        self.container.append(self.events_hist_list)

        btn_class = "btn btn-primary"
        btn_css = css.HISTORY_SEARCH_STYLE

        self.search_history_btn = SButton("Search", "fa-search", btn_class)
        self.set_today_btn = SButton("Today", "fa-sun", btn_class, btn_css)
        self.set_prev_day_btn = SButton("", "fa-chevron-left", btn_class, btn_css)
        self.set_next_day_btn = SButton("", "fa-chevron-right", btn_class, btn_css)

        todays_date = datetime.now().strftime(DAY_FORMAT)
        self.search_from_date_widget = gui.Date(todays_date)
        self.search_to_date_widget = gui.Date(todays_date)
        self.filter_by_label_input = gui.TextInput()
        self.filter_by_label_input.set_text("*")
        self.search_info_lbl = gui.Label("")
        self.download_selected_btn = SButton(
            "Download selected", "fa-download", btn_class
        )
        self.select_all_btn = SButton("Select All", "fa-check-square", btn_class)
        self.deselect_all_btn = SButton("Deselect All", "fa-square", btn_class)
        self.reset_filters_btn = SButton("Reset", "fa-undo-alt", btn_class)
        self.apply_filters_btn = SButton("Filter", "fa-filter", btn_class)

        search_form = CustomFormWidget()
        search_form.css_width = "70%"
        search_form.add_field("from_day", "Search from", self.search_from_date_widget)
        search_form.add_field("to_day", "Search to", self.search_to_date_widget)
        search_form.add_field("by_label", "Filter by label", self.filter_by_label_input)

        hbox = gui.HBox()
        hbox.css_display = "block"
        hbox.append(self.set_prev_day_btn)
        hbox.append(self.set_today_btn)
        hbox.append(self.set_next_day_btn)
        hbox.append(self.search_history_btn)

        search_form.add_field("controls", "", hbox)
        search_form.append(self.search_info_lbl)

        form_layout = gui.VBox()
        form_layout.append(search_form)

        controls_layout = gui.HBox()
        controls_layout.css_display = "block"
        controls_layout.append(self.download_selected_btn)
        controls_layout.append(self.select_all_btn)
        controls_layout.append(self.deselect_all_btn)
        controls_layout.append(self.apply_filters_btn)
        controls_layout.append(self.reset_filters_btn)

        self.hourly_hist_widget = HourlyToggleHistogram()
        self.style["padding"] = "0px 5px"
        self.append(HorizontalLine())
        self.append(form_layout)
        self.append(HorizontalLine())
        self.append(self.hourly_hist_widget)
        self.append(self.unique_rois_list)
        self.append(self.unique_labels_list)
        self.append(HorizontalLine())
        self.append(controls_layout)
        self.append(self.container)
        self.append(HorizontalLine())

        # signals:
        self.search_history_btn.onclick.do(self.update_events_history_list)
        self.set_prev_day_btn.onclick.do(self.shift_search_dates, delta=-1)
        self.set_next_day_btn.onclick.do(self.shift_search_dates, delta=1)
        self.set_today_btn.onclick.do(self.set_today_date)
        self.download_selected_btn.onclick.do(self.on_download_images)
        self.select_all_btn.onclick.do(self.select_all_images)
        self.deselect_all_btn.onclick.do(self.deselect_all_images)
        self.reset_filters_btn.onclick.do(self.reset_filters)
        self.apply_filters_btn.onclick.do(self.apply_filters)

    def search_for_events(self) -> Tuple[List[HistoryEventWidget], List[str], bool]:
        widgets, labels, msg = load_history_widgets(
            start_date=self.search_from_date_widget.get_value(),
            end_date=self.search_to_date_widget.get_value(),
            labels_filter=self.filter_by_label_input.get_text(),
        )
        if widgets is None:
            self.search_info_lbl.set_text(f"Error: {msg}")
            return [], [], False

        return widgets, labels, True

    def update_events_history_list(self, emitter=None):
        self.events_hist_list.empty()
        self.unique_labels_list.empty()
        self.unique_rois_list.empty()

        widgets, labels, is_ok = self.search_for_events()
        if not is_ok:
            return False

        for widget in widgets:
            self.events_hist_list.append(widget)

        self.search_info_lbl.set_text(f"Found {len(widgets)} events.")

        labels_counts = Counter(labels).most_common()
        for label, count in labels_counts:
            label_btn = ToggleButton(f"{label} ({count})", label)
            label_btn.set_style(css.SMALL_BUTTON_STYLE)
            self.unique_labels_list.append(label_btn)

        rois_counts = Counter([w.roi_name for w in widgets]).most_common()
        for roi, count in rois_counts:
            label_btn = ToggleButton(f"{roi} ({count})", roi)
            label_btn.set_style(css.SMALL_BUTTON_STYLE)
            self.unique_rois_list.append(label_btn)

        self.hourly_hist_widget.update_from_dates([w.event_date for w in widgets])

    def reset_filters(self, emitter=None):
        for btn in self.unique_rois_list.children.values():
            btn.set_checked(False)
        for btn in self.unique_labels_list.children.values():
            btn.set_checked(False)

        self.hourly_hist_widget.reset_selections()

    def get_selected_labels(self) -> List[str]:
        return [
            w.internal_value
            for w in self.unique_labels_list.children.values()
            if w.is_toggled
        ]

    def get_selected_rois(self) -> List[str]:
        return [
            w.internal_value
            for w in self.unique_rois_list.children.values()
            if w.is_toggled
        ]

    def apply_filters(self, emitter=None):
        widgets, _, is_ok = self.search_for_events()
        if not is_ok:
            return False

        selected_labels = set(self.get_selected_labels())
        selected_rois = self.get_selected_rois()
        selected_hours = self.hourly_hist_widget.get_selected_hours()

        labels_empty = len(selected_labels) == 0
        rois_empty = len(selected_rois) == 0
        hours_empty = len(selected_hours) == 0

        self.events_hist_list.empty()
        filtered_labels = []
        for widget in widgets:

            roi = widget.roi_name
            labels = set(widget.labels)
            hour = widget.event_date.hour

            roi_test = roi in selected_rois or rois_empty
            labels_test = len(labels.intersection(selected_labels)) > 0 or labels_empty
            hours_test = hour in selected_hours or hours_empty

            if all([roi_test, labels_test, hours_test]):
                self.events_hist_list.append(widget)
                filtered_labels += list(labels)

        self.search_info_lbl.set_text(
            f"Filtered {len(self.events_hist_list.children)} events."
        )

        labels_counts = Counter(filtered_labels)
        for btn in self.unique_labels_list.children.values():
            label = btn.internal_value
            count = labels_counts.get(label, 0)
            btn.set_text(f"{label} ({count})")

        rois_counts = Counter(
            [w.roi_name for w in self.events_hist_list.children.values()]
        )
        for btn in self.unique_rois_list.children.values():
            roi = btn.internal_value
            count = rois_counts.get(roi, 0)
            btn.set_text(f"{roi} ({count})")

    def set_today_date(self, emitter=None):
        todays_date = datetime.now().strftime(DAY_FORMAT)
        self.search_from_date_widget.set_value(todays_date)
        self.search_to_date_widget.set_value(todays_date)

    @property
    def search_start_date(self) -> datetime:
        start_date = self.search_from_date_widget.get_value()
        return datetime.strptime(start_date, DAY_FORMAT)

    @property
    def search_end_date(self) -> datetime:
        start_date = self.search_to_date_widget.get_value()
        return datetime.strptime(start_date, DAY_FORMAT)

    def shift_search_dates(self, emitter=None, delta: int = 1):
        delta = timedelta(days=delta)
        date = self.search_start_date + delta
        self.search_from_date_widget.set_value(date.strftime(DAY_FORMAT))
        date = self.search_end_date + delta
        self.search_to_date_widget.set_value(date.strftime(DAY_FORMAT))

    def selected_images(self) -> List[str]:
        images_to_pack = []
        for name, widget in self.events_hist_list.children.items():
            if type(widget) == HistoryEventWidget and widget.is_selected():
                images_to_pack.append(widget.imagePath)
        return images_to_pack

    def select_all_images(self, emitter=None) -> None:
        for name, widget in self.events_hist_list.children.items():
            if type(widget) == HistoryEventWidget:
                widget.set_selected(True)

    def deselect_all_images(self, emitter=None) -> None:
        for name, widget in self.events_hist_list.children.items():
            if type(widget) == HistoryEventWidget:
                widget.set_selected(False)

    def on_download_images(self, emitter):
        if not self.selected_images():
            return

        Config.APP_INSTANCE.execute_javascript(
            f'window.location = "/{id(self)}/direct_download_selected"'
        )

    def direct_download_selected(self):

        images_to_pack = self.selected_images()
        start_date = self.search_from_date_widget.get_value()
        end_date = self.search_to_date_widget.get_value()
        zip_name = f"snapshots-{start_date}-{end_date}.zip"
        zip_bytes = BytesIO()
        zip_file = zipfile.ZipFile(zip_bytes, "w")
        for image in images_to_pack:
            image_bytes = open(image, "r+b").read()
            image_name = Path(image).name
            zip_file.writestr(image_name, image_bytes)
        zip_file.close()

        headers = {
            "Content-type": "application/zip",
            "Content-Disposition": f'attachment; filename="{zip_name}"',
        }
        return [zip_bytes.getvalue(), headers]


def append_snapshots_history(
    image: PILImage,
    labels: List[str],
    labels_filter: str,
    roi_name: str,
    camera_name: str,
    image_change: float,
) -> bool:
    now = datetime.now()
    date = now.strftime(DAY_FORMAT)
    hour = now.strftime(HOUR_FORMAT)
    saveDir = Config.SNAPSHOTS_DIR / str(date)
    saveDir.mkdir(exist_ok=True, parents=True)

    thumbnail = image.copy()
    thumbnail.thumbnail(Config.THUMBNAIL_SIZE)
    thumbnail_path = f"{saveDir}/thumbnail-{hour}.jpg"
    image_path = f"{saveDir}/image-{hour}.jpg"

    thumbnail.save(thumbnail_path)
    image.save(image_path)

    data = {
        "datetime": now.strftime(f"{DAY_FORMAT} {HOUR_FORMAT}"),
        "thumbnail_path": thumbnail_path,
        "image_path": image_path,
        "labels": labels,
        "class_filter": labels_filter,
        "camera_name": camera_name,
        "roi_name": roi_name,
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

    return True


def string_to_datetime(date: str) -> datetime:
    return datetime.strptime(date, DATE_FORMAT)


def load_history_widgets(
    start_date: Union[str, datetime],
    end_date: Union[str, datetime],
    labels_filter: str,
    max_days: int = 30,
) -> Tuple[Optional[List[HistoryEventWidget]], List[str], str]:

    if type(start_date) is str:
        start_date = datetime.strptime(start_date, DAY_FORMAT)
    if type(end_date) is str:
        end_date = datetime.strptime(end_date, DAY_FORMAT)

    labels_filter = labels_filter.strip().lower()
    if end_date < start_date:
        return None, [], "End date cannot be smaller than start day"

    widgets = []
    labels = []
    search_day = start_date
    add_one_day = timedelta(days=1)
    while search_day <= end_date:
        folder = Config.SNAPSHOTS_DIR / search_day.strftime(DAY_FORMAT)
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
                widget = HistoryEventWidget.from_config(event)
                widgets.append(widget)
                labels += event_labels
        search_day += add_one_day

    return widgets[::-1], labels, ""


def load_day_history(date: Union[str, datetime]) -> Optional[List[Dict[str, Any]]]:

    if type(date) is str:
        date = datetime.strptime(date, DAY_FORMAT)

    folder = Config.SNAPSHOTS_DIR / date.strftime(DAY_FORMAT)
    day_config_path = Path(folder) / "history.json"
    if not day_config_path.exists():
        return []

    with day_config_path.open("r") as file:
        history = json.load(file)
    return history[::-1]
