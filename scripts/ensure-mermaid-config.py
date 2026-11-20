#!/usr/bin/env python3
"""Ensure Zensical's native Mermaid fence is enabled in a TOML config."""

from pathlib import Path
import re
import sys


MERMAID_FENCE = (
    '{ name = "mermaid", class = "mermaid", '
    'format = "pymdownx.superfences.fence_code_format" }'
)
SECTION = re.compile(r"(?m)^\[([^\[\]#]+)\][ \t]*(?:#.*)?$")


def _section_span(text: str, name: str) -> tuple[int, int] | None:
    sections = list(SECTION.finditer(text))
    for index, section in enumerate(sections):
        if section.group(1).strip() == name:
            end = sections[index + 1].start() if index + 1 < len(sections) else len(text)
            return section.start(), end
    return None


def _find_array_end(text: str, opening_bracket: int) -> int:
    depth = 0
    quote = None
    triple_quote = False
    escaped = False
    comment = False

    for index in range(opening_bracket, len(text)):
        char = text[index]
        if comment:
            if char in "\r\n":
                comment = False
            continue
        if quote:
            if triple_quote:
                if text.startswith(quote * 3, index):
                    quote = None
                    triple_quote = False
                continue
            if escaped:
                escaped = False
            elif char == "\\" and quote == '"':
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char == "#":
            comment = True
        elif char in "\"'":
            quote = char
            triple_quote = text.startswith(char * 3, index)
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return index

    raise ValueError("unterminated TOML custom_fences array")


def _append_fence(text: str, opening_bracket: int) -> str:
    closing_bracket = _find_array_end(text, opening_bracket)
    contents = text[opening_bracket + 1 : closing_bracket]
    trimmed = contents.rstrip()
    suffix = contents[len(trimmed) :]

    if not trimmed:
        if "\n" in contents or "\r" in contents:
            updated = f"\n  {MERMAID_FENCE}{suffix}"
        else:
            updated = MERMAID_FENCE
    elif "\n" in contents or "\r" in contents:
        separator = "" if trimmed.endswith(",") else ","
        updated = f"{trimmed}{separator}\n  {MERMAID_FENCE}{suffix}"
    else:
        separator = " " if trimmed.endswith(",") else ", "
        updated = f"{trimmed}{separator}{MERMAID_FENCE}{suffix}"

    return text[: opening_bracket + 1] + updated + text[closing_bracket:]


def _insert_setting(text: str, section_name: str, setting: str) -> str | None:
    span = _section_span(text, section_name)
    if span is None:
        return None

    start, end = span
    header_end = text.find("\n", start, end)
    if header_end < 0:
        header_end = end
        prefix = "\n"
    else:
        header_end += 1
        prefix = ""
    return text[:header_end] + prefix + setting + "\n" + text[header_end:]


def ensure_mermaid_config(text: str) -> str:
    """Add Mermaid to an existing superfences list or create the setting."""
    if re.search(r"\bname\s*=\s*['\"]mermaid['\"]", text):
        return text

    superfences_span = _section_span(
        text, "project.markdown_extensions.pymdownx.superfences"
    )
    if superfences_span is not None:
        start, end = superfences_span
        array = re.search(r"(?m)^\s*custom_fences\s*=\s*\[", text[start:end])
        if array:
            opening_bracket = start + array.end() - 1
            return _append_fence(text, opening_bracket)
        return _insert_setting(
            text,
            "project.markdown_extensions.pymdownx.superfences",
            f"custom_fences = [{MERMAID_FENCE}]",
        ) or text

    extensions_span = _section_span(text, "project.markdown_extensions")
    if extensions_span is not None:
        start, end = extensions_span
        array = re.search(
            r"(?m)^\s*pymdownx\.superfences\.custom_fences\s*=\s*\[",
            text[start:end],
        )
        if array:
            opening_bracket = start + array.end() - 1
            return _append_fence(text, opening_bracket)
        return _insert_setting(
            text,
            "project.markdown_extensions",
            f"pymdownx.superfences.custom_fences = [{MERMAID_FENCE}]",
        ) or text

    suffix = "" if not text or text.endswith("\n") else "\n"
    return (
        f"{text}{suffix}\n[project.markdown_extensions.pymdownx.superfences]\n"
        f"custom_fences = [{MERMAID_FENCE}]\n"
    )


def main(argv: list[str]) -> int:
    config = Path(argv[1]) if len(argv) > 1 else Path("zensical.toml")
    if not config.is_file():
        print(f"error: Zensical config not found: {config}", file=sys.stderr)
        return 1

    original = config.read_text(encoding="utf-8")
    updated = ensure_mermaid_config(original)
    if updated != original:
        config.write_text(updated, encoding="utf-8")
        print(f"Enabled native Mermaid fences in {config}.")
    else:
        print(f"Native Mermaid fences already enabled in {config}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
