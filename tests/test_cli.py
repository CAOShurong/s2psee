from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from s2psee.cli import main
from s2psee.demo import demo_touchstone

FIXTURES = Path(__file__).parent / "fixtures"


class CliTests(unittest.TestCase):
    def test_demo_exit_zero_and_mentions_s21(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["--demo"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("S21", out)
        self.assertIn("dB", out)
        self.assertIn("100 nH", out)

    def test_file_argument(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main([str(FIXTURES / "series_l.s2p")])
        self.assertEqual(code, 0)
        self.assertIn("S11", buf.getvalue())

    def test_missing_file(self) -> None:
        err = io.StringIO()
        with redirect_stderr(err):
            code = main(["no-such-file.s2p"])
        self.assertEqual(code, 2)
        self.assertIn("not a file", err.getvalue())

    def test_no_args(self) -> None:
        err = io.StringIO()
        with redirect_stderr(err):
            code = main([])
        self.assertEqual(code, 2)

    def test_bad_touchstone(self) -> None:
        bad = FIXTURES / "empty.txt"
        err = io.StringIO()
        with redirect_stderr(err):
            code = main([str(bad)])
        self.assertEqual(code, 1)

    def test_smith_mode(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["--demo", "--smith"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("Smith", out)
        self.assertIn("S11", out)
        self.assertIn("@", out)
        self.assertNotIn("S21  (dB)", out)

    def test_smith_rejects_phase(self) -> None:
        err = io.StringIO()
        with redirect_stderr(err):
            code = main(["--demo", "--smith", "--phase"])
        self.assertEqual(code, 2)
        self.assertIn("smith", err.getvalue())

    def test_phase_mode(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["--demo", "--phase", "--trace", "S21"])
        self.assertEqual(code, 0)
        self.assertIn("deg", buf.getvalue())

    def test_demo_survives_cp1252_stdout(self) -> None:
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="cp1252", errors="strict", newline="\n")
        with redirect_stdout(stream):
            code = main(["--demo"])
        stream.flush()
        self.assertEqual(code, 0)
        text = raw.getvalue().decode("utf-8", errors="replace")
        if "S21" not in text:
            text = raw.getvalue().decode("cp1252", errors="replace")
        self.assertIn("S21", text)
        self.assertNotIn("\u03a9", text)

    def test_memory_roundtrip_via_tmp(self) -> None:
        path = FIXTURES / "series_l.s2p"
        self.assertIn("# HZ S RI R 50", path.read_text(encoding="utf-8"))
        self.assertIn(demo_touchstone().splitlines()[1], "# HZ S RI R 50")


if __name__ == "__main__":
    unittest.main()
