"""firelab/.env is read at start-up, and the shell always wins over it."""

import os
import tempfile
import unittest
from pathlib import Path

from firelab.app import dotenv


class TestDotenv(unittest.TestCase):
    def setUp(self):
        for name in ("DOTENV_TEST_A", "DOTENV_TEST_B", "DOTENV_TEST_C", "DOTENV_TEST_D"):
            os.environ.pop(name, None)

    def write(self, text):
        path = Path(tempfile.mkdtemp()) / ".env"
        path.write_text(text)
        return path

    def test_sets_missing_variables_and_reports_them(self):
        path = self.write("DOTENV_TEST_A=one\n# a comment\n\nexport DOTENV_TEST_B='two words'\nDOTENV_TEST_C=\"3\"\n")
        self.assertEqual(dotenv.load(path), ["DOTENV_TEST_A", "DOTENV_TEST_B", "DOTENV_TEST_C"])
        self.assertEqual(os.environ["DOTENV_TEST_A"], "one")
        self.assertEqual(os.environ["DOTENV_TEST_B"], "two words")
        self.assertEqual(os.environ["DOTENV_TEST_C"], "3")

    def test_the_shell_wins_over_the_file(self):
        os.environ["DOTENV_TEST_D"] = "from the shell"
        path = self.write("DOTENV_TEST_D=from the file\n")
        self.assertEqual(dotenv.load(path), [])
        self.assertEqual(os.environ["DOTENV_TEST_D"], "from the shell")

    def test_a_missing_file_is_not_an_error(self):
        self.assertEqual(dotenv.load(Path(tempfile.mkdtemp()) / ".env"), [])


if __name__ == "__main__":
    unittest.main()
