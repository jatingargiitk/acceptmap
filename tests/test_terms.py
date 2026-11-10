import unittest

from acceptmap.terms import literals, same_term, stem, term_words, terms


class TermsTest(unittest.TestCase):
    def test_identifier_styles_reduce_to_same_terms(self):
        self.assertEqual(terms("LOGIN_MAX_ATTEMPTS"), ["login", "max", "attempt"])
        self.assertEqual(terms("loginMaxAttempts"), ["login", "max", "attempt"])
        self.assertEqual(terms("max login attempts"), ["max", "login", "attempt"])
        self.assertEqual(terms("login-max-attempts"), ["login", "max", "attempt"])

    def test_acronym_then_word(self):
        self.assertEqual(terms("HTTPResponse"), ["http", "respons"])

    def test_stopwords_and_short_words_dropped(self):
        self.assertEqual(terms("The user should be able to see it"), ["user", "see"])

    def test_meaningful_two_letter_words_kept(self):
        self.assertIn("ip", terms("per client IP"))

    def test_numbers_two_digits_or_more(self):
        self.assertEqual(terms("returns 429 after 5 tries"), ["429", "try"])

    def test_stemming(self):
        for w in ("limit", "limits", "limited", "limiting", "limiter"):
            self.assertEqual(stem(w), "limit", w)
        for w in ("expire", "expires", "expired", "expiring"):
            self.assertEqual(stem(w), "expir", w)
        self.assertEqual(stem("retries"), "retry")
        self.assertEqual(stem("status"), "status")
        self.assertEqual(stem("address"), "address")

    def test_same_term_prefix_rule(self):
        self.assertTrue(same_term("config", "configur"))
        self.assertTrue(same_term("token", "tokeniz"))
        self.assertFalse(same_term("log", "login"))  # shorter side under 5 chars
        self.assertFalse(same_term("login", "logout"))

    def test_term_words_keep_original_word_for_display(self):
        self.assertEqual(term_words("Empty tables export files"),
                         {"empty": "empty", "tabl": "tables", "export": "export", "fil": "files"})

    def test_literals(self):
        self.assertEqual(literals("set `Retry-After` and `LOGIN_MAX_ATTEMPTS`, not `x`"),
                         ["Retry-After", "LOGIN_MAX_ATTEMPTS"])
        self.assertEqual(literals("run `make all now`"), [])


if __name__ == "__main__":
    unittest.main()
