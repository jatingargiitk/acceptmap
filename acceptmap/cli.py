"""Command-line interface."""

from __future__ import annotations

import argparse
import subprocess
import sys
from typing import List, Optional

from . import __version__
from .criteria import parse_criteria
from .diff import parse_diff
from .mapper import CODE_ONLY, UNMAPPED, map_criteria
from .report import criteria_list, summary, to_json, to_markdown

EPILOG = """\
exit codes: 0 ok, 1 --fail-on condition met, 2 usage or input error

examples:
  acceptmap issue.md --diff pr.diff
  acceptmap issue.md --git origin/main...HEAD --json report.json
  gh pr view 42 --json body -q .body | acceptmap - --git main...HEAD --fail-on untested
"""


def _n(count: int) -> str:
    return "%d %s" % (count, "criterion" if count == 1 else "criteria")


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="acceptmap",
        description="Map acceptance criteria in an issue or spec (Markdown) to the code and "
                    "tests changed in a diff. Criteria nothing matched stay visibly UNMAPPED.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("spec", help="Markdown issue, PR description or spec ('-' for stdin)")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--diff", metavar="FILE", help="unified diff / patch file ('-' for stdin)")
    src.add_argument("--git", metavar="RANGE",
                     help="run 'git diff RANGE' in the current repo, e.g. main...HEAD")
    p.add_argument("--format", choices=("md", "json"), default="md", help="stdout format (default md)")
    p.add_argument("-o", "--output", metavar="FILE", help="write the report here instead of stdout")
    p.add_argument("--json", metavar="FILE", dest="json_out", help="also write the JSON report to FILE")
    p.add_argument("--title", help="report heading (default 'Acceptance criteria coverage')")
    p.add_argument("--min-terms", type=int, default=2, metavar="N",
                   help="distinct shared terms a line needs to count as evidence (default 2)")
    p.add_argument("--max-evidence", type=int, default=3, metavar="N",
                   help="evidence entries kept per criterion for code and for tests (default 3, 0 = all)")
    p.add_argument("--test-glob", action="append", default=[], metavar="GLOB",
                   help="extra glob for test files (repeatable), e.g. 'qa/*'")
    p.add_argument("--no-details", action="store_true", help="omit the evidence section in Markdown")
    p.add_argument("--list", action="store_true", help="only print the extracted criteria and exit")
    p.add_argument("--fail-on", choices=("unmapped", "untested"),
                   help="exit 1 if any criterion is UNMAPPED (unmapped) or lacks test evidence (untested)")
    p.add_argument("--fail-on-unmapped", action="store_true", help="shorthand for --fail-on unmapped")
    p.add_argument("--version", action="version", version="acceptmap " + __version__)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.diff == "-" and args.spec == "-":
        print("acceptmap: spec and diff cannot both come from stdin", file=sys.stderr)
        return 2
    try:
        spec_text = _read(args.spec)
    except OSError as e:
        print("acceptmap: cannot read spec: %s" % e, file=sys.stderr)
        return 2
    criteria = parse_criteria(spec_text)
    if args.list:
        sys.stdout.write(criteria_list(criteria))
        return 0

    if args.diff:
        try:
            diff_text = _read(args.diff)
        except OSError as e:
            print("acceptmap: cannot read diff: %s" % e, file=sys.stderr)
            return 2
    elif args.git:
        try:
            proc = subprocess.run(["git", "diff", "--no-color", "--no-ext-diff", args.git],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace")
        except OSError as e:
            print("acceptmap: cannot run git: %s" % e, file=sys.stderr)
            return 2
        if proc.returncode != 0:
            print("acceptmap: git diff failed: %s" % proc.stderr.strip(), file=sys.stderr)
            return 2
        diff_text = proc.stdout
    else:
        print("acceptmap: give --diff FILE or --git RANGE (or --list)", file=sys.stderr)
        return 2

    files = parse_diff(diff_text, args.test_glob)
    mappings = map_criteria(criteria, files, min_terms=max(1, args.min_terms),
                            max_evidence=args.max_evidence)
    spec_name = None if args.spec == "-" else args.spec
    if args.format == "json":
        out = to_json(mappings, spec_name)
    else:
        out = to_markdown(mappings, title=args.title, spec=spec_name, details=not args.no_details)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(out)
    else:
        sys.stdout.write(out)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            fh.write(to_json(mappings, spec_name))

    fail_on = "unmapped" if args.fail_on_unmapped and not args.fail_on else args.fail_on
    s = summary(mappings)
    if fail_on == "unmapped" and s[UNMAPPED]:
        print("acceptmap: %s unmapped" % _n(s[UNMAPPED]), file=sys.stderr)
        return 1
    if fail_on == "untested" and (s[UNMAPPED] + s[CODE_ONLY]):
        print("acceptmap: %s without test evidence" % _n(s[UNMAPPED] + s[CODE_ONLY]),
              file=sys.stderr)
        return 1
    return 0
