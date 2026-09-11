"""Terminal plots and numeric summaries. No numpy, no matplotlib."""

from __future__ import annotations

import math
from typing import Iterable

from s2psee.parse import Network, mag_db, phase_deg, vswr

def format_freq(hz: float) -> str:
    ah = abs(hz)
    if ah >= 1e9:
        return f"{hz / 1e9:.3g} GHz"
    if ah >= 1e6:
        return f"{hz / 1e6:.3g} MHz"
    if ah >= 1e3:
        return f"{hz / 1e3:.3g} kHz"
    return f"{hz:.3g} Hz"


def format_db(value: float) -> str:
    if value <= -200:
        return "-inf dB"
    return f"{value:.2f} dB"


def crossing_hz(freq: list[float], values: list[float], threshold: float) -> float | None:
    """First frequency where `values` falls through `threshold` (high to low)."""
    for i in range(len(values) - 1):
        a, b = values[i], values[i + 1]
        if a >= threshold > b:
            if b == a:
                return freq[i]
            frac = (threshold - a) / (b - a)
            return freq[i] + frac * (freq[i + 1] - freq[i])
    return None


def downsample(xs: list[float], ys: list[float], width: int) -> list[float | None]:
    """Bin by log10(frequency). VNA sweeps are almost always log-spaced."""
    if width < 8:
        width = 8
    if not xs:
        return [None] * width
    logs = [math.log10(x) if x > 0 else 0.0 for x in xs]
    xmin, xmax = logs[0], logs[-1]
    bins: list[list[float]] = [[] for _ in range(width)]
    span = xmax - xmin
    for x, y in zip(logs, ys):
        if span <= 0:
            idx = 0
        else:
            idx = int((x - xmin) / span * (width - 1))
            idx = min(max(idx, 0), width - 1)
        bins[idx].append(y)
    last: float | None = None
    out: list[float | None] = []
    for bucket in bins:
        if bucket:
            last = sum(bucket) / len(bucket)
            out.append(last)
        else:
            out.append(last)
    return out


def sparkline(values: list[float | None], height: int = 10) -> list[str]:
    present = [v for v in values if v is not None]
    if not present:
        return [" " * len(values) for _ in range(height)]
    lo, hi = min(present), max(present)
    if math.isclose(lo, hi):
        hi = lo + 1.0
        lo = lo - 1.0
    rows = [[" "] * len(values) for _ in range(height)]
    scale = height - 1
    prev = None
    for x, v in enumerate(values):
        if v is None:
            continue
        y = int(round((v - lo) / (hi - lo) * scale))
        y = min(max(y, 0), scale)
        if prev is not None:
            step = 1 if y >= prev else -1
            for mid in range(prev, y, step):
                rows[scale - mid][x] = "│"
        rows[scale - y][x] = "█"
        prev = y
    left = _axis_labels(hi, lo, height)
    width_lab = max(len(s) for s in left)
    lines = []
    for i, row in enumerate(rows):
        lines.append(f"{left[i].rjust(width_lab)} {''.join(row)}")
    return lines


def _axis_labels(hi: float, lo: float, height: int) -> list[str]:
    labels = []
    for i in range(height):
        frac = i / (height - 1) if height > 1 else 0
        val = hi - frac * (hi - lo)
        labels.append(f"{val:6.1f}")
    return labels


def render_trace(
    freq: list[float],
    values: list[float],
    title: str,
    unit: str,
    width: int = 64,
    height: int = 10,
) -> str:
    cols = downsample(freq, values, width)
    body = sparkline(cols, height=height)
    axis = (
        " " * 7
        + format_freq(freq[0]).ljust(width // 2)
        + format_freq(freq[-1]).rjust(width - width // 2)
        + "  (log f)"
    )
    return "\n".join([title + (f"  ({unit})" if unit else ""), *body, axis])


def summarize(net: Network, i: int, j: int) -> dict:
    trace = net.s_at(i, j)
    dbs = [mag_db(z) for z in trace]
    peak_i = max(range(len(dbs)), key=lambda k: dbs[k])
    floor_i = min(range(len(dbs)), key=lambda k: dbs[k])
    minus3 = crossing_hz(net.freq_hz, dbs, -3.0)
    return {
        "name": f"S{i}{j}",
        "max_db": dbs[peak_i],
        "max_hz": net.freq_hz[peak_i],
        "min_db": dbs[floor_i],
        "min_hz": net.freq_hz[floor_i],
        "minus3_hz": minus3,
        "dbs": dbs,
        "deg": [phase_deg(z) for z in trace],
        "vswr": [vswr(z) for z in trace],
    }


def render_network(
    net: Network,
    traces: Iterable[tuple[int, int]] | None = None,
    mode: str = "db",
    width: int = 64,
) -> str:
    if traces is None:
        traces = [(1, 1), (2, 1)] if net.ports >= 2 else [(1, 1)]
    lines = [
        f"{net.path}   {net.ports}-port  S  {net.fmt}  Z0={net.z0:g} ohm   "
        f"{len(net.freq_hz)} pts   {format_freq(net.freq_hz[0])} - {format_freq(net.freq_hz[-1])}"
    ]
    plots = []
    for i, j in traces:
        if i > net.ports or j > net.ports:
            raise ValueError(f"S{i}{j} needs a {max(i, j)}-port file")
        info = summarize(net, i, j)
        extra = ""
        if info["minus3_hz"] is not None and (i, j) != (1, 1):
            extra = f"   -3 dB @ {format_freq(info['minus3_hz'])}"
        lines.append(
            f"{info['name']}  max {format_db(info['max_db'])} @ {format_freq(info['max_hz'])}"
            f"   min {format_db(info['min_db'])} @ {format_freq(info['min_hz'])}"
            f"{extra}"
        )
        if mode == "phase":
            plots.append(
                render_trace(net.freq_hz, info["deg"], info["name"], "deg", width=width)
            )
        elif mode == "vswr":
            finite = [v if math.isfinite(v) else 99.0 for v in info["vswr"]]
            plots.append(
                render_trace(net.freq_hz, finite, info["name"], "VSWR", width=width)
            )
        else:
            plots.append(
                render_trace(net.freq_hz, info["dbs"], info["name"], "dB", width=width)
            )
    return "\n".join(lines) + "\n\n" + "\n\n".join(plots) + "\n"
