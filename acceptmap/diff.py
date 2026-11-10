"""Parse a unified diff (``git diff`` output or a .diff/.patch file).

Every added and removed line is kept with its file, line number (new-side for
added lines, old-side for removed lines) and the enclosing function or test
name, worked out from the hunk header and definitions seen in the hunk.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@ ?(.*)$")

# (regex, group holding the name). Matched against the stripped line.
_DEF_PATTERNS: Sequence[Tuple[re.Pattern, int]] = [
    (re.compile(r"^(?:async\s+)?def\s+([A-Za-z_]\w*)"), 1),                       # Python
    (re.compile(r"^class\s+([A-Za-z_]\w*)"), 1),                                   # Python / JS / Java
    (re.compile(r"^(?:it|test|describe|context)(?:\.\w+)*\(\s*(['\"`])(.+?)\1"), 2),  # JS/TS test blocks
    (re.compile(r"^(?:it|describe|context|test)\s+(['\"])(.+?)\1"), 2),         # RSpec
    (re.compile(r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)"), 1),
    (re.compile(r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>"), 1),
    (re.compile(r"^func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)"), 1),                   # Go
    (re.compile(r"^(?:pub(?:\([\w:]+\))?\s+)?(?:async\s+)?fn\s+([A-Za-z_]\w*)"), 1),  # Rust
    (re.compile(r"^(?:(?:public|private|protected|internal|static|final|override|suspend|open)\s+)*fun\s+([A-Za-z_]\w*)"), 1),  # Kotlin
    (re.compile(r"^(?:(?:public|private|protected|internal|static|final|async|virtual|override|synchronized)\s+)+[\w<>\[\],.?]+\s+([A-Za-z_]\w*)\s*\("), 1),  # Java / C#
    (re.compile(r"^def\s+(?:self\.)?([A-Za-z_]\w*[?!]?)"), 1),                    # Ruby
]

DEFAULT_TEST_GLOBS: Sequence[str] = (
    "test/*", "tests/*", "*/test/*", "*/tests/*", "__tests__/*", "*/__tests__/*",
    "spec/*", "*/spec/*", "test_*.py", "*/test_*.py", "*_test.py", "*_test.go",
    "*.test.*", "*.spec.*", "*Test.java", "*Tests.java", "*Test.kt", "*Tests.cs",
    "*Test.cs", "*_spec.rb", "*_test.rb", "conftest.py", "*/conftest.py",
)


@dataclass
class Line:
    path: str
    line: int
    text: str
    kind: str  # "added" | "removed"
    symbol: Optional[str] = None


@dataclass
class FileDiff:
    path: str
    old_path: Optional[str] = None
    status: str = "modified"  # added | deleted | modified | renamed
    binary: bool = False
    lines: List[Line] = field(default_factory=list)
    is_test: bool = False


def definition_name(text: str) -> Optional[str]:
    s = text.strip()
    for rx, grp in _DEF_PATTERNS:
        m = rx.match(s)
        if m:
            return m.group(grp)
    return None


def is_test_path(path: str, extra_globs: Sequence[str] = ()) -> bool:
    p = path.replace("\\", "/")
    name = p.rsplit("/", 1)[-1]
    for g in tuple(DEFAULT_TEST_GLOBS) + tuple(extra_globs):
        if fnmatch.fnmatchcase(p, g) or ("/" not in g and fnmatch.fnmatchcase(name, g)):
            return True
    return False


def _strip_prefix(p: str) -> str:
    p = p.strip()
    if "\t" in p:
        p = p.split("\t", 1)[0]
    if p.startswith('"') and p.endswith('"'):
        p = p[1:-1]
    if p.startswith(("a/", "b/")):
        p = p[2:]
    return p


def _indent(text: str) -> int:
    return len(text) - len(text.lstrip(" \t").expandtabs(4)) if text.strip() else 10**6


def parse_diff(text: str, test_globs: Sequence[str] = ()) -> List[FileDiff]:
    files: List[FileDiff] = []
    cur: Optional[FileDiff] = None
    old_no = new_no = 0
    old_left = new_left = 0
    symbol: Optional[Tuple[str, int]] = None
    seen_plus = False  # current file already had its "+++" header

    def track(content: str) -> Optional[str]:
        """Update the enclosing-definition tracker with one line of new-side content."""
        nonlocal symbol
        name = definition_name(content)
        ind = len(content.expandtabs(4)) - len(content.expandtabs(4).lstrip())
        if name:
            symbol = (name, ind)
        elif symbol is not None and content.strip():
            first = content.strip()[:1]
            if ind <= symbol[1] and first not in "})]@#/*":
                symbol = None
        return symbol[0] if symbol else None

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        if raw.startswith("diff --git "):
            parts = raw[len("diff --git "):]
            m = re.match(r'"?a/(.+?)"? "?b/(.+?)"?$', parts)
            cur = FileDiff(path=m.group(2) if m else parts)
            files.append(cur)
            old_left = new_left = 0
            seen_plus = False
            continue
        if old_left > 0 or new_left > 0:
            if cur is None:
                continue
            if raw.startswith("+"):
                content = raw[1:]
                cur.lines.append(Line(cur.path, new_no, content, "added", track(content)))
                new_no += 1
                new_left -= 1
            elif raw.startswith("-"):
                content = raw[1:]
                cur.lines.append(Line(cur.path, old_no, content, "removed",
                                      symbol[0] if symbol else definition_name(content)))
                old_no += 1
                old_left -= 1
            elif raw.startswith("\\"):
                pass  # "\ No newline at end of file"
            else:
                content = raw[1:] if raw.startswith(" ") else raw
                track(content)
                old_no += 1
                new_no += 1
                old_left -= 1
                new_left -= 1
            continue
        if raw.startswith("--- "):
            p = raw[4:]
            if cur is None or seen_plus:
                # Plain "diff -u" output, or a second file without a "diff --git" line.
                cur = FileDiff(path=_strip_prefix(p))
                files.append(cur)
                seen_plus = False
            if p.strip().startswith("/dev/null"):
                cur.status = "added"
            else:
                cur.old_path = _strip_prefix(p)
            continue
        if raw.startswith("+++ ") and cur is not None:
            p = raw[4:]
            seen_plus = True
            if p.strip().startswith("/dev/null"):
                cur.status = "deleted"
                cur.path = cur.old_path or cur.path
            else:
                cur.path = _strip_prefix(p)
            continue
        if cur is None:
            continue
        if raw.startswith("new file mode"):
            cur.status = "added"
        elif raw.startswith("deleted file mode"):
            cur.status = "deleted"
        elif raw.startswith("rename from "):
            cur.status = "renamed"
            cur.old_path = raw[len("rename from "):]
        elif raw.startswith("rename to "):
            cur.path = raw[len("rename to "):]
        elif raw.startswith("Binary files ") or raw.startswith("GIT binary patch"):
            cur.binary = True
        else:
            h = HUNK_RE.match(raw)
            if h:
                old_no = int(h.group(1))
                old_left = int(h.group(2)) if h.group(2) is not None else 1
                new_no = int(h.group(3))
                new_left = int(h.group(4)) if h.group(4) is not None else 1
                header = h.group(5)
                name = definition_name(header) if header else None
                symbol = (name, len(header) - len(header.lstrip())) if name else None

    for f in files:
        f.is_test = is_test_path(f.path, test_globs)
        for ln in f.lines:
            ln.path = f.path
    return files
