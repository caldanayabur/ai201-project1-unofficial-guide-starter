"""
Milestone 3 -- Document Cleaning
Reads each raw JSON in documents/, removes boilerplate (forms, cookie banners,
country dropdowns, CTAs, pricing lines), fixes encoding artifacts, and writes
cleaned_text back into the same file.
"""

import json
import re
from pathlib import Path

DOCUMENTS_DIR = Path(__file__).parent / "documents"

# -- 1. Section-level cut points ---------------------------------------------
# Everything at or after the first match is discarded entirely.
_SECTION_CUTS = [
    # americancampus.com contact block
    "Stay\n\nConnected",
    "Stay Connected",
    # americancampus.com contact form error message (appears before country list)
    "Sorry, there has been an error submitting your request",
    # station42.us cookie banner
    "We are using cookies to give you the best experience",
    # 4050 Lofts / The Ivy -- end-of-page CTA
    "\nSay Hello",
    "\nWhere College Life",
]

# -- 2. Line-level patterns to drop ------------------------------------------
_DROP_LINE_RES = [re.compile(p, re.IGNORECASE) for p in [
    r"^skip\s+to\s+content$",
    r"^schedule\s+a\s+tour",
    r"^apply\s+(now|online)$",
    r"^(call|email)\s*$",
    r"^view\s*$",
    r"^view\s+all\s+available\s+floor\s+plans",
    r"^view\s+floor\s+plans$",
    r"^(virtual tours|photos|videos)$",
    r"^highlights$",
    r"^specials$",
    r"^now\s+leasing[!]?$",
    r"^leasing\s+now$",
    r"^\d+\s*$",                         # lone carousel numbers
    r"^\$[\d,]+\s*/?",                   # pricing lines ($820 / Month)
    r"^from\s*$",
    r"^/month\s*$",
    r"^/bed\s*$",
    r"^explore\s+floor\s+plans$",
    r"^(two|three|four|five)\s+bedroom$",  # floor-plan nav labels
    r"^[;]\s*$",                         # stray semicolons (The Ivy)
    r"^ask\s+about\s+our",               # promo banners
    r"^starting\s+at\s+\$",
    r"^limited\s+space",
    r"^prices\s+as\s+low\s+as",
    r"^contact\s+us",
    r"^explore\s+the\s+neighborhood$",
    r"^(choose\s+your|discover\s+the).*apartment",
    r"^check\s+out\s+your\s+new\s+apartment",
    r"^(academic center|fitness center|model apartment|swimming pool|recreation center)$",
    # Marketing section subheadings with no retrieval value
    r"^welcome\s+home$",
    r"^to\s+college\s+living\s+done\s+right$",
    r"^campus\s+life$",
    r"^with\s+style$",
    r"^fit,?\s+healthy\s+and\s+happy$",
    r"^the\s+lifestyle\s+you\s+want$",
    r"^prepare\s+to\s+succeed$",
    r"^where\s+you\s+want\s+to\s+be$",
]]

# -- 3. Mojibake / encoding artifact fixes -----------------------------------
# Two failure modes depending on how requests decoded the page character set.
#
# Mode A (Latin-1 / ISO-8859-1): UTF-8 bytes stored as raw codepoints U+00xx.
#   E.g. UTF-8 bytes E2 80 99 (U+2019 RIGHT SINGLE QUOTATION MARK) become the
#   three characters U+00E2 U+0080 U+0099 in the decoded Python string.
#
# Mode B (Windows-1252): UTF-8 bytes misread as cp1252 code points.
#   E.g. same bytes E2 80 99 become â (U+00E2) + € (U+20AC) + ™ (U+2122).
#
# Mode A patterns are applied first because they are more specific (contain
# U+0080–U+009F control-range characters) and do not overlap with Mode B.
_MOJIBAKE = [
    # -- Mode A: raw Latin-1 codepoints (U+00E2 U+0080 U+00xx) ---------------
    (re.compile("â"), "’"),  # right single quote U+2019
    (re.compile("â"), "“"),  # left double quote  U+201C
    (re.compile("â"), "”"),  # right double quote U+201D
    (re.compile("â"), "—"),  # em dash  U+2014
    (re.compile("â"), "–"),  # en dash  U+2013
    (re.compile("Â "),       " "),       # non-breaking space U+00A0
    (re.compile("Ã"),       ""),        # × close-button glyph U+00D7
    # -- Mode B: Windows-1252 sequences ---------------------------------------
    (re.compile("Â "),   " "),    # Â + NBSP  -> regular space
    (re.compile("Â "),        " "),    # Â + ASCII space -> regular space
    (re.compile("Â"),         ""),     # orphaned Â
    (re.compile(r"^Ã\s*$", re.MULTILINE), ""),  # Ã alone on a line
    (re.compile("â€™"), "’"),  # â€™ right single quote
    (re.compile("â€œ"), "“"),  # â€œ left double quote
    (re.compile("â€"), "”"),  # â€  right double quote
    (re.compile("â€“"), "—"),  # â€" em dash
    (re.compile("â€”"), "–"),  # â€" en dash
    (re.compile("â(?=\\s|$)"),    "’"),  # orphaned first byte
]


def _apply_section_cuts(text: str) -> str:
    for marker in _SECTION_CUTS:
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]
    return text


def _drop_junk_lines(text: str) -> str:
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if any(rx.match(stripped) for rx in _DROP_LINE_RES):
            continue
        out.append(line)
    return "\n".join(out)


def _fix_mojibake(text: str) -> str:
    for pattern, replacement in _MOJIBAKE:
        text = pattern.sub(replacement, text)
    return text


def _remove_duplicate_lines(text: str) -> str:
    """Drop consecutive identical (stripped) lines."""
    out, prev = [], None
    for line in text.splitlines():
        if line.strip() != prev:
            out.append(line)
            prev = line.strip()
    return "\n".join(out)


def _collapse_whitespace(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_text(raw_text: str) -> str:
    text = raw_text
    text = _fix_mojibake(text)
    text = _apply_section_cuts(text)
    text = _drop_junk_lines(text)
    text = _remove_duplicate_lines(text)
    text = _collapse_whitespace(text)
    return text


def main():
    json_files = sorted(DOCUMENTS_DIR.glob("*.json"))
    print(f"Cleaning {len(json_files)} documents in {DOCUMENTS_DIR}/\n")

    for path in json_files:
        doc = json.loads(path.read_text(encoding="utf-8"))

        if not doc.get("raw_text"):
            print(f"[SKIP]  {path.name} -- no raw_text")
            continue

        cleaned = clean_text(doc["raw_text"])
        doc["cleaned_text"] = cleaned
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

        raw_chars = len(doc["raw_text"])
        clean_chars = len(cleaned)
        removed_pct = 100 * (raw_chars - clean_chars) / raw_chars if raw_chars else 0
        print(f"[OK]  {path.name}")
        print(f"      {raw_chars:,} -> {clean_chars:,} chars  ({removed_pct:.0f}% removed)")

    print("\nDone.")


if __name__ == "__main__":
    main()
