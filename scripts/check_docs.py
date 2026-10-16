#!/usr/bin/env python3
"""Check local documentation links and accessible SVG diagrams, without network access."""

import argparse
from pathlib import Path
import re
import subprocess
import unicodedata
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def prose(text):
    """Mask fenced examples while preserving line numbers for diagnostics."""
    lines = []
    fence = None
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = None
            lines.append("\n" if line.endswith("\n") else "")
        elif marker:
            fence = marker[1]
            lines.append("\n" if line.endswith("\n") else "")
        else:
            lines.append(line)
    return "".join(lines)


def anchors(text):
    result, counts = set(), {}
    for match in re.finditer(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", prose(text), re.M):
        heading = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", match[1])
        heading = re.sub(r"<[^>]+>", "", heading).lower()
        slug = "".join(c for c in heading if c in "-_" or unicodedata.category(c)[0] not in "PS")
        slug = slug.replace(" ", "-").strip()
        number = counts.get(slug, 0)
        counts[slug] = number + 1
        result.add(slug + ("-" + str(number) if number else ""))
    result.update(re.findall(r'\b(?:id|name)=[\'"]([^\'"]+)[\'"]', text))
    return result


def markdown_errors(path, root):
    text = prose(path.read_text(encoding="utf-8"))
    errors = []
    # Owned docs use inline links or explicit reference definitions. Remote URLs
    # are intentionally not requested: this check must work offline and in CI.
    pattern = r"!?\[[^\]\n]*\]\((<[^>\n]+>|[^\s)]+)(?:\s+[^)]+)?\)|^\s{0,3}\[[^\]]+\]:\s*(<[^>\n]+>|\S+)"
    for match in re.finditer(pattern, text, re.M):
        raw = (match[1] or match[2]).strip("<>")
        url = urlsplit(raw)
        if url.scheme or url.netloc:
            continue
        target = (path.parent / unquote(url.path)).resolve() if url.path else path
        line = text.count("\n", 0, match.start()) + 1
        label = "{}:{}".format(path.relative_to(root), line)
        try:
            target.relative_to(root)
        except ValueError:
            errors.append(label + ": link escapes repository: " + raw)
            continue
        if not target.exists():
            errors.append(label + ": missing local target: " + raw)
        elif url.fragment and target.suffix.lower() == ".md":
            if unquote(url.fragment) not in anchors(target.read_text(encoding="utf-8")):
                errors.append(label + ": missing heading: " + raw)
    return errors


def svg_errors(path, root):
    label = str(path.relative_to(root))
    try:
        svg = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return [label + ": invalid SVG: " + str(exc)]
    errors = []
    if svg.tag != "{http://www.w3.org/2000/svg}svg" or not svg.get("viewBox"):
        errors.append(label + ": SVG needs its namespace and viewBox")
    ids = {e.get("id"): e for e in svg.iter() if e.get("id")}
    names = svg.get("aria-labelledby", "").split()
    if svg.get("role") != "img" or not names or any(name not in ids for name in names):
        errors.append(label + ": diagram needs role=img and valid aria-labelledby")
    for tag in ("title", "desc"):
        node = svg.find("{http://www.w3.org/2000/svg}" + tag)
        if node is None or not "".join(node.itertext()).strip():
            errors.append(label + ": diagram needs a nonempty " + tag)
    for node in svg.iter():
        if node.tag.rsplit("}", 1)[-1] in ("script", "foreignObject", "image"):
            errors.append(label + ": diagrams must use self-contained vector elements")
        for key, value in node.attrib.items():
            if key.lower().startswith("on") or (key.endswith("href") and not value.startswith("#")):
                errors.append(label + ": external or executable SVG attribute")
    return errors


def check(root):
    names = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root
    ).decode().split("\0")
    errors, count = [], 0
    for name in sorted(set(names)):
        path = root / name
        if name and path.is_file() and path.suffix == ".md":
            count += 1
            errors.extend(markdown_errors(path, root))
        elif name.startswith("docs/assets/") and path.suffix == ".svg":
            count += 1
            errors.extend(svg_errors(path, root))
    return count, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    count, errors = check(ROOT)
    if errors:
        print("\n".join(errors))
        return 1
    print("Documentation checks passed ({} Markdown/SVG files; local links only).".format(count))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
