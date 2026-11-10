"""Extract acceptance criteria from a Markdown issue, PR description or spec.

Recognised, in order of preference:

* list items (bulleted or numbered, with or without checkboxes) under a heading
  such as "Acceptance criteria", "Definition of done", "Requirements",
  "Success criteria" or "Done when" (Markdown headings or a bold/colon line);
* Given/When/Then scenarios (consecutive Given/When/Then/And/But lines form one
  criterion);
* checkbox items (``- [ ]`` / ``- [x]``) anywhere, but only when the document
  has no acceptance-criteria section at all.

An explicit id at the start of an item (``AC-3: ...`` or ``[AC-3] ...``) is
kept; other criteria are numbered AC-1, AC-2, ... in order of appearance,
skipping explicit ids.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
SECTION_RE = re.compile(
    r"\b(acceptance(\s+criteria|\s+tests?)?|definition\s+of\s+done|requirements?"
    r"|success\s+criteria|done\s+when|expected\s+behaviou?r)\b",
    re.I,
)
PSEUDO_HEADING_RE = re.compile(r"^(?:\*\*|__)(.+?)(?:\*\*|__)\s*:?\s*$|^([A-Za-z][^.!?]{0,60}):\s*$")
LIST_RE = re.compile(r"^(\s*)(?:[-*+]|\d{1,3}[.)])\s+(.*\S)\s*$")
CHECK_RE = re.compile(r"^\[( |x|X)\]\s+(.*)$")
GWT_RE = re.compile(r"^\s*(?:[-*+]\s+)?(?:\*\*|__)?(given|when|then|and|but)(?:\*\*|__)?(?:\s*:)?\s+(\S.*)$", re.I)
TAG_RE = re.compile(r"^\[?(AC[-_ ]?(\d+))\]?\s*[:.)\-\u2013\u2014]?\s+(.*)$", re.I)
FENCE_RE = re.compile(r"^\s*(```|~~~)")


@dataclass
class Criterion:
    id: str
    text: str
    line: int
    kind: str  # "list" | "checkbox" | "scenario"
    checked: Optional[bool] = None
    explicit_id: bool = False
    in_section: bool = False
    _indent: int = field(default=0, repr=False, compare=False)

    def to_dict(self) -> dict:
        d = {"id": self.id, "text": self.text, "line": self.line, "kind": self.kind}
        if self.checked is not None:
            d["checked"] = self.checked
        d["explicit_id"] = self.explicit_id
        return d


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_criteria(markdown: str) -> List[Criterion]:
    found: List[Criterion] = []
    in_fence = False
    in_section = False
    section_level = 0
    current: Optional[Criterion] = None  # last list item, for continuation lines
    scenario: Optional[Criterion] = None

    def flush_scenario() -> None:
        nonlocal scenario
        scenario = None

    for lineno, raw in enumerate(markdown.splitlines(), 1):
        if FENCE_RE.match(raw):
            in_fence = not in_fence
            current = None
            flush_scenario()
            continue
        if in_fence:
            continue
        stripped = raw.strip()
        if not stripped:
            current = None
            flush_scenario()
            continue

        m = HEADING_RE.match(raw)
        if m:
            level = len(m.group(1))
            title = m.group(2)
            if SECTION_RE.search(title):
                in_section, section_level = True, level
            elif in_section and level <= section_level:
                in_section = False
            current = None
            flush_scenario()
            continue

        pm = PSEUDO_HEADING_RE.match(stripped)
        if pm and not LIST_RE.match(raw) and not GWT_RE.match(raw):
            title = pm.group(1) or pm.group(2)
            if SECTION_RE.search(title):
                in_section, section_level = True, 7
            elif in_section and section_level == 7:
                in_section = False
            current = None
            flush_scenario()
            continue

        g = GWT_RE.match(raw)
        if g and not CHECK_RE.match(stripped.lstrip("-*+ ")):
            kw = g.group(1).lower()
            if kw == "given" or (scenario is None and kw in ("when", "then")):
                scenario = Criterion("", _clean(stripped.lstrip("-*+ ")), lineno, "scenario",
                                     in_section=in_section)
                found.append(scenario)
                current = None
                continue
            if scenario is not None:
                scenario.text += " " + _clean(stripped.lstrip("-*+ "))
                continue
            # A stray "And ..." line with no scenario: treat as ordinary text below.

        lm = LIST_RE.match(raw)
        if lm:
            flush_scenario()
            indent = len(lm.group(1).expandtabs(4))
            body = lm.group(2)
            cm = CHECK_RE.match(body)
            if cm:
                current = Criterion("", _clean(cm.group(2)), lineno, "checkbox",
                                    checked=cm.group(1) in "xX", in_section=in_section,
                                    _indent=indent)
                found.append(current)
            elif in_section:
                if current is not None and indent > current._indent:
                    current.text += " " + _clean(body)
                else:
                    current = Criterion("", _clean(body), lineno, "list",
                                        in_section=True, _indent=indent)
                    found.append(current)
            else:
                current = None
            continue

        if current is not None and raw[:1] in (" ", "\t"):
            current.text += " " + _clean(stripped)
            continue
        if in_section and TAG_RE.match(stripped):
            current = Criterion("", _clean(stripped), lineno, "list", in_section=True)
            found.append(current)
            continue
        current = None
        flush_scenario()

    if any(c.in_section for c in found):
        found = [c for c in found if c.in_section or c.kind == "scenario"]

    return _assign_ids(found)


def _assign_ids(found: List[Criterion]) -> List[Criterion]:
    used = set()
    for c in found:
        tm = TAG_RE.match(c.text)
        if tm:
            c.id = "AC-%d" % int(tm.group(2))
            c.text = tm.group(3).strip()
            c.explicit_id = True
            used.add(c.id)
    n = 0
    for c in found:
        if c.id:
            continue
        n += 1
        while "AC-%d" % n in used:
            n += 1
        c.id = "AC-%d" % n
        used.add(c.id)
    return found
