import pytest

from troubleshooter.ui.report_view import plain


@pytest.mark.parametrize(
    ("text", "escaped"),
    [
        ("[click](http://evil.example)", r"\[click\]\(http\://evil\.example\)"),
        ("![](http://evil.example/t.png)", r"\!\[\]\(http\://evil\.example/t\.png\)"),
        ("<script>alert(1)</script>", r"\<script\>alert\(1\)\</script\>"),
        ("**bold** _it_ `code`", r"\*\*bold\*\* \_it\_ \`code\`"),
        (":red[alarm] $x$", r"\:red\[alarm\] \$x\$"),
        ("# heading", r"\# heading"),
        ("back\\slash", "back\\\\slash"),
    ],
)
def test_escapes_markdown_syntax(text: str, escaped: str) -> None:
    assert plain(text) == escaped


def test_plain_words_are_unchanged() -> None:
    assert plain("Two milestones slipped this month") == "Two milestones slipped this month"


def test_empty_text_stays_empty() -> None:
    assert plain("") == ""
