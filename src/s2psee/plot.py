"""Terminal plots and numeric summaries. No numpy, no matplotlib."""

from __future__ import annotations

import math
from collections.abc import Iterable

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


def z_normalized(gamma: complex) -> complex | None:
    """z/Z0 from Γ. None at the open-circuit pole."""
    denom = 1.0 - gamma
    if abs(denom) < 1e-12:
        return None
    return (1.0 + gamma) / denom


def render_smith(
    freq: list[float],
    gamma: list[complex],
    name: str,
    height: int = 17,
) -> str:
    """ASCII Γ-plane sketch. Character cells are ~2:1, so width is 2*height-1."""
    if height < 9:
        height = 9
    if height % 2 == 0:
        height += 1
    width = height * 2 - 1
    canvas = [[" "] * width for _ in range(height)]
    cx, cy = width // 2, height // 2
    rx, ry = float(cx), float(cy)

    def put(gx: float, gy: float, ch: str, *, overlay: bool = False) -> None:
        x = cx + round(gx * rx)
        y = cy - round(gy * ry)
        if 0 <= y < height and 0 <= x < width and (overlay or canvas[y][x] == " "):
            canvas[y][x] = ch

    def circle(gcx: float, gcy: float, radius: float, ch: str) -> None:
        for t in range(0, 360, 2):
            ang = math.radians(t)
            put(gcx + radius * math.cos(ang), gcy + radius * math.sin(ang), ch)

    circle(0.0, 0.0, 1.0, ".")  # |Γ|=1
    circle(0.5, 0.0, 0.5, ":")  # r=1 (Z0 match circle)

    for g in gamma:
        mag = abs(g)
        if mag > 1.05:
            g = g / mag
        put(g.real, g.imag, "*", overlay=True)
    last = gamma[-1]
    put(last.real, last.imag, "@", overlay=True)

    canvas[0][cx] = "j"
    canvas[height - 1][cx] = "v"
    canvas[cy][0] = "s"
    canvas[cy][width - 1] = "o"

    zlast = z_normalized(last)
    ztxt = "z/Z0 inf" if zlast is None else f"z/Z0 {zlast.real:.2f}{zlast.imag:+.2f}j"
    head = (
        f"{name}  Smith  {format_freq(freq[0])} -> {format_freq(freq[-1])}  "
        f"end |{name}| {format_db(mag_db(last))}  {phase_deg(last):.0f} deg  {ztxt}"
    )
    legend = "  .=|G|=1  :=r=1  *=sweep  @=stop  s=short  o=open  j=+j  v=-j"
    body = ["".join(row) for row in canvas]
    return "\n".join([head, *body, legend])


def interp_complex(
    src_f: list[float], src_z: list[complex], dst_f: list[float]
) -> list[complex | None]:
    """Linear interpolate Re/Im onto ``dst_f``. None outside the source span."""
    if not src_f:
        return [None] * len(dst_f)
    out: list[complex | None] = []
    j = 0
    n = len(src_f)
    for f in dst_f:
        if f < src_f[0] or f > src_f[-1]:
            out.append(None)
            continue
        while j + 1 < n and src_f[j + 1] < f:
            j += 1
        if j + 1 >= n or src_f[j] == f:
            out.append(src_z[j])
            continue
        span = src_f[j + 1] - src_f[j]
        t = 0.0 if span == 0 else (f - src_f[j]) / span
        a, b = src_z[j], src_z[j + 1]
        out.append(a + t * (b - a))
    return out


def compare_networks(
    this: Network,
    other: Network,
    traces: Iterable[tuple[int, int]] | None = None,
    width: int = 64,
) -> str:
    """Magnitude-dB delta: this minus other, interpolated onto this frequency grid."""
    if this.ports != other.ports:
        raise ValueError(
            f"port count mismatch: {this.path} is {this.ports}-port, "
            f"{other.path} is {other.ports}-port"
        )
    if traces is None:
        traces = [(1, 1), (2, 1)] if this.ports >= 2 else [(1, 1)]
    lo = max(this.freq_hz[0], other.freq_hz[0])
    hi = min(this.freq_hz[-1], other.freq_hz[-1])
    if lo >= hi:
        raise ValueError("the two files have no overlapping frequency range")
    freq = [f for f in this.freq_hz if lo <= f <= hi]
    if len(freq) < 2:
        raise ValueError("need at least two overlapping frequency points to compare")

    znote = ""
    if this.z0 != other.z0:
        znote = f"   Z0 {this.z0:g} vs {other.z0:g} ohm (S still compared)"
    lines = [
        f"compare  {this.path}  minus  {other.path}{znote}",
        f"overlap  {format_freq(freq[0])} - {format_freq(freq[-1])}  {len(freq)} pts",
    ]
    plots = []
    for i, j in traces:
        if i > this.ports or j > this.ports:
            raise ValueError(f"S{i}{j} needs a {max(i, j)}-port file")
        a = interp_complex(this.freq_hz, this.s_at(i, j), freq)
        b = interp_complex(other.freq_hz, other.s_at(i, j), freq)
        delta: list[float] = []
        used_f: list[float] = []
        for f, za, zb in zip(freq, a, b):
            if za is None or zb is None:
                continue
            used_f.append(f)
            delta.append(mag_db(za) - mag_db(zb))
        if not delta:
            raise ValueError(f"S{i}{j}: no overlapping samples")
        peak = max(range(len(delta)), key=lambda k: abs(delta[k]))
        lines.append(
            f"S{i}{j}  max |Δ| {format_db(abs(delta[peak]))} @ {format_freq(used_f[peak])}"
            f"   mean Δ {format_db(sum(delta) / len(delta))}"
        )
        plots.append(render_trace(used_f, delta, f"S{i}{j}  ΔdB", "this-other", width=width))
    return "\n".join(lines) + "\n\n" + "\n\n".join(plots) + "\n"


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
            plots.append(render_trace(net.freq_hz, finite, info["name"], "VSWR", width=width))
        elif mode == "smith":
            plots.append(render_smith(net.freq_hz, net.s_at(i, j), info["name"], height=17))
        else:
            plots.append(
                render_trace(net.freq_hz, info["dbs"], info["name"], "dB", width=width)
            )
    return "\n".join(lines) + "\n\n" + "\n\n".join(plots) + "\n"
