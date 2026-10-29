"""Headless overlay-session generation checks (no windows or recognition)."""
import unittest
from types import SimpleNamespace
from captura import overlay_text as OT
from captura.textlayer import Word


class SessionGenerationTests(unittest.TestCase):
    def test_completion_from_abandoned_selection_cannot_match_the_next_selection(self):
        session = OT.TextSession(SimpleNamespace())
        session.job += 1             # first selection's start
        previous = session.job
        session.reset()
        session.job += 1             # second selection's start
        session.phase = "scan"
        session._done(previous, [Word("stale", (1, 1, 20, 20), (1, 1, 1))])
        self.assertIsNone(session.result)
        self.assertEqual(session.words, [])


if __name__ == "__main__":
    unittest.main()
