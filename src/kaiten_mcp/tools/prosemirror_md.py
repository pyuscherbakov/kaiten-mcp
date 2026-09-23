"""Render Kaiten document bodies (ProseMirror JSON) as Markdown for reading."""

import json
import re
from typing import Any

# Kaiten stores headings both as {"type": "heading", attrs.level} and as "heading3".
_HEADING = re.compile(r"^heading([1-6])?$")


def _children(node: dict) -> list[dict]:
    return [c for c in node.get("content") or [] if isinstance(c, dict)]


def _attrs(node: dict) -> dict:
    return node.get("attrs") or {}


def _text(node: dict) -> str:
    """Render a text node; edge whitespace stays outside the markers."""
    text = str(node.get("text", ""))
    core = text.strip()
    if not core:
        return text
    marks = {m.get("type"): _attrs(m) for m in node.get("marks") or [] if isinstance(m, dict)}
    if "code" in marks:
        core = f"`{core}`"
    if "strong" in marks:
        core = f"**{core}**"
    if "em" in marks:
        core = f"*{core}*"
    if "strike" in marks:
        core = f"~~{core}~~"
    href = marks.get("link", {}).get("href")
    if href:
        core = f"[{core}]({href})"
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()) :]
    return lead + core + trail


def _image(node: dict) -> str:
    attrs = _attrs(node)
    return f"![{attrs.get('alt') or ''}]({attrs.get('src') or ''})"


def _inline(nodes: list[dict]) -> str:
    out = []
    for node in nodes:
        kind = node.get("type")
        if kind == "text":
            out.append(_text(node))
        elif kind == "hard_break":
            out.append("\n")
        elif kind == "image":
            out.append(_image(node))
        else:
            # ponytail: unknown inline (mention, emoji) degrades to child text or attrs label
            attrs = _attrs(node)
            label = next(
                (attrs[k] for k in ("label", "text", "name", "title") if attrs.get(k)), ""
            )
            out.append(_inline(_children(node)) or str(label))
    return "".join(out)


def _blocks(nodes: list[dict], sep: str = "\n\n") -> str:
    return sep.join(b for b in (_block(n) for n in nodes) if b.strip())


def _list(node: dict, ordered: bool) -> str:
    start = _attrs(node).get("order") or 1
    items = []
    for i, item in enumerate(_children(node)):
        marker = f"{start + i}. " if ordered else "- "
        body = _blocks(_children(item), "\n").replace("\n", "\n" + " " * len(marker))
        items.append(marker + body)
    return "\n".join(items)


def _cell(cell: dict) -> str:
    return _blocks(_children(cell), " ").replace("\n", " ").replace("|", "\\|")


def _table(node: dict) -> str:
    rows = [[_cell(c) for c in _children(r)] for r in _children(node)]
    rows = [r for r in rows if r]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    lines = ["| " + " | ".join(r + [""] * (width - len(r))) + " |" for r in rows]
    lines.insert(1, "|" + " --- |" * width)
    return "\n".join(lines)


def _block(node: dict) -> str:
    kind = str(node.get("type", ""))
    heading = _HEADING.match(kind)
    if heading:
        level = int(heading.group(1) or _attrs(node).get("level") or 1)
        text = _inline(_children(node))
        return f"{'#' * level} {text}" if text.strip() else ""
    if kind == "paragraph":
        return _inline(_children(node))
    if kind in ("bullet_list", "ordered_list"):
        return _list(node, kind == "ordered_list")
    if kind == "blockquote":
        inner = _blocks(_children(node)).split("\n")
        return "\n".join(f"> {line}" if line else ">" for line in inner)
    if kind == "code_block":
        code = "".join(str(c.get("text", "")) for c in _children(node))
        return f"```{_attrs(node).get('language') or ''}\n{code}\n```"
    if kind == "horizontal_rule":
        return "---"
    if kind == "table":
        return _table(node)
    if kind in ("text", "hard_break", "image"):
        return _inline([node])
    # doc and unknown blocks (callouts etc.): keep whatever text is inside
    children = _children(node)
    if any(c.get("type") == "text" for c in children):
        return _inline(children)
    return _blocks(children)


def prosemirror_to_markdown(data: Any) -> str:
    """Convert a ProseMirror doc (dict or its JSON string, as Kaiten returns it) to Markdown.

    Invalid JSON strings are returned unchanged; anything else non-dict yields "".
    """
    if isinstance(data, str):
        raw = data
        try:
            data = json.loads(raw)
        except ValueError:
            return raw
    return _block(data).strip() if isinstance(data, dict) else ""
