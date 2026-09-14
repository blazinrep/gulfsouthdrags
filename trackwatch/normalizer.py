"""Turn raw HTML into normalized visible text.

Stdlib only (html.parser). Goal is not a perfect readability extraction —
it's just good enough that meaningless formatting/markup churn doesn't look
like a content change, while dates, times, prices and schedule text survive
intact for the classifier to look at.
"""

import re
from html.parser import HTMLParser

# Tags whose entire contents are never visible text.
SKIP_CONTENT_TAGS = {"script", "style", "noscript", "template", "svg", "iframe"}

# <nav> is almost always link labels, not informational content — drop it
# so a menu-wording tweak doesn't look like a content change. <header> and
# <footer> are NOT skipped: small track sites routinely put the phone
# number, address, or "closed for the season" notices in the footer, and
# those are exactly the changes this bot exists to catch.
SKIP_CONTENT_TAGS |= {"nav"}

# Block-level tags: insert a newline boundary so words from adjacent blocks
# don't run together (e.g. a heading followed immediately by a paragraph).
BLOCK_TAGS = {
    "p", "div", "section", "article", "li", "tr", "table", "h1", "h2", "h3",
    "h4", "h5", "h6", "br", "hr", "ul", "ol", "blockquote", "form",
}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._skip_tag_stack = []
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_CONTENT_TAGS:
            self._skip_depth += 1
            self._skip_tag_stack.append(tag)
            return
        if tag in BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_startendtag(self, tag, attrs):
        if tag in BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_endtag(self, tag):
        if self._skip_tag_stack and tag == self._skip_tag_stack[-1]:
            self._skip_tag_stack.pop()
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag in BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_data(self, data):
        if self._skip_depth:
            return
        self.chunks.append(data)

    def error(self, message):  # pragma: no cover - HTMLParser API relic
        pass


_WS_RE = re.compile(r"[ \t\f\v]+")
_BLANKLINES_RE = re.compile(r"\n{2,}")


def html_to_text(html_source):
    """Extract visible text from an HTML document, stripped of script/style/
    nav/header/footer content, with collapsed whitespace."""
    parser = _TextExtractor()
    try:
        parser.feed(html_source)
        parser.close()
    except Exception:
        # Malformed HTML shouldn't crash a sweep; fall back to whatever
        # was extracted before the parser choked.
        pass
    text = "".join(parser.chunks)
    lines = [_WS_RE.sub(" ", line).strip() for line in text.split("\n")]
    text = "\n".join(line for line in lines if line)
    return _BLANKLINES_RE.sub("\n", text).strip()


def normalize_for_hashing(text):
    """A further-collapsed version used only for the change-detection hash,
    so things like a stray double space don't count as a 'change'."""
    collapsed = re.sub(r"\s+", " ", text).strip().lower()
    return collapsed
