#!/usr/bin/env python3
"""Build a dependency-free HTML rendering of the venue-neutral Markdown paper."""

from __future__ import annotations

import html
import re
from pathlib import Path

_INLINE = re.compile(
    r"`([^`]+)`|\*\*([^*]+)\*\*|\[([^]]+)\]\(([^)]+)\)"
    r"|\*([^*]+)\*|(https?://[^\s<>]+)"
)


def inline(text: str) -> str:
    escaped = html.escape(text)

    def replace(match: re.Match[str]) -> str:
        code, bold, label, url, emphasis, bare_url = match.groups()
        if code is not None:
            return f"<code>{code}</code>"
        if bold is not None:
            return f"<strong>{bold}</strong>"
        if emphasis is not None:
            return f"<em>{emphasis}</em>"
        if bare_url is not None:
            return f'<a href="{bare_url}">{bare_url}</a>'
        return f'<a href="{url}">{label}</a>'

    return _INLINE.sub(replace, escaped)


def render(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    in_code = False
    list_tag: str | None = None
    in_table = False

    def flush_paragraph() -> None:
        if paragraph:
            output.append(f"<p>{inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_tag
        if list_tag:
            output.append(f"</{list_tag}>")
            list_tag = None

    def close_table() -> None:
        nonlocal in_table
        if in_table:
            output.append("</tbody></table></div>")
            in_table = False

    for line in lines:
        if in_table and not line.startswith("|"):
            close_table()
        if line.startswith("```"):
            flush_paragraph()
            close_list()
            if in_code:
                output.append("</code></pre>")
            else:
                output.append("<pre><code>")
            in_code = not in_code
            continue
        if in_code:
            output.append(html.escape(line) + "\n")
            continue
        if not line.strip():
            flush_paragraph()
            close_list()
            continue
        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            output.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
            continue
        list_item = re.match(r"^(?:(-) |\d+\. )(.*)$", line)
        if list_item:
            flush_paragraph()
            tag = "ul" if list_item.group(1) else "ol"
            if list_tag != tag:
                close_list()
                output.append(f"<{tag}>")
                list_tag = tag
            output.append(f"<li>{inline(list_item.group(2))}</li>")
            continue
        if line.startswith("|"):
            flush_paragraph()
            close_list()
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                continue
            if not in_table:
                output.append('<div class="table-wrap"><table><thead><tr>')
                output.extend(
                    f'<th scope="col">{inline(cell)}</th>' for cell in cells
                )
                output.append("</tr></thead><tbody>")
                in_table = True
            else:
                output.append("<tr>")
                output.extend(f"<td>{inline(cell)}</td>" for cell in cells)
                output.append("</tr>")
            continue
        paragraph.append(line)
    flush_paragraph()
    close_list()
    close_table()
    if in_code:
        output.append("</code></pre>")
    body = "\n".join(output)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent Retry Conformance Harness</title>
<style>
body {{ max-width: 920px; margin: 2rem auto; padding: 0 1rem;
font: 16px/1.55 system-ui, sans-serif; color: #1d2733; }}
h1, h2, h3 {{ line-height: 1.2; color: #123b5d; }}
code, pre {{ background: #f2f5f7; border-radius: 4px; }}
code {{ padding: .1rem .25rem; overflow-wrap: anywhere; }}
pre {{ padding: 1rem; overflow-x: auto; }}
.table-wrap {{ overflow-x: auto; margin: 1.5rem 0; }}
table {{ width: 100%; border-collapse: collapse; font-size: .9rem; }}
th, td {{ text-align: left; padding: .6rem; border-bottom: 1px solid #dce3e9; }}
th {{ background: #f2f5f7; color: #123b5d; }}
a {{ color: #075e9a; }}
@media print {{ body {{ max-width: none; margin: 0; font-size: 11pt; }}
thead {{ display: table-header-group; }} tr {{ break-inside: avoid; }}
pre {{ white-space: pre-wrap; }} .table-wrap {{ overflow: visible; }} }}
</style></head><body>{body}</body></html>
"""


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    source = root / "paper" / "paper.md"
    destination = root / "paper" / "paper.html"
    destination.write_text(render(source.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"built {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
