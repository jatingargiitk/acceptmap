import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from acceptmap.cli import main

HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(HERE, "..", "examples")
ISSUE = os.path.join(EX, "issue-118.md")
DIFF = os.path.join(EX, "pr-118.diff")


def cli(*argv, stdin=None):
    out, err = io.StringIO(), io.StringIO()
    old = sys.stdin
    if stdin is not None:
        sys.stdin = io.StringIO(stdin)
    try:
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = main(list(argv))
            except SystemExit as e:  # argparse errors
                code = e.code
    finally:
        sys.stdin = old
    return code, out.getvalue(), err.getvalue()


class CliTest(unittest.TestCase):
    def test_markdown_report(self):
        code, out, _ = cli(ISSUE, "--diff", DIFF)
        self.assertEqual(code, 0)
        self.assertIn("**3/5 mapped to code and tests** · 1 code only · 0 tests only · 1 unmapped", out)
        self.assertIn("| AC-5 | ❌ UNMAPPED |", out)
        self.assertIn("### Unmapped criteria", out)
        self.assertIn("<details><summary>Evidence</summary>", out)

    def test_committed_example_reports_are_current(self):
        cwd = os.getcwd()
        os.chdir(os.path.join(HERE, ".."))
        self.addCleanup(os.chdir, cwd)
        args = ("examples/issue-118.md", "--diff", "examples/pr-118.diff")
        _, out, _ = cli(*args)
        with open("examples/report.md", encoding="utf-8") as fh:
            self.assertEqual(out, fh.read())
        _, out, _ = cli(*args, "--format", "json")
        with open("examples/report.json", encoding="utf-8") as fh:
            self.assertEqual(out, fh.read())

    def test_no_details_and_title(self):
        _, out, _ = cli(ISSUE, "--diff", DIFF, "--no-details", "--title", "PR #118")
        self.assertTrue(out.startswith("## PR #118\n"))
        self.assertNotIn("<details>", out)

    def test_json(self):
        code, out, _ = cli(ISSUE, "--diff", DIFF, "--format", "json")
        doc = json.loads(out)
        self.assertEqual(doc["summary"], {"MAPPED": 3, "CODE-ONLY": 1, "TEST-ONLY": 0,
                                          "UNMAPPED": 1, "total": 5})
        self.assertEqual(doc["criteria"][4]["status"], "UNMAPPED")
        self.assertEqual(doc["criteria"][4]["code"], [])

    def test_output_and_json_files(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        md, js = os.path.join(d, "r.md"), os.path.join(d, "r.json")
        code, out, _ = cli(ISSUE, "--diff", DIFF, "-o", md, "--json", js)
        self.assertEqual((code, out), (0, ""))
        with open(md, encoding="utf-8") as fh:
            self.assertIn("AC-1", fh.read())
        with open(js, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["summary"]["total"], 5)

    def test_fail_on(self):
        self.assertEqual(cli(ISSUE, "--diff", DIFF, "--fail-on-unmapped")[0], 1)
        self.assertEqual(cli(ISSUE, "--diff", DIFF, "--fail-on", "unmapped")[0], 1)
        code, _, err = cli(ISSUE, "--diff", DIFF, "--fail-on", "untested")
        self.assertEqual(code, 1)
        self.assertIn("2 criteria without test evidence", err)

    def test_fail_on_passes_when_all_mapped(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        spec = os.path.join(d, "s.md")
        with open(spec, "w") as fh:
            fh.write("## Acceptance criteria\n- [ ] Successful login resets failed attempts\n")
        self.assertEqual(cli(spec, "--diff", DIFF, "--fail-on", "untested")[0], 0)

    def test_list(self):
        code, out, _ = cli(ISSUE, "--list")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines()[0],
                         "AC-1 [ ] (line 7, checkbox) After 5 failed login attempts from the same IP "
                         "within 15 minutes, `POST /login` returns HTTP 429")

    def test_spec_from_stdin(self):
        code, out, _ = cli("-", "--diff", DIFF, "--no-details",
                           stdin="Done when:\n- Retry-After header is set\n")
        self.assertEqual(code, 0)
        self.assertIn("| AC-1 | ✅ MAPPED |", out)

    def test_errors(self):
        self.assertEqual(cli(ISSUE)[0], 2)
        self.assertEqual(cli("/nonexistent.md", "--diff", DIFF)[0], 2)
        self.assertEqual(cli(ISSUE, "--diff", "/nonexistent.diff")[0], 2)
        self.assertEqual(cli("-", "--diff", "-")[0], 2)
        self.assertEqual(cli(ISSUE, "--diff", DIFF, "--git", "a...b")[0], 2)

    def test_no_criteria(self):
        code, out, _ = cli(DIFF, "--diff", DIFF)
        self.assertEqual(code, 0)
        self.assertIn("No acceptance criteria found", out)


@unittest.skipUnless(shutil.which("git"), "git not installed")
class GitRangeTest(unittest.TestCase):
    def test_git_range(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)

        def git(*a):
            subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=d,
                           check=True, capture_output=True)

        git("init", "-q", "-b", "main")
        with open(os.path.join(d, "app.py"), "w") as fh:
            fh.write("x = 1\n")
        git("add", ".")
        git("commit", "-qm", "init")
        git("checkout", "-qb", "feature")
        os.makedirs(os.path.join(d, "tests"))
        with open(os.path.join(d, "app.py"), "a") as fh:
            fh.write("def export_csv(rows):\n    return ','.join(rows)\n")
        with open(os.path.join(d, "tests", "test_app.py"), "w") as fh:
            fh.write("def test_export_csv_joins_rows():\n    pass\n")
        git("add", ".")
        git("commit", "-qm", "feature")
        spec = os.path.join(d, "issue.md")
        with open(spec, "w") as fh:
            fh.write("## Acceptance criteria\n- [ ] Export rows as CSV\n- [ ] Email the export\n")
        cwd = os.getcwd()
        os.chdir(d)
        try:
            code, out, _ = cli(spec, "--git", "main...feature", "--format", "json")
            bad = cli(spec, "--git", "nope...feature")
        finally:
            os.chdir(cwd)
        self.assertEqual(code, 0)
        doc = json.loads(out)
        self.assertEqual([c["status"] for c in doc["criteria"]], ["MAPPED", "UNMAPPED"])
        self.assertEqual(doc["criteria"][0]["code"][0]["path"], "app.py")
        self.assertEqual(doc["criteria"][0]["code"][0]["line"], 2)
        self.assertEqual(bad[0], 2)
        self.assertIn("git diff failed", bad[2])


if __name__ == "__main__":
    unittest.main()
