import os
import unittest

from acceptmap.diff import definition_name, is_test_path, parse_diff

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLE = os.path.join(HERE, "..", "examples", "pr-118.diff")

GIT_DIFF = """\
diff --git a/src/a.py b/src/a.py
index 1111111..2222222 100644
--- a/src/a.py
+++ b/src/a.py
@@ -1,4 +1,5 @@ class A:
     def foo(self):
         x = 1
+        y = 3
         return x
-    # old comment
+
diff --git a/gone.txt b/gone.txt
deleted file mode 100644
index 3333333..0000000
--- a/gone.txt
+++ /dev/null
@@ -1 +0,0 @@
-old line
diff --git a/img.png b/img.png
new file mode 100644
index 0000000..4444444
Binary files /dev/null and b/img.png differ
diff --git a/old_name.py b/new_name.py
similarity index 90%
rename from old_name.py
rename to new_name.py
index 5555555..6666666 100644
--- a/old_name.py
+++ b/new_name.py
@@ -10,2 +10,3 @@ def keep():
     a = 1
+    b = 2
\\ No newline at end of file
"""

PLAIN_DIFF = """\
--- pkg/x.go\t2026-11-10 10:00:00
+++ pkg/x.go\t2026-11-10 10:05:00
@@ -3,0 +4,3 @@
+func Parse(s string) error {
+\treturn nil
+}
--- pkg/x_test.go
+++ pkg/x_test.go
@@ -1 +1,2 @@
 package pkg
+func TestParse(t *testing.T) {}
"""


class DiffTest(unittest.TestCase):
    def test_git_diff_files_and_statuses(self):
        files = parse_diff(GIT_DIFF)
        self.assertEqual([(f.path, f.status) for f in files], [
            ("src/a.py", "modified"), ("gone.txt", "deleted"),
            ("img.png", "added"), ("new_name.py", "renamed"),
        ])
        self.assertTrue(files[2].binary)
        self.assertEqual(files[3].old_path, "old_name.py")

    def test_line_numbers_and_kinds(self):
        a = parse_diff(GIT_DIFF)[0]
        self.assertEqual([(l.kind, l.line, l.text.strip()) for l in a.lines], [
            ("added", 3, "y = 3"), ("removed", 4, "# old comment"), ("added", 5, ""),
        ])
        gone = parse_diff(GIT_DIFF)[1]
        self.assertEqual([(l.kind, l.line, l.text) for l in gone.lines], [("removed", 1, "old line")])

    def test_enclosing_symbol_from_hunk_and_body(self):
        a, _, _, renamed = parse_diff(GIT_DIFF)
        self.assertEqual(a.lines[0].symbol, "foo")
        self.assertEqual(renamed.lines[0].symbol, "keep")
        self.assertEqual([l.line for l in renamed.lines], [11])

    def test_plain_unified_diff_with_two_files(self):
        files = parse_diff(PLAIN_DIFF)
        self.assertEqual([f.path for f in files], ["pkg/x.go", "pkg/x_test.go"])
        self.assertEqual([l.line for l in files[0].lines], [4, 5, 6])
        self.assertEqual(files[0].lines[1].symbol, "Parse")
        self.assertTrue(files[1].is_test)
        self.assertEqual(files[1].lines[0].symbol, "TestParse")

    def test_example_diff(self):
        with open(EXAMPLE) as fh:
            files = parse_diff(fh.read())
        self.assertEqual([(f.path, f.status, f.is_test) for f in files], [
            ("app/auth.py", "modified", False), ("app/ratelimit.py", "added", False),
            ("app/settings.py", "modified", False), ("tests/test_auth.py", "modified", True),
        ])
        tests = files[3]
        names = {l.symbol for l in tests.lines if l.kind == "added" and l.text.strip()}
        self.assertIn("test_successful_login_resets_failed_attempts", names)

    def test_comments_and_decorators_attach_to_next_definition(self):
        diff = (
            "--- a/tests/test_x.py\n+++ b/tests/test_x.py\n@@ -1,2 +1,8 @@\n"
            " def test_old():\n"
            "     pass\n"
            "+\n"
            "+# AC-4\n"
            "+@pytest.mark.slow\n"
            "+def test_new():\n"
            "+    pass\n"
            "+# trailing comment\n"
        )
        lines = parse_diff(diff)[0].lines
        self.assertEqual([(l.text, l.symbol) for l in lines[1:]], [
            ("# AC-4", "test_new"), ("@pytest.mark.slow", "test_new"),
            ("def test_new():", "test_new"), ("    pass", "test_new"),
            ("# trailing comment", "test_new"),
        ])

    def test_is_test_path(self):
        for p in ("tests/test_x.py", "pkg/sub/tests/helpers.py", "test_x.py", "a/b_test.go",
                  "src/x.test.ts", "web/__tests__/a.js", "spec/models/user_spec.rb",
                  "src/FooTest.java", "src/app.spec.tsx"):
            self.assertTrue(is_test_path(p), p)
        for p in ("src/testing_utils.py", "src/contest.py", "app/auth.py"):
            self.assertFalse(is_test_path(p), p)
        self.assertTrue(is_test_path("qa/login.py", ["qa/*"]))

    def test_definition_names(self):
        cases = {
            "def foo(x):": "foo",
            "    async def bar(self):": "bar",
            "class Limiter:": "Limiter",
            "export async function handleLogin(req) {": "handleLogin",
            "const retryAfter = (ip) => {": "retryAfter",
            "it('returns 429 after five failures', () => {": "returns 429 after five failures",
            'test("resets counter", async () => {': "resets counter",
            "func (s *Server) Login(w http.ResponseWriter) {": "Login",
            "pub fn retry_after(&self) -> u64 {": "retry_after",
            "public void testLockout() {": "testLockout",
            "suspend fun refreshToken() {": "refreshToken",
            "x = 1": None,
        }
        for line, name in cases.items():
            self.assertEqual(definition_name(line), name, line)


if __name__ == "__main__":
    unittest.main()
