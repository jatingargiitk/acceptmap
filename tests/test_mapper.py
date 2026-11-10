import os
import textwrap
import unittest

from acceptmap.criteria import parse_criteria
from acceptmap.diff import parse_diff
from acceptmap.mapper import CODE_ONLY, MAPPED, TEST_ONLY, UNMAPPED, map_criteria

HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(HERE, "..", "examples")


def run(spec, diff, **kw):
    return map_criteria(parse_criteria(textwrap.dedent(spec)), parse_diff(textwrap.dedent(diff)), **kw)


def by_id(mappings):
    return {m.criterion.id: m for m in mappings}


TS_DIFF = """\
diff --git a/src/export.ts b/src/export.ts
--- a/src/export.ts
+++ b/src/export.ts
@@ -1,3 +1,9 @@
 import { db } from "./db";
+
+export function exportCsv(rows: Row[]): string {
+  const header = Object.keys(rows[0] ?? {}).join(",");
+  return [header, ...rows.map(toCsvLine)].join("\\n");
+}
+
+export const archivedRows = () => db.rows.filter((r) => r.archived);
diff --git a/src/export.test.ts b/src/export.test.ts
--- a/src/export.test.ts
+++ b/src/export.test.ts
@@ -1,2 +1,8 @@
 import { exportCsv } from "./export";
+
+it("csv export starts with a header row", () => {
+  expect(exportCsv([{ a: 1 }]).split("\\n")[0]).toBe("a");
+});
+
+test("AC-3 keeps unicode intact", () => {});
"""


class MapperTest(unittest.TestCase):
    def test_example_statuses(self):
        with open(os.path.join(EX, "issue-118.md")) as fh:
            criteria = parse_criteria(fh.read())
        with open(os.path.join(EX, "pr-118.diff")) as fh:
            files = parse_diff(fh.read())
        ms = by_id(map_criteria(criteria, files))
        self.assertEqual({k: m.status for k, m in ms.items()}, {
            "AC-1": MAPPED, "AC-2": MAPPED, "AC-3": MAPPED, "AC-4": CODE_ONLY, "AC-5": UNMAPPED,
        })
        # Each test function lands on the criterion it is about.
        self.assertEqual(ms["AC-2"].tests[0].symbol, "test_429_response_has_retry_after_header")
        self.assertEqual(ms["AC-3"].tests[0].symbol, "test_successful_login_resets_failed_attempts")
        # Literal `LOGIN_MAX_ATTEMPTS` points at the settings line.
        locs = {(e.path, e.line) for e in ms["AC-4"].code}
        self.assertIn(("app/settings.py", 5), locs)
        self.assertEqual(ms["AC-2"].code[0].via, "literal")

    def test_typescript_tests_tags_and_statuses(self):
        ms = by_id(run("""
            ## Acceptance criteria
            - [ ] Users can export rows as CSV with a header row
            - [ ] Archived rows are included in the export
            - [ ] Non-ASCII characters survive the round trip
            - [ ] A progress bar shows during long exports
        """, TS_DIFF))
        self.assertEqual(ms["AC-1"].status, MAPPED)
        self.assertEqual(ms["AC-1"].tests[0].symbol, "csv export starts with a header row")
        self.assertEqual(ms["AC-2"].status, CODE_ONLY)
        self.assertEqual(ms["AC-3"].status, TEST_ONLY)
        self.assertEqual(ms["AC-3"].tests[0].via, "tag")
        self.assertEqual(ms["AC-4"].status, UNMAPPED)

    def test_import_lines_are_not_evidence(self):
        ms = run("""
            ## Acceptance criteria
            - db export works
        """, TS_DIFF)
        self.assertNotIn(1, [e.line for e in ms[0].code])

    def test_min_terms(self):
        spec = """
            ## Acceptance criteria
            - Archived rows are hidden
        """
        diff = """\
            --- a/x.py
            +++ b/x.py
            @@ -0,0 +1 @@
            +rows = load()
        """
        self.assertEqual(run(spec, diff)[0].status, UNMAPPED)
        self.assertEqual(run(spec, diff, min_terms=1)[0].status, CODE_ONLY)

    def test_single_term_criterion_needs_one_match(self):
        ms = run("""
            ## Acceptance criteria
            - Pagination
        """, """\
            --- a/x.py
            +++ b/x.py
            @@ -0,0 +1 @@
            +def paginate(items): ...
        """)
        # "pagination" -> "pagin", a prefix of "paginat"; one term is enough here.
        self.assertEqual(ms[0].terms, ["pagin"])
        self.assertEqual(ms[0].status, CODE_ONLY)

    def test_removed_lines_count_as_code_evidence(self):
        ms = run("""
            ## Acceptance criteria
            - Remove the legacy XML export endpoint
        """, """\
            --- a/api.py
            +++ b/api.py
            @@ -5,2 +5,0 @@
            -@route("/export.xml")
            -def legacy_xml_export(): ...
        """)
        self.assertEqual(ms[0].status, CODE_ONLY)
        self.assertEqual(ms[0].code[0].kind, "removed")
        self.assertEqual(ms[0].code[0].line, 6)

    def test_max_evidence(self):
        diff = "--- a/x.py\n+++ b/x.py\n@@ -0,0 +1,5 @@\n" + "".join(
            "+csv_export_%d = 1\n" % i for i in range(5))
        spec = "## Acceptance criteria\n- csv export\n"
        self.assertEqual(len(run(spec, diff)[0].code), 3)
        self.assertEqual(len(run(spec, diff, max_evidence=0)[0].code), 5)

    def test_unit_goes_to_best_fitting_criterion(self):
        ms = run("""
            ## Acceptance criteria
            - Session tokens expire after one hour
            - Session cookie is marked secure
        """, """\
            --- a/s.py
            +++ b/s.py
            @@ -0,0 +1 @@
            +cookie = make_session_cookie(secure=True)
        """)
        self.assertEqual([m.status for m in ms], [UNMAPPED, CODE_ONLY])

    def test_criterion_without_terms(self):
        ms = run("## Acceptance criteria\n- It works\n", "--- a/x\n+++ b/x\n@@ -0,0 +1 @@\n+works = 1\n")
        self.assertEqual(ms[0].terms, [])
        self.assertEqual(ms[0].status, UNMAPPED)


if __name__ == "__main__":
    unittest.main()
