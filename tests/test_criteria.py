import textwrap
import unittest

from acceptmap.criteria import parse_criteria


def parse(md):
    return parse_criteria(textwrap.dedent(md))


class CriteriaTest(unittest.TestCase):
    def test_checkboxes_under_heading(self):
        cs = parse("""
            # Title
            ## Acceptance Criteria
            - [ ] first thing
            - [x] second thing
            ## Notes
            - [ ] not a criterion
        """)
        self.assertEqual([(c.id, c.text, c.checked) for c in cs],
                         [("AC-1", "first thing", False), ("AC-2", "second thing", True)])

    def test_plain_and_numbered_lists_only_inside_section(self):
        cs = parse("""
            Intro:
            - background bullet
            ### Definition of Done
            1. numbered one
            2) numbered two
            * starred
            ### Design
            - design bullet
        """)
        self.assertEqual([c.text for c in cs], ["numbered one", "numbered two", "starred"])

    def test_checkboxes_anywhere_when_no_section(self):
        cs = parse("""
            Please do this:
            - [ ] alpha
            - plain bullet is ignored
              - [ ] nested beta
        """)
        self.assertEqual([c.text for c in cs], ["alpha", "nested beta"])

    def test_section_present_drops_stray_checkboxes(self):
        cs = parse("""
            - [ ] I ran the tests
            ## Acceptance criteria
            - real criterion
        """)
        self.assertEqual([c.text for c in cs], ["real criterion"])

    def test_bold_pseudo_heading(self):
        cs = parse("""
            **Acceptance criteria:**
            - one
            - two

            **Notes**
            - not this
        """)
        self.assertEqual([c.text for c in cs], ["one", "two"])

    def test_colon_pseudo_heading(self):
        cs = parse("""
            Done when:
            - exported as CSV
        """)
        self.assertEqual([c.text for c in cs], ["exported as CSV"])

    def test_continuation_and_nested_bullets_join_parent(self):
        cs = parse("""
            ## Requirements
            - Users can export
              their data as CSV
              - including archived rows
            - Second
        """)
        self.assertEqual([c.text for c in cs],
                         ["Users can export their data as CSV including archived rows", "Second"])

    def test_given_when_then_scenarios(self):
        cs = parse("""
            ## Scenarios
            Given a signed-in user
            When they click export
            Then a CSV downloads
            And it has a header row

            **Given** an empty table
            **When** they click export
            **Then** an empty-state message shows
        """)
        self.assertEqual(len(cs), 2)
        self.assertEqual(cs[0].kind, "scenario")
        self.assertEqual(cs[0].text, "Given a signed-in user When they click export "
                                     "Then a CSV downloads And it has a header row")
        self.assertEqual(cs[1].text, "Given an empty table When they click export "
                                     "Then an empty-state message shows")

    def test_scenarios_kept_alongside_section(self):
        cs = parse("""
            Given a draft
            Then it autosaves
            ## Acceptance criteria
            - [ ] autosave every 10s
        """)
        self.assertEqual([c.kind for c in cs], ["scenario", "checkbox"])

    def test_explicit_ids_kept_and_auto_ids_skip_them(self):
        cs = parse("""
            ## Acceptance criteria
            - plain one
            - AC-2: tagged two
            - [AC-7] tagged seven
            - plain again
            - [ ] AC 3 - spaced tag
        """)
        self.assertEqual([(c.id, c.text, c.explicit_id) for c in cs], [
            ("AC-1", "plain one", False),
            ("AC-2", "tagged two", True),
            ("AC-7", "tagged seven", True),
            ("AC-4", "plain again", False),
            ("AC-3", "spaced tag", True),
        ])

    def test_unbulleted_tagged_lines_in_section(self):
        cs = parse("""
            ## Acceptance criteria
            AC-1: export works
            AC-2: import works
        """)
        self.assertEqual([c.id for c in cs], ["AC-1", "AC-2"])

    def test_code_fences_ignored(self):
        cs = parse("""
            ## Acceptance criteria
            ```
            - [ ] inside fence
            Given nothing
            ```
            - outside
        """)
        self.assertEqual([c.text for c in cs], ["outside"])

    def test_sub_heading_stays_in_section(self):
        cs = parse("""
            ## Acceptance criteria
            ### API
            - api thing
            ### UI
            - ui thing
            ## Rollout
            - not this
        """)
        self.assertEqual([c.text for c in cs], ["api thing", "ui thing"])

    def test_line_numbers(self):
        cs = parse_criteria("# T\n\n## Acceptance criteria\n- a\n- b\n")
        self.assertEqual([c.line for c in cs], [4, 5])

    def test_nothing_found(self):
        self.assertEqual(parse("Just prose.\n- a bullet\n"), [])


if __name__ == "__main__":
    unittest.main()
