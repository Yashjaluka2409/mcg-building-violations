"""Jinja2 environment for the notice templates (app/templates/notices/*.html).

The templates were converted from the Django edition; the handful of Django filters they use are provided
here with the same semantics: date, default, linebreaksbr, truncatechars (join / lower / safe are built in).
"""
from __future__ import annotations

from datetime import date, datetime
from markupsafe import Markup, escape

from jinja2 import ChainableUndefined, Environment, FileSystemLoader, select_autoescape

from app.core.config import APP_DIR
from app.core.timeutil import aware, localtime

_DJANGO_TO_STRFTIME = {"d": "%d", "j": "%-d", "m": "%m", "n": "%-m", "Y": "%Y", "y": "%y", "H": "%H", "G": "%-H", "i": "%M", "s": "%S",
                       "M": "%b", "F": "%B", "D": "%a", "l": "%A", "A": "%p", "a": "%p", "N": "%b"}


def django_date(value, fmt: str = "d-m-Y") -> str:
    """Django's |date filter for the format characters used in the templates; datetimes are shown in local time."""
    if not value:
        return ""
    if isinstance(value, datetime):
        value = localtime(aware(value))
    elif not isinstance(value, date):
        return str(value)
    out = []
    for ch in fmt:
        out.append(value.strftime(_DJANGO_TO_STRFTIME[ch]) if ch in _DJANGO_TO_STRFTIME else ch)
    return "".join(out)


def django_default(value, arg=""):
    """Django semantics: replace when the value is falsy (None, "", 0, empty list), not only when undefined."""
    return arg if not value else value


def linebreaksbr(value) -> Markup:
    if value is None:
        return Markup("")
    text = escape(str(value)).replace("\r\n", "\n")
    return Markup(text.replace("\n", "<br>"))


def truncatechars(value, n: int) -> str:
    s = "" if value is None else str(value)
    n = int(n)
    return s if len(s) <= n else s[: max(n - 1, 0)] + "…"


env = Environment(
    loader=FileSystemLoader(str(APP_DIR / "templates")),
    autoescape=select_autoescape(["html", "xml"], default=True),
    undefined=ChainableUndefined,
    trim_blocks=False, lstrip_blocks=False,
)
env.filters.update({"date": django_date, "default": django_default, "linebreaksbr": linebreaksbr, "truncatechars": truncatechars})


def render(template_name: str, ctx: dict) -> str:
    return env.get_template(template_name).render(**ctx)
