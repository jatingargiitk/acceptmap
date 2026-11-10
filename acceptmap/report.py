"""Markdown and JSON reports."""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Sequence

from . import __version__
from .mapper import CODE_ONLY, MAPPED, STATUSES, TEST_ONLY, UNMAPPED, Evidence, Mapping

_ICON = {MAPPED: "✅", CODE_ONLY: "🟡", TEST_ONLY: "🟡", UNMAPPED: "❌"}


def summary(mappings: Sequence[Mapping]) -> Dict[str, int]:
    out = {s: 0 for s in STATUSES}
    for m in mappings:
        out[m.status] += 1
    out["total"] = len(mappings)
    return out


def _cell(text: str, limit: int = 90) -> str:
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text.replace("|", "\\|")


def _loc(e: Evidence) -> str:
    s = "`%s:%d`" % (e.path, e.line)
    if e.kind == "removed":
        s += " (removed)"
    return s


def _ev_cell(evs: List[Evidence]) -> str:
    if not evs:
        return "—"
    parts = []
    for e in evs:
        p = _loc(e)
        if e.symbol:
            p += " `%s`" % e.symbol.replace("|", "\\|").replace("`", "'")
        parts.append(p)
    return "<br>".join(parts)


def to_markdown(mappings: Sequence[Mapping], title: Optional[str] = None,
                spec: Optional[str] = None, details: bool = True) -> str:
    s = summary(mappings)
    lines = []
    lines.append("## %s" % (title or "Acceptance criteria coverage"))
    lines.append("")
    if not mappings:
        lines.append("No acceptance criteria found%s." % (" in `%s`" % spec if spec else ""))
        return "\n".join(lines) + "\n"
    lines.append(
        "**%d/%d mapped to code and tests** · %d code only · %d tests only · %d unmapped"
        % (s[MAPPED], s["total"], s[CODE_ONLY], s[TEST_ONLY], s[UNMAPPED])
    )
    lines.append("")
    lines.append("| ID | Status | Criterion | Code | Tests |")
    lines.append("|----|--------|-----------|------|-------|")
    for m in mappings:
        lines.append("| %s | %s %s | %s | %s | %s |" % (
            m.criterion.id, _ICON[m.status], m.status, _cell(m.criterion.text),
            _ev_cell(m.code), _ev_cell(m.tests),
        ))
    unmapped = [m for m in mappings if m.status == UNMAPPED]
    if unmapped:
        lines.append("")
        lines.append("### Unmapped criteria")
        lines.append("")
        for m in unmapped:
            why = ("no matchable terms" if not m.terms
                   else "no changed line matched (terms: %s)" % ", ".join(m.word(t) for t in m.terms))
            lines.append("- **%s** %s — %s" % (m.criterion.id, _cell(m.criterion.text, 200), why))
    if details:
        lines.append("")
        lines.append("<details><summary>Evidence</summary>")
        lines.append("")
        for m in mappings:
            if not (m.code or m.tests):
                continue
            lines.append("**%s** %s" % (m.criterion.id, _cell(m.criterion.text, 200)))
            lines.append("")
            for label, evs in (("code", m.code), ("test", m.tests)):
                for e in evs:
                    why = ("tag %s" % m.criterion.id if e.via == "tag"
                           else "literal" if e.via == "literal" and not e.matched
                           else ", ".join(m.word(t) for t in e.matched))
                    if e.via == "literal" and e.matched:
                        why = "literal; " + why
                    lines.append("- %s %s — `%s` (%s)" % (
                        label, _loc(e), _cell(e.text.strip(), 100).replace("`", "'"), why))
            lines.append("")
        lines.append("</details>")
    lines.append("")
    lines.append("<sub>acceptmap %s · heuristic term matching; review before relying on it.</sub>" % __version__)
    return "\n".join(lines) + "\n"


def to_json(mappings: Sequence[Mapping], spec: Optional[str] = None) -> str:
    doc = {
        "tool": "acceptmap",
        "version": __version__,
        "spec": spec,
        "summary": summary(mappings),
        "criteria": [m.to_dict() for m in mappings],
    }
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def criteria_list(mappings_or_criteria) -> str:
    out = []
    for c in mappings_or_criteria:
        flag = ""
        if c.checked is not None:
            flag = " [x]" if c.checked else " [ ]"
        out.append("%s%s (line %d, %s) %s" % (c.id, flag, c.line, c.kind, c.text))
    return "\n".join(out) + ("\n" if out else "")
