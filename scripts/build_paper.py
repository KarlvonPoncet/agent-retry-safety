#!/usr/bin/env python3
"""Build a dependency-free HTML rendering of the venue-neutral Markdown paper."""

from __future__ import annotations

import html
import re
from pathlib import Path

_INLINE = re.compile(r"`([^`]+)`|\*\*([^*]+)\*\*|\[([^]]+)\]\(([^)]+)\)")


def inline(text: str) -> str:
    escaped = html.escape(text)

    def replace(match: re.Match[str]) -> str:
        code, bold, label, url = match.groups()
        if code is not None:
            return f"<code>{code}</code>"
        if bold is not None:
            return f"<strong>{bold}</strong>"
        return f'<a href="{html.escape(url, quote=True)}">{label}</a>'

    return _INLINE.sub(replace, escaped)


def render(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    in_code = False
    in_list = False

    def flush_paragraph() -> None:
        if paragraph:
            output.append(f"<p>{inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            output.append("</ul>")
            in_list = False

    for line in lines:
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
        if line.startswith("- "):
            flush_paragraph()
            if not in_list:
                output.append("<ul>")
                in_list = True
            output.append(f"<li>{inline(line[2:])}</li>")
            continue
        if line.startswith("|"):
            flush_paragraph()
            close_list()
            output.append(f"<pre class=\"table\">{html.escape(line)}\n")
            continue
        paragraph.append(line)
    flush_paragraph()
    close_list()
    if in_code:
        output.append("</code></pre>")
    body = "\n".join(output)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Retry Safety for Tool-Using Agents</title>
<style>
body {{ max-width: 920px; margin: 2rem auto; padding: 0 1rem;
font: 16px/1.55 system-ui, sans-serif; color: #1d2733; }}
h1, h2, h3 {{ line-height: 1.2; color: #123b5d; }}
code, pre {{ background: #f2f5f7; border-radius: 4px; }}
code {{ padding: .1rem .25rem; }}
pre {{ padding: 1rem; overflow-x: auto; }}
pre.table {{ white-space: pre; }}
a {{ color: #075e9a; }}
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
