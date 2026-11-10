"""Map criteria to changed lines.

Matching is heuristic and deterministic:

* a changed line is evidence for a criterion when it shares at least
  ``min_terms`` distinct terms with it (terms of the enclosing test name and of
  the file path count too), or contains one of the criterion's backticked
  literals verbatim, or carries the criterion's id as a tag (``AC-3``,
  ``test_ac3_...``) in a test name or a comment;
* lines in test files become test evidence, everything else code evidence;
* import/use lines are ignored (they name everything and prove nothing);
* scores are IDF-weighted twice: terms on many changed lines count less, and
  terms shared by many criteria count less;
* evidence is collapsed to the best line per (file, function), and each such
  unit only counts for the criteria it fits best: a criterion keeps the unit if
  its score there is at least ``share`` (default 0.5) of the best score any
  criterion got for that unit.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .criteria import Criterion
from .diff import FileDiff, Line
from .terms import literals, same_term, term_words, terms

MAPPED = "MAPPED"
CODE_ONLY = "CODE-ONLY"
TEST_ONLY = "TEST-ONLY"
UNMAPPED = "UNMAPPED"
STATUSES = (MAPPED, CODE_ONLY, TEST_ONLY, UNMAPPED)

_IMPORT_RE = re.compile(
    r"^\s*(?:import\s|from\s+\S+\s+import\s|use\s+[\w:{}, ]+;|#include\s|require\(|"
    r"(?:const|let|var)\s+[\w{}, ]+=\s*require\()"
)
_TAG_RE = re.compile(r"(?<![A-Za-z0-9])ac[-_ ]?0*(\d+)(?![0-9])", re.I)


@dataclass
class Evidence:
    path: str
    line: int
    text: str
    kind: str  # "added" | "removed"
    symbol: Optional[str]
    matched: List[str]
    via: str  # "terms" | "literal" | "tag"
    score: float

    def to_dict(self) -> dict:
        return {
            "path": self.path, "line": self.line, "kind": self.kind,
            "symbol": self.symbol, "text": self.text.strip(),
            "matched": self.matched, "via": self.via, "score": round(self.score, 3),
        }


@dataclass
class Mapping:
    criterion: Criterion
    terms: List[str]
    literals: List[str]
    code: List[Evidence] = field(default_factory=list)
    tests: List[Evidence] = field(default_factory=list)
    words: Dict[str, str] = field(default_factory=dict)  # term -> word in the criterion

    def word(self, term: str) -> str:
        return self.words.get(term, term)

    @property
    def status(self) -> str:
        if self.code and self.tests:
            return MAPPED
        if self.code:
            return CODE_ONLY
        if self.tests:
            return TEST_ONLY
        return UNMAPPED

    def to_dict(self) -> dict:
        d = self.criterion.to_dict()
        d.update({
            "status": self.status, "terms": self.terms, "literals": self.literals,
            "code": [e.to_dict() for e in self.code],
            "tests": [e.to_dict() for e in self.tests],
        })
        return d


@dataclass
class _Unit:
    """Something evidence can point at: one changed code line, or one test function."""

    is_test: bool
    lines: List[Line]
    name_terms: Set[str]
    body_terms: Set[str]
    tags: Set[str]
    text: str  # lowercased text of all lines, for literal matching
    line_terms: List[Set[str]]
    path_terms: Set[str] = field(default_factory=set)


def _tags(text: str) -> Set[str]:
    return {"AC-%d" % int(n) for n in _TAG_RE.findall(text)}


def _match(cterms: Sequence[str], pool: Set[str]) -> List[str]:
    out = []
    for t in cterms:
        if t in pool or any(same_term(t, p) for p in pool):
            out.append(t)
    return out


def _units(files: Sequence[FileDiff]) -> List[_Unit]:
    units: List[_Unit] = []
    tests: Dict[Tuple[str, str], List[Line]] = {}
    for f in files:
        if f.binary:
            continue
        for ln in f.lines:
            if not ln.text.strip() or _IMPORT_RE.match(ln.text):
                continue
            if f.is_test and ln.symbol:
                key = (f.path, ln.symbol)
                if key not in tests:
                    tests[key] = []
                    units.append(_Unit(True, tests[key], set(terms(ln.symbol)), set(),
                                       _tags(ln.symbol), "", []))
                tests[key].append(ln)
            else:
                units.append(_Unit(f.is_test, [ln], set(), set(), set(), "", []))
    for u in units:
        u.line_terms = [set(terms(ln.text)) for ln in u.lines]
        u.body_terms = set().union(*u.line_terms) - u.name_terms
        u.text = "\n".join(ln.text for ln in u.lines).lower()
        u.path_terms = set(terms(u.lines[0].path.rsplit(".", 1)[0]))
        for ln in u.lines:
            if _tag_allowed(u, ln):
                u.tags |= _tags(ln.text)
    return units


_COMMENT_RE = re.compile(r"^\s*(?:#|//|/\*|\*|--|;)")
_DOC_EXTS = (".md", ".markdown", ".rst", ".txt", ".adoc", ".html")


def _tag_allowed(u: _Unit, ln: Line) -> bool:
    """``AC-n`` tags count in added comment lines of code and tests (and in test names).

    Docs, reports and string literals often mention criterion ids without
    implementing them.
    """
    if ln.kind != "added" or ln.path.lower().endswith(_DOC_EXTS):
        return False
    return bool(_COMMENT_RE.match(ln.text))


def map_criteria(
    criteria: Sequence[Criterion],
    files: Sequence[FileDiff],
    min_terms: int = 2,
    max_evidence: int = 3,
    share: float = 0.5,
) -> List[Mapping]:
    units = _units(files)

    # Line-level IDF: terms on many changed lines say little.
    n = sum(len(u.lines) for u in units) or 1
    df: Dict[str, int] = {}
    for u in units:
        for ts in u.line_terms:
            for t in ts:
                df[t] = df.get(t, 0) + 1
    # Criterion-level IDF: terms shared by many criteria do not tell them apart.
    cterm_lists = [terms(c.text) for c in criteria]
    nc = len(criteria) or 1
    cdf: Dict[str, int] = {}
    for ts in cterm_lists:
        for t in ts:
            cdf[t] = cdf.get(t, 0) + 1

    def idf(t: str) -> float:
        line_w = math.log((n + 1) / (df.get(t, 0) + 1)) + 1.0
        crit_w = math.log((nc + 1) / (cdf.get(t, 0) + 1)) + 1.0
        return line_w * crit_w

    results = [Mapping(c, ts, literals(c.text), words=term_words(c.text))
               for c, ts in zip(criteria, cterm_lists)]
    for u in units:
        found: List[Tuple[Mapping, Evidence]] = []
        for m in results:
            ev = _score(m, u, min_terms, idf)
            if ev is not None:
                found.append((m, ev))
        if not found:
            continue
        # A unit counts only for the criteria it fits best (explicit tags always count).
        top = max(ev.score for _, ev in found)
        for m, ev in found:
            if ev.via == "tag" or ev.score >= share * top:
                (m.tests if u.is_test else m.code).append(ev)
    for m in results:
        m.code = _rank(m.code, max_evidence)
        m.tests = _rank(m.tests, max_evidence)
    return results


def _score(m: Mapping, u: _Unit, min_terms: int, idf) -> Optional[Evidence]:
    cterms = m.terms
    name = _match(cterms, u.name_terms) if cterms else []
    body = [t for t in _match(cterms, u.body_terms) if t not in name] if cterms else []
    # The file path ("README", "settings") helps, but only next to a real match.
    path = ([t for t in _match(cterms, u.path_terms) if t not in name and t not in body]
            if (name or body) else [])
    matched = name + body + path
    # In a test function the name says what is tested; the body only half counts.
    score = (sum(idf(t) for t in name)
             + (0.5 if u.name_terms else 1.0) * sum(idf(t) for t in body)
             + 0.5 * sum(idf(t) for t in path))
    if all(ln.kind == "removed" for ln in u.lines):
        score *= 0.7  # usually the old version of a changed line
    via = None
    if m.criterion.id in u.tags:
        via, score = "tag", score + 100.0
    hits = [lit for lit in m.literals if lit.lower() in u.text]
    if hits:
        via = via or "literal"
        score += 10.0 * len(hits)
    if via is None and cterms and len(matched) >= min(min_terms, len(cterms)):
        via = "terms"
    if via is None:
        return None
    # Point at the line that shows the most (the test's def line on ties).
    best_i, best_k = 0, -1
    for i, (ln, ts) in enumerate(zip(u.lines, u.line_terms)):
        k = len(_match(cterms, ts)) + (5 if any(l.lower() in ln.text.lower() for l in hits) else 0)
        k += 50 if _tag_allowed(u, ln) and m.criterion.id in _tags(ln.text) else 0
        if k > best_k:
            best_i, best_k = i, k
    ln = u.lines[best_i]
    return Evidence(ln.path, ln.line, ln.text, ln.kind, ln.symbol,
                    matched, via, score)


def _rank(evs: List[Evidence], limit: int) -> List[Evidence]:
    """Best first, but the best location of each file before second picks from any file."""
    evs = sorted(evs, key=lambda e: (-e.score, e.path, e.line))
    seen: Set[str] = set()
    first, rest = [], []
    for e in evs:
        (rest if e.path in seen else first).append(e)
        seen.add(e.path)
    ordered = first + rest
    return ordered[:limit] if limit > 0 else ordered
