# acceptmap

Take the acceptance criteria from an issue, PR description or spec, and map each one to the exact changed lines of code and tests in a pull request. Criteria that nothing in the diff supports stay visibly **UNMAPPED**, so "done" is easy to check in review.

- Reads criteria from Markdown: checkbox items, bulleted or numbered lists under an "Acceptance criteria" / "Definition of done" / "Requirements" / "Done when" heading, `AC-3:` tagged lines, and Given/When/Then scenarios.
- Reads a unified diff: a `.diff`/`.patch` file, stdin, or `git diff BASE...HEAD`.
- Writes a Markdown report (for a PR comment or the job summary) and JSON, with a status per criterion and `file:line` evidence.
- Deterministic and offline. Python 3.9+, standard library only, no LLM, no API keys.

**Matching is heuristic.** It is term matching, not understanding. It can point at a line that shares words with a criterion without implementing it, and it can miss code that implements a criterion in different words. Use the report as a review aid that shows where to look and which criteria have no evidence, not as proof that a criterion is met.

## Install

```bash
pip install git+https://github.com/jatingargiitk/acceptmap
```

Or run from a checkout without installing: `python3 -m acceptmap ...`.

## Example

[`examples/issue-118.md`](examples/issue-118.md) asks for rate-limited logins with five criteria. [`examples/pr-118.diff`](examples/pr-118.diff) is the `git diff main...rate-limit-login` of a PR that implements four of them, tests three, and forgets the audit log.

```text
$ acceptmap examples/issue-118.md --diff examples/pr-118.diff --no-details
## Acceptance criteria coverage

**3/5 mapped to code and tests** · 1 code only · 0 tests only · 1 unmapped

| ID | Status | Criterion | Code | Tests |
|----|--------|-----------|------|-------|
| AC-1 | ✅ MAPPED | After 5 failed login attempts from the same IP within 15 minutes, `POST /login` returns H… | `app/auth.py:14` `login`<br>`app/ratelimit.py:1`<br>`app/ratelimit.py:6` `FailedLoginLimiter` | `tests/test_auth.py:10` `test_login_returns_429_after_five_failed_attempts` |
| AC-2 | ✅ MAPPED | The 429 response includes a `Retry-After` header with the seconds until the window resets | `app/auth.py:15` `login`<br>`app/ratelimit.py:9` `__init__`<br>`app/auth.py:14` `login` | `tests/test_auth.py:21` `test_429_response_has_retry_after_header` |
| AC-3 | ✅ MAPPED | A successful login resets the failed-attempt counter for that IP | `app/ratelimit.py:1`<br>`app/auth.py:14` `login`<br>`app/auth.py:20` `login` | `tests/test_auth.py:24` `test_successful_login_resets_failed_attempts`<br>`tests/test_auth.py:10` `test_login_returns_429_after_five_failed_attempts` |
| AC-4 | 🟡 CODE-ONLY | The limit and window are configurable via `LOGIN_MAX_ATTEMPTS` and `LOGIN_WINDOW_SECONDS` | `app/auth.py:8`<br>`app/settings.py:5`<br>`app/ratelimit.py:7` `__init__` | — |
| AC-5 | ❌ UNMAPPED | Every lockout is written to the audit log with the IP and a timestamp | — | — |

### Unmapped criteria

- **AC-5** Every lockout is written to the audit log with the IP and a timestamp — no changed line matched (terms: lockout, written, audit, log, ip, timestamp)

<sub>acceptmap 0.1.0 · heuristic term matching; review before relying on it.</sub>
```

Each location is `file:line`, with the enclosing function or test name when there is one. Without `--no-details` the report adds a collapsed **Evidence** section with each matched line and the words it shared with the criterion; the full output is [`examples/report.md`](examples/report.md), and `--format json` gives [`examples/report.json`](examples/report.json).

| Status | Meaning |
|--------|---------|
| `MAPPED` | changed code and changed tests both match the criterion |
| `CODE-ONLY` | changed code matches, no changed test does |
| `TEST-ONLY` | a changed test matches, no changed code does |
| `UNMAPPED` | nothing in the diff matches |

Check what was extracted before mapping:

```text
$ acceptmap examples/issue-118.md --list
AC-1 [ ] (line 7, checkbox) After 5 failed login attempts from the same IP within 15 minutes, `POST /login` returns HTTP 429
AC-2 [ ] (line 8, checkbox) The 429 response includes a `Retry-After` header with the seconds until the window resets
AC-3 [ ] (line 9, checkbox) A successful login resets the failed-attempt counter for that IP
AC-4 [ ] (line 10, checkbox) The limit and window are configurable via `LOGIN_MAX_ATTEMPTS` and `LOGIN_WINDOW_SECONDS`
AC-5 [ ] (line 11, checkbox) Every lockout is written to the audit log with the IP and a timestamp
```

Fail a CI step when a criterion has no test evidence (`--fail-on untested`: UNMAPPED or CODE-ONLY) or no evidence at all (`--fail-on unmapped`, or `--fail-on-unmapped`):

```text
$ acceptmap examples/issue-118.md --diff examples/pr-118.diff --fail-on untested > /dev/null; echo "exit $?"
acceptmap: 2 criteria without test evidence
exit 1
```

### Explicit tags and scenarios

When wording alone is not enough, tag a test or a line with the criterion id: `AC-2` in a test name (`test_ac2_...`, `it("AC-2 ...")`) or in an added comment (`// AC-2` above a test, `# AC-2` next to code) always counts for AC-2. Ids that appear in strings, docs or removed lines are ignored. Criteria without an explicit `AC-n:` prefix are numbered in order of appearance, so prefer explicit ids if you tag.

[`examples/csv-export.md`](examples/csv-export.md) uses `AC-1:`/`AC-2:` lines and a Given/When/Then scenario; [`examples/csv-export.diff`](examples/csv-export.diff) is the real diff of a TypeScript change:

```text
$ acceptmap examples/csv-export.md --diff examples/csv-export.diff --no-details
## Acceptance criteria coverage

**2/3 mapped to code and tests** · 1 code only · 0 tests only · 0 unmapped

| ID | Status | Criterion | Code | Tests |
|----|--------|-----------|------|-------|
| AC-1 | ✅ MAPPED | The export starts with a header row of column names | `src/export.ts:15` `exportCsv`<br>`src/export.ts:16` `exportCsv`<br>`src/export.ts:13` `exportCsv` | `src/export.test.ts:12` `first line is the header row` |
| AC-2 | ✅ MAPPED | Values containing commas, quotes or newlines are escaped | `src/export.ts:7` `quoteCsvField`<br>`src/export.ts:4` `toCsvLine`<br>`src/export.ts:8` `quoteCsvField` | `src/export.test.ts:7` `wraps awkward fields in quotes` |
| AC-3 | 🟡 CODE-ONLY | Given a table with no rows When the user exports it Then the download is an empty file | `src/export.ts:13` `exportCsv`<br>`src/export.ts:4` `toCsvLine`<br>`src/export.ts:14` `exportCsv` | — |

<sub>acceptmap 0.1.0 · heuristic term matching; review before relying on it.</sub>
```

AC-2's test is found through the `// AC-2` comment above it. AC-3 is CODE-ONLY: `exportCsv` handles the empty table (the `rows.length === 0` check at `src/export.ts:14`), but no changed test covers it.

## GitHub Action

The repo is also a composite action. It reads the criteria from the pull request description (or a `spec` file), diffs the PR against its base, and writes the report to the job summary. [`examples/acceptmap-workflow.yml`](examples/acceptmap-workflow.yml) is a ready-to-copy workflow:

```yaml
# Copy to .github/workflows/acceptmap.yml in your repo.
name: acceptance criteria
on: pull_request
jobs:
  acceptmap:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # needed for git diff BASE...HEAD
      - uses: jatingargiitk/acceptmap@main
        with:
          fail-on: untested  # optional: "unmapped" or "untested"
```

Inputs: `spec` (Markdown file; default: PR description), `diff` (diff file instead of running git), `base` (default: PR base SHA), `fail-on`, `args` (extra CLI flags). Outputs: `report` and `json`, the paths of the Markdown and JSON reports, e.g. for posting the Markdown as a PR comment in a later step. The action runs with the runner's `python3` and installs nothing.

This repo's own CI runs the action on the examples, on a git range, and on its pull request descriptions.

## Usage

```text
$ acceptmap --help
usage: acceptmap [-h] [--diff FILE | --git RANGE] [--format {md,json}]
                 [-o FILE] [--json FILE] [--title TITLE] [--min-terms N]
                 [--max-evidence N] [--test-glob GLOB] [--no-details] [--list]
                 [--fail-on {unmapped,untested}] [--fail-on-unmapped]
                 [--version]
                 spec

Map acceptance criteria in an issue or spec (Markdown) to the code and tests changed in a diff. Criteria nothing matched stay visibly UNMAPPED.

positional arguments:
  spec                  Markdown issue, PR description or spec ('-' for stdin)

options:
  -h, --help            show this help message and exit
  --diff FILE           unified diff / patch file ('-' for stdin)
  --git RANGE           run 'git diff RANGE' in the current repo, e.g.
                        main...HEAD
  --format {md,json}    stdout format (default md)
  -o, --output FILE     write the report here instead of stdout
  --json FILE           also write the JSON report to FILE
  --title TITLE         report heading (default 'Acceptance criteria
                        coverage')
  --min-terms N         distinct shared terms a line needs to count as
                        evidence (default 2)
  --max-evidence N      evidence entries kept per criterion for code and for
                        tests (default 3, 0 = all)
  --test-glob GLOB      extra glob for test files (repeatable), e.g. 'qa/*'
  --no-details          omit the evidence section in Markdown
  --list                only print the extracted criteria and exit
  --fail-on {unmapped,untested}
                        exit 1 if any criterion is UNMAPPED (unmapped) or
                        lacks test evidence (untested)
  --fail-on-unmapped    shorthand for --fail-on unmapped
  --version             show program's version number and exit

exit codes: 0 ok, 1 --fail-on condition met, 2 usage or input error

examples:
  acceptmap issue.md --diff pr.diff
  acceptmap issue.md --git origin/main...HEAD --json report.json
  gh pr view 42 --json body -q .body | acceptmap - --git main...HEAD --fail-on untested
```

## How matching works

1. **Criteria.** If the document has an acceptance-criteria section (a Markdown heading or a bold/colon line such as `**Acceptance criteria:**` or `Done when:`), every list item, checkbox and `AC-n:` line in it is a criterion; nested bullets and indented continuation lines join their parent. Given/When/Then/And/But runs form one criterion each, anywhere. Without such a section, checkbox items anywhere are used. Code fences are skipped.
2. **Diff.** Added lines (new-side line numbers) and removed lines (old-side line numbers) are kept with their enclosing function or test, taken from the hunk header and definitions in the hunk (Python, JS/TS incl. `it(...)`/`test(...)`, Go, Rust, Java/C#/Kotlin, Ruby). Test files are recognised by path (`tests/`, `test_*.py`, `*_test.go`, `*.test.ts`, `*.spec.*`, `*Test.java`, ...; add more with `--test-glob`). Import lines are ignored.
3. **Terms.** Text and identifiers are split (`LOGIN_MAX_ATTEMPTS`, `loginMaxAttempts` and "max login attempts" give the same terms), lowercased, lightly stemmed, and stripped of English and code stopwords. Terms of 5+ characters also match longer terms they prefix (`config` / `configurable`).
4. **Evidence.** A changed code line, or a changed test function (its name plus its changed lines), is evidence for a criterion when it shares at least `--min-terms` (default 2) terms with it, contains one of the criterion's backticked literals verbatim (`` `Retry-After` ``), or carries its `AC-n` tag in a test name or comment. Words from the file path (`README`, `settings`) count too, but only on a line that already matches something. Scores weight rare terms higher, both across changed lines and across criteria, and each line or test only counts for the criteria it fits best (at least half the top score), so one shared word like "login" does not tie everything to everything.
5. **Report.** Up to `--max-evidence` (default 3) code and test locations per criterion, best first, taking the best location of each file before a second one from any file. Removed lines are shown as `(removed)` and rank below added ones.

## Limitations

- Synonyms and paraphrases are not matched: "throttle" will not find "rate limit".
- Only changed lines count. A criterion already satisfied by existing code shows up as UNMAPPED.
- Generic criteria ("it should be fast") rarely have shared terms; they will show as UNMAPPED and need a human.
- Definition detection is regex-based, not a parser, so some functions (e.g. nested or unusual syntax) are not named.

## Development

```bash
python3 -m unittest discover -s tests -v
```

## License

MIT
