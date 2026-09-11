# s2psee

**Open a Touchstone `.s2p` file and see S11 / S21 in your terminal.**

打开 VNA 导出的 `.s2p`，不用 ADS、不用 MATLAB，一条命令看 S11 / S21。

[![CI](https://github.com/CAOShurong/s2psee/actions/workflows/ci.yml/badge.svg)](https://github.com/CAOShurong/s2psee/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

```console
$ pip install "git+https://github.com/CAOShurong/s2psee.git"
$ s2psee --demo
```

```
demo: series 100 nH in 50 Ω   2-port  S  RI  Z0=50 Ω   61 pts   1 MHz – 1 GHz
S11  max -0.11 dB @ 1 GHz   min -44.04 dB @ 1 MHz
S21  max -0.00 dB @ 1 MHz   min -16.07 dB @ 1 GHz   −3 dB @ 159 MHz

S21  (dB)
  -0.0 ██████████████████████████████████│
  -1.8                                   ██████│
  -3.6                                         ███│
  -5.4                                            ██│
  -7.1                                              ██│
  -8.9                                                ██│
 -10.7                                                  ██│
 -12.5                                                    ██│
 -14.3                                                      ██│
 -16.1                                                        █
       1 MHz                                              1 GHz  (log f)
```

`--demo` is a series 100 nH inductor between 50 Ω ports. Theory puts |S21| = −3 dB at 159 MHz (`ωL = 2 Z0`); the interpolated crossing in that plot is 159 MHz.

Point it at a real file from a VNA or simulator:

```console
$ s2psee filter.s2p
$ s2psee antenna.s1p --trace S11
$ s2psee filter.s2p --phase --trace S21
```

No dependencies. Python 3.9+. The parser is Touchstone v1 (`RI` / `MA` / `DB`, Hz–THz). Two-port data uses the v1 column-major order `N11 N21 N12 N22`.

```console
$ pipx run --spec git+https://github.com/CAOShurong/s2psee.git s2psee --demo
```

## What it will not do

This is a **viewer**, not a VNA, not ADS, and not scikit-rf.

- It plots **S-parameters only**. A file whose option line says `Y`, `Z`, `H` or `G` is rejected with that reason — convert or re-export as S.
- Touchstone **v2** keywords other than `[Number of Ports]` are skipped; noise blocks stop the parse. If your file is a v2 `.ts` with mixed networks, use a full RF library.
- The picture is a **log-frequency terminal sketch** of magnitude (default), phase, or VSWR. It is not a Smith chart and it does not de-embed, gate, or calibrate.
- The −3 dB marker is linear interpolation between two samples of |Sij|. It is not a fitted pole.

## License

MIT. Touchstone is a trademark of the relevant standards body; this project is not affiliated with them.
