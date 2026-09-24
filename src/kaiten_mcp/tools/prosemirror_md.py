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


_WRAP = {"strike": "~~", "em": "*", "strong": "**"}


def _marks(node: dict) -> tuple[list[tuple[str, str]], bool]:
    """Wrapper marks outermost first, as (type, href), plus whether the node is code."""
    found = {m.get("type"): _attrs(m) for m in node.get("marks") or [] if isinstance(m, dict)}
    wraps = [(kind, "") for kind in _WRAP if kind in found]
    href = found.get("link", {}).get("href")
    if href:
        wraps.insert(0, ("link", str(href)))
    return wraps, "code" in found


def _code(text: str) -> str:
    # ponytail: text containing "``" would need a longer fence; not seen in Kaiten docs
    return f"`` {text} ``" if "`" in text else f"`{text}`"


def _image(node: dict) -> str:
    attrs = _attrs(node)
    return f"![{attrs.get('alt') or ''}]({attrs.get('src') or ''})"


def _atom(node: dict) -> str:
    # ponytail: unknown inline (mention, emoji) degrades to child text or attrs label
    attrs = _attrs(node)
    label = next((attrs[k] for k in ("label", "text", "name", "title") if attrs.get(k)), "")
    text = _inline(_children(node)) or str(label)
    # file / inline_card_link carry the target only in attrs.url
    url = attrs.get("url")
    return f"[{text or url}]({url})" if url else text


def _inline(nodes: list[dict]) -> str:
    """Render inline nodes; marks stay open across adjacent text nodes that share them."""
    out = ""
    stack: list[tuple[str, str]] = []  # open wrapper marks, outermost first

    def close(keep: int) -> None:
        nonlocal out
        body = out.rstrip()  # edge whitespace goes outside the closing markers
        closers = "".join(
            f"]({href})" if kind == "link" else _WRAP[kind]
            for kind, href in reversed(stack[keep:])
        )
        out = body + closers + out[len(body) :]
        del stack[keep:]

    for node in nodes:
        kind = node.get("type")
        if kind != "text":
            close(0)
            piece = (
                "\n" if kind == "hard_break" else _image(node) if kind == "image" else _atom(node)
            )
            # Kaiten puts attached files side by side with no text between them
            if piece.startswith("[") and out.endswith(")"):
                out += " "
            out += piece
            continue
        text = str(node.get("text") or "")
        core = text.strip()
        if not core:
            out += text
            continue
        wraps, code = _marks(node)
        keep = 0
        while keep < len(stack) and stack[keep] in wraps:
            keep += 1
        close(keep)
        opens = [w for w in wraps if w not in stack]
        stack.extend(opens)
        lead = text[: len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()) :]
        markers = "".join("[" if k == "link" else _WRAP[k] for k, _ in opens)
        out += lead + markers + (_code(core) if code else core) + trail
    close(0)
    return out


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
        level = max(1, min(6, int(heading.group(1) or _attrs(node).get("level") or 1)))
        text = _inline(_children(node)).replace("\n", " ")
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
    if not isinstance(data, dict):
        return ""
    try:
        return _block(data).strip()
    except (TypeError, ValueError, AttributeError):
        # Malformed attrs (wrong types) must not make the document unreadable.
        return _plain(data).strip()


def _plain(node: dict) -> str:
    """Bare text of a node tree: fallback when the Markdown rendering fails."""
    if node.get("type") == "text":
        return str(node.get("text") or "")
    children = _children(node)
    sep = "" if any(c.get("type") == "text" for c in children) else "\n"
    return sep.join(_plain(c) for c in children)
