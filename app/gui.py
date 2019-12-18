import base64
import binascii
import io
import mimetypes
import time
from typing import Union, Optional, List

import PIL
import PIL.Image
import remi.gui as gui
from remi import App

PILImage = PIL.Image.Image
BUTTON_STYLE = {
    "margin": "5px 5px",
    "padding": "5px 5px",
    "font-size": "medium",
    "border-radius": "5px",
}
SMALL_BUTTON_STYLE = {
    "margin": "5px 5px",
    "padding": "5px 5px",
    "font-size": "small",
    "border-radius": "5px",
    "background": "rgb(188, 125, 4)",
}


class CustomButton(gui.Button):
    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)
        self.set_style(style=BUTTON_STYLE)


class LoggerWidget(gui.ListView):
    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)
        self.history = []

    def update_history(self, label: gui.Label):
        self.history = self.history[-5:]
        self.history.append(label)
        self.empty()
        for label in self.history:
            self.append(label)

    def info(self, text: str):
        self.update_history(gui.Label(text))

    def warning(self, text: str):
        self.update_history(gui.Label(text))

    def error(self, text: str):
        self.update_history(gui.Label(text))


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


class CustomFormWidget(gui.Container):
    def __init__(self, *args):
        super(CustomFormWidget, self).__init__(*args)
        self.inputs = {}
        self.container = gui.Container()
        self.container.style.update(
            {"display": "block", "overflow": "auto", "margin": "5px"}
        )
        self.container.set_layout_orientation(gui.Container.LAYOUT_VERTICAL)
        self.append(self.container)

    def add_field_with_label(self, key: str, label_description: str, field: gui.Widget):
        """
        Adds a field to the dialog together with a descriptive label and a unique identifier.

        Note: You can access to the fields content calling the function GenericDialog.get_field(key).

        Args:
            key (str): The unique identifier for the field.
            label_description (str): The string content of the description label.
            field (Widget): The instance of the field Widget. It can be for example a TextInput or maybe
            a custom widget.
        """
        label = gui.Label(label_description)
        label.style["margin"] = "0px 5px"
        label.style["min-width"] = "30%"

        field.add_class("input")
        field.set_style({"height": "40px"})
        field.style["margin"] = "0px 5px"
        container = gui.HBox()
        container.style.update(
            {"justify-content": "space-between", "overflow": "auto", "padding": "3px",}
        )
        container.append(label, key="lbl" + key)
        container.append(field, key=key)
        self.container.append(container, key=key)
        self.inputs[key] = field

    def add_text(self, key: str, desc: str, text: str = "", **kwargs):
        label = gui.TextInput(**kwargs)

        label.set_text(text)
        self.add_field_with_label(key=key, label_description=desc, field=label)

    def add_numeric(
        self, key: str, desc: str, default_value=0, min_value=0, max_value=100, **kwargs
    ):
        spin = gui.SpinBox(
            default_value=default_value,
            min_value=min_value,
            max_value=max_value,
            **kwargs,
        )

        self.add_field_with_label(key=key, label_description=desc, field=spin)

    def get_value(self, key: str) -> Union[int, str, float]:
        field = self.inputs[key]
        if isinstance(field, gui.TextInput):
            return field.get_text()
        elif isinstance(field, gui.SpinBox):
            return field.get_value()
        raise NotImplementedError(f"Getter for {field} is not implemented.")

    def has_field(self, key: str) -> bool:
        return key in self.inputs

    def set_value(self, key: str, value: str):
        field = self.inputs[key]
        if isinstance(field, gui.TextInput):
            return field.set_text(value)
        elif isinstance(field, gui.SpinBox):
            return field.set_value(value)
        raise NotImplementedError(f"Setter for {field} is not implemented.")


class StaticPILImageWidget(gui.Image):
    """
    Use this when image does not have to reloaded frequently
    """

    def __init__(self, dummy_image_path: str, **kwargs):
        super(StaticPILImageWidget, self).__init__("", **kwargs)
        self.dummyImagePath = dummy_image_path
        self._buf = None
        self.image: PILImage = None
        if dummy_image_path is not None:
            self.set_image(image=None)

    def load(self, path: str):
        self.set_image(PIL.Image.open(path))

    def get_image(self) -> PILImage:
        return self.image

    def set_image(self, image: Optional[PILImage]) -> None:
        if image is None:
            image = PIL.Image.open(self.dummyImagePath)

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
    def __init__(self, app_instance: App, file_path_name=None, **kwargs):
        """
        :param app_instance:
        :param file_path_name:
        :param kwargs:
        """
        # self.app_instance = app_instance
        image = file_path_name
        super(PILImageWidget, self).__init__(image, **kwargs)
        self.app_instance = app_instance
        self.imagedata = None
        self.mimetype = None
        self.encoding = None
        if not image:
            return
        self.load(image)

    def load(self, file_path_name, use_js: bool = True):
        if type(file_path_name) is bytes or len(file_path_name) > 200:
            try:
                # here a base64 image is received
                self.imagedata = base64.b64decode(file_path_name, validate=True)
                self.attributes["src"] = "/%s/get_image_data?update_index=%s" % (
                    id(self),
                    str(time.time()),
                )
            except binascii.Error:
                # here an image data is received (opencv image)
                self.imagedata = file_path_name
                self.refresh()
        else:
            # here a filename is received
            self.mimetype, self.encoding = mimetypes.guess_type(file_path_name)
            with open(file_path_name, "rb") as f:
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

    def get_image_data(self, update_index):
        headers = {
            "Content-type": self.mimetype
            if self.mimetype
            else "application/octet-stream"
        }
        return [self.imagedata, headers]
