import base64
import binascii
import io
import mimetypes
import smtplib
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Union, Optional, List, Tuple, Dict, Any
import numpy as np
import PIL
import PIL.Image
import remi.gui as gui
from PIL import ImageDraw, ImageFont
from remi import App
import yagmail

from config.config import Config
import config.styles as css

PILImage = PIL.Image.Image


class CustomButton(gui.Button):
    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)
        self.set_style(style=css.DEFAULT_BUTTON_STYLE)
        self.add_class("btn-small btn btn-secondary")
        self.type = "button"


class ToggleButton(gui.Button):
    def __init__(
        self,
        text: str,
        internal_value: Any = None,
        style: Dict[str, Any] = None,
        *arg,
        **kwargs,
    ):
        """
        A button which can be toggled, similar to checkbox.
        Args:
            text: a button text
            internal_value: internal value which button can keep
            style: any css style
        """
        super().__init__(text=text, *arg, **kwargs)
        self.is_toggled = False
        self.internal_value = internal_value
        if style is None:
            self.set_style(css.TOGGLE_BUTTON_STYLE)
        else:
            self.set_style(style)
        self.update_state()
        self.onclick.do(self.on_toggled)

    @gui.decorate_set_on_listener("(self, emitter)")
    @gui.decorate_event
    def on_toggled(self, *args):
        self.is_toggled = not self.is_toggled
        self.update_state()
        return (self.is_toggled,)

    def set_checked(self, checked: bool):
        self.is_toggled = checked
        self.update_state()

    def update_state(self):
        if not self.is_toggled:
            self.remove_class("btn-success")
            self.add_class("btn-secondary")
        else:
            self.add_class("btn-success")
            self.remove_class("btn-secondary")


class HourlyToggleHistogram(gui.Container):
    HEIGHT = 80

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        hours_layout = gui.HBox()
        hours_layout.css_height = f"{self.HEIGHT}px"
        width = f"{100 / 24}%"

        # create list of clickable buttons for every hour
        self.hourly_buttons = []
        for hour in range(24):
            btn = ToggleButton(text="", internal_value=hour, width=width)
            btn.css_height = f"0px"
            btn.css_margin = "0px 1px"
            btn.css_position = "relative"
            self.hourly_buttons.append(btn)
            hours_layout.append(btn)
        self.append(hours_layout)

        hours_layout = gui.HBox()
        for hour in range(24):
            btn = gui.Label(text=f"{hour + 1}", width=width)
            btn.css_text_align = "center"
            btn.css_font_size = "smaller"
            hours_layout.append(btn)
        self.append(hours_layout)

        self.update_from_dates([])

    def reset_selections(self):
        for btn in self.hourly_buttons:
            btn.set_checked(False)

    def get_selected_hours(self) -> List[int]:
        hours = [w.internal_value for w in self.hourly_buttons if w.is_toggled]
        return hours

    def update_from_dates(self, dates: List[datetime]):
        """
        Creates histogram of events for every hour in the day.
        Args:
            dates: a list of events dates
        """
        hour_count = Counter([date.hour for date in dates])
        max_prob = 1
        total_count = 1
        if len(hour_count) > 0:
            total_count = sum(hour_count.values())
            max_count = max(hour_count.values())
            max_prob = max_count / total_count

        for hour in range(24):
            count = hour_count.get(hour, 0)
            bt = self.hourly_buttons[hour]
            new_height = int(self.HEIGHT * (count / total_count / max_prob))
            new_height = max(1, new_height)
            new_top = (self.HEIGHT - new_height) // 2
            bt.css_height = f"{new_height}px"
            bt.css_top = f"{new_top}px"
            bt.css_position = "relative"
            bt.set_checked(False)


class MonitoringScheduleWidget(gui.VBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.css_width = "100%"
        hours = [f"{h}:00" for h in range(24)]
        self.from_hour_combo = gui.DropDown.new_from_list(hours)
        self.to_hour_combo = gui.DropDown.new_from_list(hours)
        self.weekdays = [
            ToggleButton("Mo", width="inherit"),
            ToggleButton("Tu", width="inherit"),
            ToggleButton("We", width="inherit"),
            ToggleButton("Th", width="inherit"),
            ToggleButton("Fr", width="inherit"),
            ToggleButton("Sa", width="inherit"),
            ToggleButton("Su", width="inherit"),
        ]
        self.from_hour_combo.set_value("8:00")
        self.to_hour_combo.set_value("18:00")

        layout = gui.HBox(width="100%")
        layout.append(gui.Label("From: "))
        layout.append(self.from_hour_combo)
        layout.append(gui.Label("To: "))
        layout.append(self.to_hour_combo)
        self.append(layout)

        layout = gui.HBox(width="100%")
        for day in self.weekdays:
            layout.append(day)
        self.append(layout)

    def get_values(self) -> Dict[str, Any]:
        return {
            "from": self.from_hour_combo.get_value(),
            "to": self.to_hour_combo.get_value(),
            "weekdays": [w.is_toggled for w in self.weekdays],
        }

    def set_values(self, config: Dict[str, Any]):
        if "from" in config:
            self.from_hour_combo.set_value(config["from"])
        if "to" in config:
            self.to_hour_combo.set_value(config["to"])
        if "weekdays" in config:
            for toggle, day in zip(config["weekdays"], self.weekdays):
                day.set_checked(toggle)

    @property
    def from_hour(self) -> int:
        return int(self.from_hour_combo.get_value().split(":")[0])

    @property
    def to_hour(self) -> int:
        return int(self.to_hour_combo.get_value().split(":")[0])

    def is_date_in_schedule(self, date: Optional[datetime] = None) -> bool:
        if date is None:
            date = datetime.now()
        if not self.weekdays[date.weekday()].is_toggled:
            return False

        return self.from_hour <= date.hour < self.to_hour


class SButton(gui.Button):
    def __init__(
        self,
        text: str,
        icon: str = None,
        btn_class: str = "btn btn-secondary",
        styles: Dict[str, Any] = None,
        *arg,
        **kwargs,
    ):
        """
        Styled button with possible icon and bootstrap class
        Args:
            text: button text
            icon: optional font awesome type
            btn_class: button bootstrap class
            styles: additional styles
        """
        self.icon = icon
        self.btn_class = btn_class
        self.btn_text = text

        super().__init__(text=text, *arg, **kwargs)
        if styles is not None:
            self.set_style(styles)
        else:
            self.set_style(css.DEFAULT_BUTTON_STYLE)

    def update(self):
        text = gui.escape(self.btn_text, quote=False)
        icon = ""
        if self.icon:
            icon = f"<i class='fa {self.icon}'></i>"

        self.add_child("text", f"{icon} {text}")
        if self.btn_class:
            self.add_class(self.btn_class)

    def set_icon(self, icon: str):
        if icon != self.icon:
            self.icon = icon
            self.update()

    def set_text(self, text):
        """
        Sets the text label for the Widget.

        Args:
            text (str): The string label of the Widget.
        """
        self.btn_text = text
        self.update()

    def get_text(self):
        """
        Returns:
            str: The text content of the Widget. You can set the text content with set_text(text).
        """
        return self.btn_text

    def set_value(self, text):
        return self.set_text(text)

    def get_value(self):
        return self.get_text()


class StyledDropDownMenu(gui.Container):
    def __init__(self, title_widget: gui.Widget, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.set_style({"display": "contents"})
        title_widget.add_class("dropdown-toggle")
        title_widget.attributes["data-toggle"] = "dropdown"
        self.append(title_widget)

        menu = gui.Container()
        menu.add_class("dropdown-menu")

        self.menu = menu
        self.append(menu)

    def add_item(self, key: str, item: gui.Widget):
        item.add_class("dropdown-item")
        item.style["box-shadow"] = "0px 0px 0px #fff"
        self.menu.add_child(key, item)


class LoggerWidget(gui.ListView):
    def __init__(self, history_size: int = 5, *arg, **kwargs):
        super().__init__(*arg, **kwargs)
        self.history = []
        self.history_size = history_size
        self.set_style(css.LOGGER_STYLE)

    def update_history(self, label: gui.Label):
        print(label.get_text())
        self.history = self.history[-self.history_size :]
        self.history.append(label)
        self.empty()
        for label in self.history:
            self.append(label)

    @staticmethod
    def time() -> str:
        return datetime.now().strftime("%H:%M:%S")

    def format_text(self, level: str, text: str) -> str:
        return f"{self.time()}::{level.upper()}::{text}"

    def text_to_label(self, level: str, text: str) -> gui.Label:
        label = gui.Label(self.format_text(level, text))
        label.css_font_family = "monospace"
        return label

    def info(self, text: str):
        label = self.text_to_label("Info", text)
        self.update_history(label)

    def warning(self, text: str):
        label = self.text_to_label("Warning", text)
        self.update_history(label)

    def error(self, text: str):
        label = self.text_to_label("Error", text)
        self.update_history(label)


class PlainHTML(gui.Widget):
    def __init__(self, html: str, *arg, **kwargs):
        super().__init__(*arg, **kwargs)
        self.add_child("html", html)


class Header(PlainHTML):
    def __init__(self, html: str, level: int = 1, *arg, **kwargs):
        super().__init__(html=html, *arg, **kwargs)
        self.add_child("html", f"<h{level}>{html}</h{level}>")


class HorizontalLine(PlainHTML):
    def __init__(self, *arg, **kwargs):
        super().__init__(html="<hr>", *arg, **kwargs)


class CenteredHBox(gui.HBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.css_display = "table"
        self.css_margin = "auto"


class CustomFormWidget(gui.Container):
    def __init__(self, labels_min_width: str = "40%", *args):
        super(CustomFormWidget, self).__init__(*args)
        self.inputs = {}
        self.container = gui.Container()
        self.container.style.update(
            {"display": "block", "overflow": "auto", "margin": "5px"}
        )
        self.css_margin = "5px"
        self.css_labels_min_width = labels_min_width
        self.container.set_layout_orientation(gui.Container.LAYOUT_VERTICAL)
        self.append(self.container)

    def add_field(self, key: str, desc: str, field: gui.Widget):
        """
        Adds a field to the dialog together with a descriptive label and a unique identifier.

        Note: You can access to the fields content calling the function GenericDialog.get_field(key).

        Args:
            key (str): The unique identifier for the field.
            desc (str): The string content of the description label.
            field (Widget): The instance of the field Widget. It can be for example a TextInput or maybe
            a custom widget.
        """
        label = gui.Label(desc)
        label.style["min-width"] = self.css_labels_min_width
        label.css_font_weight = 1000

        field.add_class("input")
        if not isinstance(field, gui.Button):
            field.set_style(
                {
                    "padding": "5px 5px",
                    "background": "white",
                    "border-bottom": "2px solid  # 00000061",
                }
            )

        container = gui.HBox()
        container.style.update(
            {"justify-content": "space-between", "overflow": "auto", "padding": "3px",}
        )
        container.append(label, key="lbl" + key)
        container.append(field, key=key)
        self.container.append(container, key=key)
        self.inputs[key] = field

    def add_progress_bar(self, key: str, desc: str):
        bar = gui.Progress(width="100%", height="30px")
        self.add_field(key=key, desc=desc, field=bar)

    def add_text(self, key: str, desc: str, text: str = "", **kwargs):
        label = gui.TextInput(**kwargs)
        label.set_text(text)
        self.add_field(key=key, desc=desc, field=label)

    def add_password(self, key: str, desc: str, text: str = "", **kwargs):
        label = gui.Input(input_type="password", width="100%", **kwargs)
        label.set_value(text)
        self.add_field(key=key, desc=desc, field=label)

    def add_checkbox(self, key: str, desc: str, **kwargs):
        label = gui.CheckBox(checked=True, **kwargs)
        self.add_field(key=key, desc=desc, field=label)

    def add_numeric(
        self,
        key: str,
        desc: str,
        default_value=0,
        min_value=0,
        max_value=100,
        step=5,
        **kwargs,
    ):
        spin = gui.SpinBox(
            default_value=default_value,
            min_value=min_value,
            max_value=max_value,
            step=step,
            **kwargs,
        )

        self.add_field(key=key, desc=desc, field=spin)

    def add_dropdown(self, key: str, desc: str, values: List[str], **kwargs):
        dropDown = gui.DropDown.new_from_list(values, **kwargs,)
        self.add_field(key=key, desc=desc, field=dropDown)

    def get_value(self, key: str) -> Union[int, str, float, Dict[str, Any]]:
        gettables = [gui.SpinBox, gui.DropDown, gui.CheckBox, gui.Input]
        field = self.inputs[key]
        if isinstance(field, gui.TextInput):
            return field.get_text()
        elif any([isinstance(field, gb) for gb in gettables]):
            return field.get_value()
        elif isinstance(field, MonitoringScheduleWidget):
            return field.get_values()
        raise NotImplementedError(f"Getter for {field} is not implemented.")

    def has_field(self, key: str) -> bool:
        return key in self.inputs

    def set_value(self, key: str, value: Any):
        settables = [gui.SpinBox, gui.DropDown, gui.CheckBox, gui.Input]
        field = self.inputs[key]
        if isinstance(field, gui.TextInput):
            return field.set_text(value)
        elif any([isinstance(field, sb) for sb in settables]):
            return field.set_value(value)
        elif isinstance(field, MonitoringScheduleWidget):
            return field.set_values(value)
        raise NotImplementedError(f"Setter for {field} is not implemented.")


class SettingsWidget(gui.Container):
    def __init__(
        self, title: str = None, labels_min_width: str = "40%", *args, **kwargs
    ):
        super(SettingsWidget, self).__init__(*args, **kwargs)
        self.settings = CustomFormWidget(labels_min_width=labels_min_width)
        self.settings.add_class("border border-secondary rounded")
        self.settings.style["padding"] = "5px 5px"

        if title is not None:
            title_label = gui.Label(title)
            title_label.css_font_weight = "1000"
            title_label.style["padding"] = "5px"
            self.append(title_label)

    def __getitem__(self, item: str):
        return self.settings.inputs[item]

    def add_text_field(self, *args, **kwargs):
        self.settings.add_text(*args, **kwargs)

    def add_progress_bar(self, *args, **kwargs):
        self.settings.add_progress_bar(*args, **kwargs)

    def add_password_field(self, *args, **kwargs):
        self.settings.add_password(*args, **kwargs)

    def add_checkbox_field(self, *args, **kwargs):
        self.settings.add_checkbox(*args, **kwargs)

    def add_int_field(self, *args, **kwargs):
        self.settings.add_numeric(*args, **kwargs)

    def add_choice_field(self, *args, **kwargs):
        self.settings.add_dropdown(*args, **kwargs)

    def get_settings(self) -> Dict[str, Any]:
        config = {
            k: self.settings.get_value(k) for k, _ in self.settings.inputs.items()
        }
        return config

    def set_settings(self, settings: Dict[str, Any]) -> None:
        for key, value in settings.items():
            if self.settings.has_field(key):
                self.settings.set_value(key, value)

    @classmethod
    def from_settings(cls, settings: Dict[str, Any]) -> "SettingsWidget":
        widget = cls()
        widget.set_settings(settings)
        return widget


class StaticPILImageWidget(gui.Image):
    """
    Use this when image does not have to reloaded frequently
    """

    def __init__(self, image_path: str, **kwargs):
        super(StaticPILImageWidget, self).__init__("", **kwargs)
        self.image_path = image_path
        self._buf = None
        self.image: PILImage = None
        if image_path is not None:
            self.set_image(image=None)

    def load(self, path: str):
        self.set_image(PIL.Image.open(path))

    def get_image(self) -> PILImage:
        return self.image

    def set_image(self, image: Optional[PILImage]) -> None:
        if image is None:
            image = PIL.Image.open(self.image_path)

        self.image = image
        self._buf = io.BytesIO()
        image.save(self._buf, format="jpeg")
        self.refresh()

    def refresh(self):
        i = int(time.time() * 1e6)
        self.attributes["src"] = f"/{id(self)}/get_image_data?update_index={i}"

    def get_image_data(self, update_index):
        if self._buf is None:
            return None
        self._buf.seek(0)
        headers = {"Content-type": "image/jpeg"}
        return [self._buf.read(), headers]


class PILImageWidget(gui.Image):
    def __init__(self, app_instance: App, filename=None, **kwargs):
        """
        :param app_instance:
        :param filename:
        :param kwargs:
        """
        super(PILImageWidget, self).__init__(filename, **kwargs)
        self.app_instance = app_instance
        self.imagedata = None
        self.mimetype = None
        self.encoding = None
        if not filename:
            return
        self.load(filename)

    def load(self, filepath: Union[str, Path], use_js: bool = True):

        if isinstance(filepath, Path):
            filepath = str(filepath)

        if type(filepath) is bytes or len(filepath) > 200:
            try:
                # here a base64 image is received
                self.imagedata = base64.b64decode(filepath, validate=True)
                self.attributes["src"] = "/%s/get_image_data?update_index=%s" % (
                    id(self),
                    str(time.time()),
                )
            except binascii.Error:
                # here an image data is received (opencv image)
                self.imagedata = filepath
                self.refresh()
        else:
            # here a filename is received
            self.mimetype, self.encoding = mimetypes.guess_type(filepath)
            with open(filepath, "rb") as f:
                self.imagedata = f.read()
            self.refresh(use_js=use_js)

    def set_pil_image(self, image: PILImage) -> None:
        buf = io.BytesIO()
        image.save(buf, format="jpeg")
        self.mimetype = "image/jpeg"
        self.imagedata = buf.getvalue()
        self.refresh(use_js=True)

    def refresh(self, use_js: bool = True):
        i = int(time.time() * 1e6)
        if use_js:
            self.app_instance.execute_javascript(
                """
                var url = '/%(id)s/get_image_data?update_index=%(frame_index)s';
                var xhr = new XMLHttpRequest();
                xhr.open('GET', url, true);
                xhr.responseType = 'blob'
                xhr.onload = function(e){
                    var urlCreator = window.URL || window.webkitURL;
                    var imageUrl = urlCreator.createObjectURL(this.response);
                    document.getElementById('%(id)s').src = imageUrl;
                }
                xhr.send();
                """
                % {"id": id(self), "frame_index": i}
            )
        else:
            self.attributes["src"] = f"/{id(self)}/get_image_data?update_index={i}"

    def get_image_data(self, update_index: int = None):
        headers = {
            "Content-type": self.mimetype
            if self.mimetype
            else "application/octet-stream"
        }
        return [self.imagedata, headers]


class ROIWidget(SettingsWidget):
    ROI_X_MIN = "roi_x_min"
    ROI_Y_MIN = "roi_y_min"
    ROI_X_MAX = "roi_x_max"
    ROI_Y_MAX = "roi_y_max"
    LABELS_FILTER = "labels_filter"
    NAME = "name"
    ENABLED = "enabled"
    PER_PIXEL_CHANGE_THRESHOLD = 0.2
    MEAN_CHANGE_THRESHOLD = 0.01

    def __init__(self, name: str = "default", *args):
        super(ROIWidget, self).__init__(*args)
        self.settings.css_labels_min_width = "50%"
        self.add_checkbox_field(self.ENABLED, "Enabled")
        self.add_text_field(self.NAME, "Name", name)
        self.add_text_field(self.LABELS_FILTER, "Labels (comma separated)", "*")
        self.add_int_field(self.ROI_X_MIN, "X min [%]")
        self.add_int_field(self.ROI_Y_MIN, "Y min [%]")
        self.add_int_field(self.ROI_X_MAX, "X max [%]", default_value=100)
        self.add_int_field(self.ROI_Y_MAX, "Y max [%]", default_value=100)
        self.append(self.settings)

        # signals
        self[self.ROI_X_MIN].onchange.do(self.on_roi_changed)
        self[self.ROI_Y_MIN].onchange.do(self.on_roi_changed)
        self[self.ROI_X_MAX].onchange.do(self.on_roi_changed)
        self[self.ROI_Y_MAX].onchange.do(self.on_roi_changed)
        self[self.ENABLED].onchange.do(self.on_roi_changed)
        self[self.NAME].onchange.do(self.on_roi_changed)
        self[self.LABELS_FILTER].onchange.do(self.on_roi_changed)

    def is_enabled(self) -> bool:
        return self[self.ENABLED].get_value()

    @property
    def name(self) -> str:
        return self[self.NAME].get_value()

    @property
    def labels_filter(self) -> str:
        return self[self.LABELS_FILTER].get_value()

    def filter_labels(self, labels: List[str]) -> List[str]:
        filtered_labels = labels
        if self.labels_filter != "*":
            search_labels = self.labels_filter.lower().strip().split(",")
            filtered_labels = []
            for label in labels:
                if label.lower() in search_labels:
                    filtered_labels.append(label)
        return filtered_labels

    @gui.decorate_set_on_listener("(self, emitter)")
    @gui.decorate_event
    def on_roi_changed(self, *args):
        return ()

    def get_image_roi(self, image: PILImage) -> Tuple[int, int, int, int]:
        x_min = int(self[self.ROI_X_MIN].get_value())
        y_min = int(self[self.ROI_Y_MIN].get_value())
        x_max = int(self[self.ROI_X_MAX].get_value())
        y_max = int(self[self.ROI_Y_MAX].get_value())

        x_min, y_min = max(0, x_min) / 100.0, max(0, y_min) / 100.0
        x_max, y_max = min(100, x_max) / 100.0, min(100, y_max) / 100.0
        width, height = image.size
        box = (
            int(min(x_min, x_max) * width),
            int(min(y_min, y_max) * height),
            int(max(x_min, x_max) * width),
            int(max(y_min, y_max) * height),
        )
        return box

    def draw_roi_on_image(self, image: PILImage) -> PILImage:
        roi = self.get_image_roi(image)
        font_size = 30
        outline = (40, 167, 69, 250) if self.is_enabled() else "red"

        fnt = ImageFont.truetype(str(Config.FONT_PATH), size=font_size)
        draw = ImageDraw.Draw(image, "RGBA")
        x1, y1, x2, y2 = roi
        draw.rectangle((roi[:2], roi[2:]), outline=outline, width=3)
        draw.rectangle((x1, y1 - font_size - 2, x2, y1), fill=outline, width=3)
        draw.text((roi[0], roi[1] - font_size + 2), self.name, font=fnt)
        return image

    def crop(self, image: PILImage) -> PILImage:
        roi = self.get_image_roi(image)
        return image.crop(box=roi)

    def compute_roi_image_change(
        self, prev_image: PILImage, curr_image: PILImage
    ) -> float:
        """
        Estimate the fraction of image ROI changed  between
        to frames
        Args:
            prev_image:
            curr_image:

        Returns:
            a number between (0, 1) which defines the fraction of
            pixels in the ROI which changed more then "per pixel"
            threshold
        """
        crop_size = (200, 200)
        cim = self.crop(curr_image).resize(crop_size, resample=2)
        pim = self.crop(prev_image).resize(crop_size, resample=2)
        cim_gray = np.array(cim).mean(-1) / 255.0
        pim_gray = np.array(pim).mean(-1) / 255.0
        image_diff = np.abs(cim_gray - pim_gray)
        fraction_changed = (image_diff > self.PER_PIXEL_CHANGE_THRESHOLD).mean()
        return fraction_changed


class DroppableTabBox(gui.TabBox):
    """
    A tab box which tab can be remove at runtime
    """

    def drop_tab(self, key: str) -> None:
        if len(self.tab_keys_ordered_list) == 0:
            return
        self.tab_keys_ordered_list.remove(key)
        child = self.get_child(key)
        self.remove_child(child)
        tab_child = self.container_tab_titles.get_child(key)
        self.container_tab_titles.remove_child(tab_child)
        if len(self.tab_keys_ordered_list) > 0:
            self.select_by_index(-1)
        else:
            self.selected_widget_key = None


class EmailNotifierWidget(SettingsWidget):
    def __init__(self, *args, **kwargs):
        super().__init__("Gmail notification settings", *args, **kwargs)
        self.last_message_send: Optional[datetime] = None
        self.settings.css_labels_min_width = "60%"

        self.enable_notifications_btn = ToggleButton(
            "Disabled", style=css.DEFAULT_BUTTON_STYLE
        )
        self.send_email_btn = SButton("Send test mail", "fa-paper-plane")
        self.last_message_send_lbl = gui.Label()
        self.last_message_send_lbl.style["padding"] = "5px"

        self.add_text_field(
            "sender_email",
            "Sender email account ('Less secure app access' must be enabled)",
            "your.mail@gmail.com",
        )
        self.add_password_field("sender_password", "Sender email password", "")
        self.add_text_field(
            "receiver_email", "Receiver email ", "your.mail@gmail.com",
        )
        self.add_int_field(
            "frequency",
            "Trigger when last event was later than this number "
            "of minutes (for example 1440min = 24h)",
            default_value=60,
            max_value=1440,
            step=15,
        )
        self.add_int_field(
            "max_num_images",
            "Maximum images to send",
            default_value=5,
            min_value=1,
            max_value=20,
            step=1,
        )
        self.settings.append(HorizontalLine())
        self.settings.append(self.last_message_send_lbl)
        self.settings.append(HorizontalLine())

        layout = CenteredHBox()
        layout.append(self.enable_notifications_btn)
        layout.append(self.send_email_btn)
        self.settings.append(layout)

        self.append(self.settings)

        self.enable_notifications_btn.on_toggled.do(self.toggle_notifications)
        self.send_email_btn.onclick.do(self.on_send_message)

    @gui.decorate_set_on_listener("(self, emitter)")
    @gui.decorate_event
    def on_send_message(self, *args):
        return ()

    def toggle_notifications(self, emitter=None, is_toggled: bool = False):
        text = "Enabled" if is_toggled else "Disabled"
        self.enable_notifications_btn.set_text(text)

    @property
    def notification_frequency(self) -> int:
        return int(self["frequency"].get_value())

    @property
    def is_enabled(self) -> bool:
        return self.enable_notifications_btn.is_toggled

    @property
    def max_num_images(self) -> int:
        return int(self["max_num_images"].get_value())

    @property
    def sender_email(self) -> str:
        return self["sender_email"].get_value()

    @property
    def sender_password(self) -> str:
        return self["sender_password"].get_value()

    @property
    def receiver_email(self) -> str:
        return self["receiver_email"].get_value()

    def cannot_send_email(self) -> bool:
        if not self.is_enabled:
            print("Cannot send mail, tool not enabled.")
            return True

        date = datetime.now()
        if self.last_message_send is not None:
            delta = date - self.last_message_send
            delta_minutes = delta.total_seconds() // 60
            if delta_minutes < self.notification_frequency:
                return True
        return False

    def send_notification_message(
        self,
        do_checks: bool = True,
        title: str = "",
        contents: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None,
    ):

        date = datetime.now()
        if do_checks and self.cannot_send_email():
            print("Cannot send mail, frequency condition not satisfied")
            return False

        subject = f"[Clever-Camera] {date} {title} "

        if len(attachments) > self.max_num_images:
            ntimes = len(attachments) // self.max_num_images
            attachments = attachments[::ntimes][: self.max_num_images]

        try:
            yag = yagmail.SMTP(user=self.sender_email, password=self.sender_password)
            result = yag.send(
                self.receiver_email, subject, contents, attachments=attachments
            )
            if result is not False:
                self.last_message_send_lbl.set_text(f"Message sent at: {date}")
            else:
                self.last_message_send_lbl.set_text(f"Cannot send message: {result}")

        except smtplib.SMTPAuthenticationError as e:
            self.last_message_send_lbl.set_text(
                f"Cannot send message: {e.smtp_error.decode()}"
            )
        except Exception as e:
            self.last_message_send_lbl.set_text(f"Cannot send message: {e}")

        self.last_message_send = date
        return True

    def get_settings(self) -> Dict[str, Any]:
        settings = super().get_settings()
        settings["is_enabled"] = self.is_enabled
        return settings

    def set_settings(self, settings: Dict[str, Any]) -> None:
        super().set_settings(settings)
        self.enable_notifications_btn.set_checked(settings["is_enabled"])
        self.toggle_notifications(is_toggled=settings["is_enabled"])
