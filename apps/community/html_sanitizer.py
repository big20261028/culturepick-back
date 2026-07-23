from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

import nh3
from django.conf import settings


ALLOWED_HTML_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "em",
    "h2",
    "h3",
    "hr",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "s",
    "strong",
    "u",
    "ul",
}
ALLOWED_HTML_ATTRIBUTES = {
    "a": {"href"},
    "img": {"alt", "src", "title"},
}
SAFE_URL_SCHEMES = {"http", "https", "mailto"}
REMOVE_WITH_CONTENT_TAGS = {
    "embed",
    "form",
    "iframe",
    "math",
    "noscript",
    "object",
    "script",
    "style",
    "svg",
    "template",
}


def _allowed_image_source(value: str) -> bool:
    value = value.strip()
    if not value:
        return False

    try:
        parsed = urlsplit(value)
    except ValueError:
        return False

    if parsed.username is not None or parsed.password is not None:
        return False

    if parsed.scheme:
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            return False
        allowed_hosts = {
            str(host).strip().lower().rstrip(".")
            for host in settings.COMMUNITY_ALLOWED_IMAGE_HOSTS
            if str(host).strip()
        }
        return parsed.hostname.lower().rstrip(".") in allowed_hosts

    # Protocol-relative URLs still load from an external host. Local editor
    # uploads must use the backend media path instead.
    if parsed.netloc:
        return False

    decoded_path = unquote(parsed.path)
    if ".." in decoded_path.split("/"):
        return False
    return decoded_path.startswith("/media/")


def _filter_attribute(tag: str, attribute: str, value: str) -> str | None:
    if tag == "img" and attribute == "src" and not _allowed_image_source(value):
        return None
    return value


_cleaner = nh3.Cleaner(
    tags=ALLOWED_HTML_TAGS,
    clean_content_tags=REMOVE_WITH_CONTENT_TAGS,
    attributes=ALLOWED_HTML_ATTRIBUTES,
    attribute_filter=_filter_attribute,
    strip_comments=True,
    link_rel=None,
    url_schemes=SAFE_URL_SCHEMES,
)


def sanitize_post_html(value: str) -> str:
    """Return a safe HTML fragment suitable for rendering with v-html."""

    return _cleaner.clean(value).strip()


class _MeaningfulContentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.has_meaningful_content = False

    def handle_data(self, data):
        visible_data = data.translate(
            str.maketrans("", "", "\u200b\u200c\u200d\u2060\ufeff")
        )
        if visible_data.strip():
            self.has_meaningful_content = True

    def handle_starttag(self, tag, attrs):
        if tag != "img":
            return
        attributes = dict(attrs)
        if attributes.get("src", "").strip():
            self.has_meaningful_content = True

    handle_startendtag = handle_starttag


def has_meaningful_html_content(value: str) -> bool:
    """Treat visible text or an image with a safe, non-empty src as content."""

    parser = _MeaningfulContentParser()
    parser.feed(value)
    parser.close()
    return parser.has_meaningful_content
