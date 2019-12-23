from typing import Dict, Any

HTML_HEAD = """
    <meta name="description" content="Clever camera">
    <meta name="author" content="Krzysztof Kolasiński">
    <link  href="/static:css/fa/css/all.min.css" rel="stylesheet">
    <script defer src="/static:css/fa/js/all.min.js"></script>
    <link href="/static:css/bootstrap4/css/bootstrap.min.css" rel="stylesheet">
    <script src="/static:js/jquery/jquery-3.4.1.slim.js"></script>
    <script src = "/static:js/popper/popper.min.js"></script>
    <script src="/static:css/bootstrap4/js/bootstrap.min.js"></script>
    """

APP_TABS_CSS = {"margin": "5px auto", "box-shadow": "0px 0px 3px 3px lightgray"}


DEFAULT_BUTTON_STYLE = {
    "margin": "1px 1px",
    "padding": "5px 5px",
    "font-size": "medium",
    "border-radius": "2px",
    "min-width": "160px",
}

HISTORY_SEARCH_STYLE = {
    "margin": "1px 1px",
    "padding": "5px 5px",
    "font-size": "medium",
}

SMALL_BUTTON_STYLE = {
    "margin": "1px 1px",
    "padding": "3px 5px",
    "font-size": "small",
    "border-radius": "2px",
    "box-shadow": "0px 0px 0px 0px #fff",
}

LOGGER_STYLE = {
    "margin": "5px 15px",
    "font-family": "monospace",
    "background": "dimgrey",
    "padding": "5px 10px",
    "color": "azure",
    "border-radius": "5px",
}

TOGGLE_BUTTON_STYLE = {
    "font-size": "small",
    "border-radius": "2px 2px 0px 0px",
    "box-shadow": "0px 0px 0px 0px #fff",
}


def apply_styles(widget: Any, styles: Dict[str, Any]) -> Any:
    widget.set_style(APP_TABS_CSS)
    return widget
