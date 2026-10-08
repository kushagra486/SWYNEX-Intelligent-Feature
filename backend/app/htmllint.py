"""Structural HTML validity check. Browsers silently repair malformed markup,
so a headless-browser load alone can't tell a clean page from a broken one.
Uses only the stdlib parser: flags stray '<' in text, mismatched and
unclosed tags, and a missing doctype/title.
"""

from html.parser import HTMLParser

VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}
# Closing tag is optional in HTML, so a missing one isn't an error.
OPTIONAL_CLOSE = {"li", "p", "dt", "dd", "tr", "td", "th", "thead", "tbody", "tfoot", "option", "colgroup"}
RAW_TEXT = {"script", "style"}


class _Linter(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.errors: list[str] = []
        self.stack: list[tuple[str, int]] = []
        self.in_raw: str | None = None
        self.has_doctype = False
        self.has_title = False

    def handle_decl(self, decl):
        if decl.lower().startswith("doctype"):
            self.has_doctype = True

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self.has_title = True
        if tag in VOID:
            return
        self.stack.append((tag, self.getpos()[0]))
        if tag in RAW_TEXT:
            self.in_raw = tag

    def handle_startendtag(self, tag, attrs):
        if tag == "title":
            self.has_title = True

    def handle_endtag(self, tag):
        if self.in_raw:
            if tag != self.in_raw:
                return
            self.in_raw = None
        if tag in VOID:
            return
        line = self.getpos()[0]
        for i in range(len(self.stack) - 1, -1, -1):
            open_tag, open_line = self.stack[i]
            if open_tag == tag:
                for skipped, skipped_line in self.stack[i + 1:]:
                    if skipped not in OPTIONAL_CLOSE:
                        self.errors.append(f"line {skipped_line}: <{skipped}> is never closed before </{tag}> on line {line}")
                del self.stack[i:]
                return
        self.errors.append(f"line {line}: stray closing tag </{tag}> with no matching opener")

    def handle_data(self, data):
        if self.in_raw:
            return
        if "<" in data:
            self.errors.append(f"line {self.getpos()[0]}: stray '<' character in text content")

    def finish(self) -> list[str]:
        for tag, line in self.stack:
            if tag not in OPTIONAL_CLOSE:
                self.errors.append(f"line {line}: <{tag}> is never closed")
        if not self.has_doctype:
            self.errors.append("missing <!DOCTYPE html>")
        if not self.has_title:
            self.errors.append("missing <title>")
        return self.errors


def lint_html(html: str) -> list[str]:
    linter = _Linter()
    linter.feed(html)
    linter.close()
    return [f"html-lint: {e}" for e in linter.finish()]
