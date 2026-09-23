"""Unit tests for ProseMirror -> Markdown conversion."""

import json

from kaiten_mcp.tools.prosemirror_md import prosemirror_to_markdown


def _doc(*blocks):
    return {"type": "doc", "content": list(blocks)}


def _p(*inline):
    return {"type": "paragraph", "content": list(inline)}


def _t(text, *marks):
    node = {"type": "text", "text": text}
    if marks:
        node["marks"] = list(marks)
    return node


def _li(*blocks):
    return {"type": "list_item", "content": list(blocks)}


# Shape copied from a real Kaiten response (text translated to ASCII for RUF001).
REAL_DATA = json.dumps(
    {
        "type": "doc",
        "content": [
            {
                "type": "heading3",
                "attrs": {"id": "KB-HINT-b6debd39"},
                "content": [{"type": "text", "text": "KNOWLEDGE BASE HINT"}],
            },
            {
                "type": "bullet_list",
                "content": [
                    _li({"type": "paragraph", "attrs": {}, "content": [_t("Use search")]}),
                    _li(
                        {
                            "type": "paragraph",
                            "attrs": {},
                            "content": [
                                _t("Follow the "),
                                _t(
                                    "rules ",
                                    {
                                        "type": "link",
                                        "attrs": {
                                            "href": "https://wiki.example/rules",
                                            "title": None,
                                            "target": "_blank",
                                        },
                                    },
                                ),
                                _t("for each section"),
                            ],
                        }
                    ),
                ],
            },
            {"type": "paragraph", "attrs": {}},
            {"type": "paragraph", "attrs": {}},
        ],
    }
)


class TestTopLevel:
    def test_real_kaiten_document(self):
        assert prosemirror_to_markdown(REAL_DATA) == (
            "### KNOWLEDGE BASE HINT\n\n"
            "- Use search\n"
            "- Follow the [rules](https://wiki.example/rules) for each section"
        )

    def test_accepts_dict(self):
        assert prosemirror_to_markdown(_doc(_p(_t("hi")))) == "hi"

    def test_none_and_empty(self):
        assert prosemirror_to_markdown(None) == ""
        assert prosemirror_to_markdown("") == ""

    def test_invalid_json_returned_as_is(self):
        assert prosemirror_to_markdown("not json {") == "not json {"

    def test_non_dict_json(self):
        assert prosemirror_to_markdown("[1, 2]") == ""

    def test_garbage_children_ignored(self):
        assert prosemirror_to_markdown(_doc("junk", None, _p(_t("ok")))) == "ok"


class TestBlocks:
    def test_heading_with_level_attr(self):
        node = {"type": "heading", "attrs": {"level": 2}, "content": [_t("Title")]}
        assert prosemirror_to_markdown(_doc(node)) == "## Title"

    def test_heading_without_level_defaults_to_1(self):
        assert prosemirror_to_markdown(_doc({"type": "heading", "content": [_t("X")]})) == "# X"

    def test_empty_heading_dropped(self):
        assert prosemirror_to_markdown(_doc({"type": "heading3"}, _p(_t("a")))) == "a"

    def test_ordered_list_with_start(self):
        node = {
            "type": "ordered_list",
            "attrs": {"order": 3},
            "content": [_li(_p(_t("a"))), _li(_p(_t("b")))],
        }
        assert prosemirror_to_markdown(_doc(node)) == "3. a\n4. b"

    def test_nested_list(self):
        inner = {"type": "bullet_list", "content": [_li(_p(_t("b")))]}
        outer = {"type": "bullet_list", "content": [_li(_p(_t("a")), inner)]}
        assert prosemirror_to_markdown(_doc(outer)) == "- a\n  - b"

    def test_multiline_list_item(self):
        node = {"type": "bullet_list", "content": [_li(_p(_t("a")), _p(_t("b")))]}
        assert prosemirror_to_markdown(_doc(node)) == "- a\n  b"

    def test_blockquote(self):
        node = {"type": "blockquote", "content": [_p(_t("a")), _p(_t("b"))]}
        assert prosemirror_to_markdown(_doc(node)) == "> a\n>\n> b"

    def test_code_block(self):
        node = {"type": "code_block", "attrs": {"language": "py"}, "content": [_t("x = 1\ny = 2")]}
        assert prosemirror_to_markdown(_doc(node)) == "```py\nx = 1\ny = 2\n```"

    def test_horizontal_rule(self):
        doc = _doc(_p(_t("a")), {"type": "horizontal_rule"}, _p(_t("b")))
        assert prosemirror_to_markdown(doc) == "a\n\n---\n\nb"

    def test_block_image(self):
        node = {"type": "image", "attrs": {"src": "http://i/x.png", "alt": "pic"}}
        assert prosemirror_to_markdown(_doc(node)) == "![pic](http://i/x.png)"

    def test_table(self):
        def cell(kind, text):
            return {"type": kind, "content": [_p(_t(text))]}

        table = {
            "type": "table",
            "content": [
                {
                    "type": "table_row",
                    "content": [cell("table_header", "A"), cell("table_header", "B|C")],
                },
                {"type": "table_row", "content": [cell("table_cell", "1")]},
            ],
        }
        assert prosemirror_to_markdown(_doc(table)) == ("| A | B\\|C |\n| --- | --- |\n| 1 |  |")

    def test_empty_table(self):
        assert prosemirror_to_markdown(_doc({"type": "table", "content": []})) == ""

    def test_unknown_block_keeps_text(self):
        node = {"type": "callout", "content": [_p(_t("note"))]}
        assert prosemirror_to_markdown(_doc(node)) == "note"

    def test_unknown_block_with_inline_children_stays_one_line(self):
        node = {"type": "callout", "content": [_t("a "), _t("b", {"type": "strong"})]}
        assert prosemirror_to_markdown(_doc(node)) == "a **b**"


class TestInline:
    def test_marks(self):
        para = _p(
            _t("b", {"type": "strong"}),
            _t(" "),
            _t("i", {"type": "em"}),
            _t(" "),
            _t("s", {"type": "strike"}),
            _t(" "),
            _t("c", {"type": "code"}),
            _t(" "),
            _t("u", {"type": "underline"}),
        )
        assert prosemirror_to_markdown(_doc(para)) == "**b** *i* ~~s~~ `c` u"

    def test_mark_edge_whitespace_outside_markers(self):
        para = _p(_t("a"), _t(" b ", {"type": "strong"}), _t("c"), _t(" ", {"type": "em"}))
        assert prosemirror_to_markdown(_doc(para)) == "a **b** c"

    def test_link_without_href_is_plain_text(self):
        para = _p(_t("x", {"type": "link", "attrs": {}}))
        assert prosemirror_to_markdown(_doc(para)) == "x"

    def test_hard_break(self):
        para = _p(_t("a"), {"type": "hard_break"}, _t("b"))
        assert prosemirror_to_markdown(_doc(para)) == "a\nb"

    def test_inline_image(self):
        para = _p(_t("see "), {"type": "image", "attrs": {"src": "http://i/x.png"}})
        assert prosemirror_to_markdown(_doc(para)) == "see ![](http://i/x.png)"

    def test_unknown_inline_keeps_text(self):
        para = _p(_t("hi "), {"type": "mention", "content": [_t("@bob")]})
        assert prosemirror_to_markdown(_doc(para)) == "hi @bob"
