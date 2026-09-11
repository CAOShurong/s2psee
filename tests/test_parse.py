from __future__ import annotations

import math
import unittest
from pathlib import Path

from s2psee.demo import demo_network, demo_touchstone, series_l_s21_3db_hz
from s2psee.parse import ParseError, mag_db, parse_touchstone_text
from s2psee.plot import crossing_hz, summarize

FIXTURES = Path(__file__).parent / "fixtures"


class ParseTests(unittest.TestCase):
    def test_ri_two_port_column_major(self) -> None:
        text = """
# HZ S RI R 50
! one point
1e6  0.1 0.0  0.0 0.5  0.0 -0.5  0.2 0.0
"""
        net = parse_touchstone_text(text, path="x.s2p")
        self.assertEqual(net.ports, 2)
        self.assertEqual(net.z0, 50.0)
        self.assertEqual(net.freq_hz, [1e6])
        self.assertAlmostEqual(net.s[0][0][0].real, 0.1)
        self.assertAlmostEqual(net.s[0][1][0].imag, 0.5)  # S21
        self.assertAlmostEqual(net.s[0][0][1].imag, -0.5)  # S12
        self.assertAlmostEqual(net.s[0][1][1].real, 0.2)

    def test_ma_and_db_round_trip(self) -> None:
        mag, ang = 0.5, 90.0
        ma = f"# GHZ S MA R 50\n1  {mag} {ang}\n"
        db = f"# GHZ S DB R 50\n1  {20*math.log10(mag)} {ang}\n"
        a = parse_touchstone_text(ma, path="a.s1p")
        b = parse_touchstone_text(db, path="b.s1p")
        self.assertAlmostEqual(a.s[0][0][0].real, 0.0, places=9)
        self.assertAlmostEqual(a.s[0][0][0].imag, 0.5, places=9)
        self.assertAlmostEqual(b.s[0][0][0].real, 0.0, places=6)
        self.assertAlmostEqual(b.s[0][0][0].imag, 0.5, places=6)
        self.assertAlmostEqual(a.freq_hz[0], 1e9)

    def test_rejects_y_parameters(self) -> None:
        with self.assertRaises(ParseError) as ctx:
            parse_touchstone_text("# HZ Y RI R 50\n1 0 0\n", path="y.s1p")
        self.assertIn("Y-parameters", str(ctx.exception))

    def test_rejects_missing_option_line(self) -> None:
        with self.assertRaises(ParseError):
            parse_touchstone_text("1 0 0\n", path="n.s1p")

    def test_demo_round_trip(self) -> None:
        generated = demo_network()
        parsed = parse_touchstone_text(demo_touchstone(), path="demo.s2p")
        self.assertEqual(len(parsed.freq_hz), len(generated.freq_hz))
        for i, (a, b) in enumerate(zip(generated.s, parsed.s)):
            self.assertAlmostEqual(a[1][0].real, b[1][0].real, places=7, msg=i)
            self.assertAlmostEqual(a[1][0].imag, b[1][0].imag, places=7, msg=i)

    def test_demo_minus3db_near_theory(self) -> None:
        net = demo_network()
        info = summarize(net, 2, 1)
        theory = series_l_s21_3db_hz()
        self.assertIsNotNone(info["minus3_hz"])
        self.assertLess(abs(info["minus3_hz"] - theory) / theory, 0.05)

    def test_crossing(self) -> None:
        hz = crossing_hz([0.0, 10.0], [0.0, -10.0], -3.0)
        self.assertAlmostEqual(hz, 3.0)

    def test_mag_db_zero(self) -> None:
        self.assertLess(mag_db(0j), -100)

    def test_fixture_file(self) -> None:
        from s2psee.parse import parse_touchstone

        net = parse_touchstone(FIXTURES / "series_l.s2p")
        self.assertEqual(net.ports, 2)
        self.assertGreater(len(net.freq_hz), 3)


if __name__ == "__main__":
    unittest.main()
