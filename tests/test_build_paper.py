from html.parser import HTMLParser
from pathlib import Path

from scripts.build_paper import render


class StructureCheck(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.tags: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        self.tags.append(tag)
        if tag not in {"meta", "br", "img", "hr"}:
            self.stack.append(tag)

    def handle_endtag(self, tag) -> None:
        assert self.stack.pop() == tag


def test_full_paper_build_has_balanced_semantic_tables_and_lists() -> None:
    paper = Path(__file__).resolve().parents[1] / "paper" / "paper.md"
    document = render(paper.read_text())
    structure = StructureCheck()
    structure.feed(document)
    assert not structure.stack
    assert structure.tags.count("table") == 3
    assert structure.tags.count("ol") == 2
    assert '<pre class="table">' not in document
    assert "</table></div>" in document
    assert "<em>Communications of the ACM</em>" in document


def test_table_eof_and_escaping() -> None:
    document = render("| Field | Value |\n|---|---|\n| `<script>` | **safe** |")
    structure = StructureCheck()
    structure.feed(document)
    assert not structure.stack
    assert "<code>&lt;script&gt;</code>" in document
    assert "<strong>safe</strong>" in document
