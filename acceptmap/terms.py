"""Term extraction shared by criteria and diff lines.

Both sides go through the same pipeline so that ``LOGIN_MAX_ATTEMPTS``,
``loginMaxAttempts`` and "max login attempts" all reduce to the same terms.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Set

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_CAMEL_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
_BACKTICK_RE = re.compile(r"`([^`]+)`")

# English filler, spec boilerplate ("should", "given", "user story") and
# keywords that show up on almost every line of code or tests.
STOPWORDS: Set[str] = set(
    """
    a about above after again against all also am an and any are as at be because been
    before being below between both but by can cannot could did do does doing done down
    during each either else ever every few for from further had has have having he her here
    hers him his how however i if in into is it its itself just least less let like make
    makes may me might more most much must my need needs neither no nor not now of off on
    once one only or other our ours out over own per same shall she should since so some
    such than that the their them then there these they this those though through thus to
    too under until up upon us use used uses using very via was we were what whatever when
    where whether which while who whom whose why will with within without would yet you
    your yours
    given then when and but scenario feature story criteria criterion acceptance able
    ensure ensures correctly correct properly proper expected expect expects behavior
    behaviour case cases work works working new existing etc eg ie e g
    def class return returns returned self cls this none null nil true false const var
    function func fn import from export async await assert assertequal asserttrue
    assertfalse equal equals tobe toequal test tests testing spec it describe pass
    """.split()
)

_SUFFIXES = (
    "ations", "ation", "ables", "able", "ibles", "ible", "ings", "ing",
    "ers", "er", "ed", "es", "s", "ly", "ment",
)

# Two-letter words that carry meaning in specs and code.
SHORT_WORDS: Set[str] = {"ip", "id", "ui", "db", "io", "os", "ci", "ux"}


def stem(word: str) -> str:
    """Very light suffix stripping: limits/limited/limiting/limiter -> limit."""
    if word.isdigit():
        return word
    for suf in _SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            if suf == "s" and word.endswith(("ss", "us", "is")):
                continue
            if suf == "es" and not word.endswith(("sses", "xes", "ches", "shes", "zes")):
                # "expires" -> "expire" is handled by the "s" rule below.
                continue
            word = word[: -len(suf)]
            break
    if word.endswith("ie") and len(word) >= 4:
        word = word[:-2] + "y"
    if word.endswith("e") and len(word) > 3:
        word = word[:-1]
    return word


def split_words(text: str) -> List[str]:
    """Split text and identifiers (snake_case, camelCase, kebab-case) into lowercase words."""
    out: List[str] = []
    for tok in _TOKEN_RE.findall(text):
        for part in _CAMEL_RE.findall(tok):
            out.append(part.lower())
    return out


def terms(text: str) -> List[str]:
    """Ordered, de-duplicated, stemmed, stopword-free terms of ``text``."""
    seen: Set[str] = set()
    out: List[str] = []
    for w in split_words(text):
        if w in STOPWORDS:
            continue
        if w.isdigit():
            if len(w) < 2:
                continue
        elif len(w) < 3 and w not in SHORT_WORDS:
            continue
        s = stem(w) if len(w) > 2 else w
        if s in STOPWORDS or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def term_set(text: str) -> Set[str]:
    return set(terms(text))


def literals(text: str) -> List[str]:
    """Backticked literals in a criterion, e.g. `Retry-After` or `LOGIN_MAX_ATTEMPTS`.

    Only literals that look like identifiers, headers, paths or flags (at least
    four characters, no spaces) are kept; they count as evidence on their own
    when they appear verbatim in a changed line.
    """
    out = []
    for lit in _BACKTICK_RE.findall(text):
        lit = lit.strip()
        if len(lit) >= 4 and " " not in lit and lit not in out:
            out.append(lit)
    return out


def join(items: Iterable[str]) -> str:
    return ", ".join(items)


def same_term(a: str, b: str) -> bool:
    """Exact match, or one term is a prefix of the other and the shorter has 5+ chars.

    Lets ``config`` meet ``configur`` (configurable) and ``token`` meet ``tokeniz``.
    """
    if a == b:
        return True
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= 5 and long_.startswith(short)
