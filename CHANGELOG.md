# Changelog

## Unreleased

- `--compare FILE` plots magnitude-dB delta versus a second Touchstone file
  (this minus FILE), interpolated onto this frequency grid. Same-file compare
  is a flat 0 dB; port-count mismatch is an error.
- `--smith` draws an ASCII Smith chart of S11 (Γ-plane, unit circle and r=1).
  Coarse terminal sketch, not a calibrated chart.

## 0.1.0

- First public release: parse Touchstone v1 `.s1p`/`.s2p` (RI, MA, DB),
  plot S11/S21 in the terminal, and ship a `--demo` series-L network.
