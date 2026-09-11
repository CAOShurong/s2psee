"""A series 100 nH inductor between 50 Ω ports — a known S21 roll-off."""

from __future__ import annotations

import math

from s2psee.parse import Network

Z0 = 50.0
L_H = 100e-9
N_POINTS = 61
F_START = 1e6
F_STOP = 1e9


def series_l_s21_3db_hz() -> float:
    """|S21| = 1/sqrt(2) when ωL = 2 Z0."""
    return (2.0 * Z0) / (2.0 * math.pi * L_H)


def demo_network() -> Network:
    freqs = [
        F_START * (F_STOP / F_START) ** (k / (N_POINTS - 1)) for k in range(N_POINTS)
    ]
    matrices = []
    for f in freqs:
        z = 1j * 2.0 * math.pi * f * L_H
        s11 = z / (z + 2.0 * Z0)
        s21 = (2.0 * Z0) / (z + 2.0 * Z0)
        matrices.append([[s11, s21], [s21, s11]])
    return Network(
        path="demo: series 100 nH in 50 ohm",
        ports=2,
        param="S",
        fmt="RI",
        z0=Z0,
        freq_hz=freqs,
        s=matrices,
    )


def demo_touchstone() -> str:
    """RI .s2p text matching :func:`demo_network`."""
    lines = [
        "! s2psee demo: series 100 nH between 50 ohm ports",
        "# HZ S RI R 50",
    ]
    net = demo_network()
    for f, m in zip(net.freq_hz, net.s):
        n11, n21, n12, n22 = m[0][0], m[1][0], m[0][1], m[1][1]
        lines.append(
            f"{f:.9e} {n11.real:.9e} {n11.imag:.9e} "
            f"{n21.real:.9e} {n21.imag:.9e} "
            f"{n12.real:.9e} {n12.imag:.9e} "
            f"{n22.real:.9e} {n22.imag:.9e}"
        )
    return "\n".join(lines) + "\n"
