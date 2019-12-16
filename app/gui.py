import io
import time
from typing import Union, Optional

import PIL
import PIL.Image
import remi.gui as gui
from remi import App

PILImage = PIL.Image.Image
BUTTON_STYLE = {"margin": "5px 5px", "padding": "5px 5px", "font-size": "medium"}


class CustomButton(gui.Button):
    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)
        self.set_style(style=BUTTON_STYLE)


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


class CustomFormWidget(gui.Widget):
    def __init__(self, *args):
        super(CustomFormWidget, self).__init__(*args)
        self.inputs = {}
        self.container = gui.Widget()
        self.container.style.update(
            {"display": "block", "overflow": "auto", "margin": "5px"}
        )
        self.container.set_layout_orientation(gui.Widget.LAYOUT_VERTICAL)
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


class ConfigInfoWidget(gui.Widget):
    def __init__(self, app: App, parent: gui.Widget, html_text: str, *args):
        super(ConfigInfoWidget, self).__init__(*args)
        self.app = app
        self.parent = parent
        self.style.update({"display": "block", "overflow": "auto", "margin": "5px"})
        self.set_layout_orientation(gui.Widget.LAYOUT_VERTICAL)
        self.back_button = CustomButton("Back")
        self.back_button.onclick.do(self.exit)
        self.append(self.back_button)

        self.title_label = gui.TextInput()
        self.title_label.set_enabled(False)
        self.html_content = PlainHTML(html_text)
        self.append(self.title_label)
        self.append(self.html_content)

    def set_title(self, text: str):
        self.title_label.set_text(text)

    def exit(self, emitter):
        self.app.set_root_widget(self.parent)


class WarningBoxWidget(gui.Widget):
    def __init__(self, app: App, parent: gui.Widget, title: str, msg: str, *args):
        super(WarningBoxWidget, self).__init__(*args)
        self.app = app
        self.parent = parent
        self.style.update({"display": "block", "overflow": "auto", "margin": "5px"})
        self.set_layout_orientation(gui.Widget.LAYOUT_VERTICAL)
        self.back_button = CustomButton("Back")
        self.back_button.onclick.do(self.exit)
        self.append(self.back_button)

        self.title = Header(title)
        self.message = PlainHTML(msg)
        self.append(self.title)
        self.append(self.message)

    def exit(self, emitter):
        self.app.set_root_widget(self.parent)

    def show(self):
        self.app.set_root_widget(self)


class YesNoMessageBoxWidget(gui.Widget):
    def __init__(
        self, app: App, parent: gui.Widget, title: str, msg: str, accept_fn, *args
    ):
        super(YesNoMessageBoxWidget, self).__init__(*args)
        self.app = app
        self.parent = parent
        self.accept_fn = accept_fn
        self.style.update({"display": "block", "overflow": "auto", "margin": "5px"})
        self.set_layout_orientation(gui.Widget.LAYOUT_VERTICAL)
        self.ok_button = CustomButton("Yes")
        self.ok_button.onclick.do(self.accept)
        self.no_button = CustomButton("No")
        self.no_button.onclick.do(self.exit)

        self.title = Header(title)
        self.message = PlainHTML(msg)
        self.append(self.title)
        self.append(HorizontalLine())
        self.append(self.message)
        self.append(HorizontalLine())
        hlayout = gui.HBox()
        hlayout.append(self.no_button)
        hlayout.append(self.ok_button)
        self.append(hlayout)

    def exit(self, emitter):
        self.app.set_root_widget(self.parent)

    def accept(self, emitter):
        self.accept_fn()
        self.app.set_root_widget(self.parent)

    def show(self):
        self.app.set_root_widget(self)


class PILImageViewerWidget(gui.Image):
    def __init__(self, dummy_image_path: str, **kwargs):
        super(PILImageViewerWidget, self).__init__("", **kwargs)
        self.dummyImagePath = dummy_image_path
        self._buf = None
        self.image: PILImage = None
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
