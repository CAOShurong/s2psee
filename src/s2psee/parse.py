"""Touchstone v1 parser. Converts every supported file to complex S-parameters."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

FREQ_SCALE = {
    "HZ": 1.0,
    "KHZ": 1e3,
    "MHZ": 1e6,
    "GHZ": 1e9,
    "THZ": 1e12,
}

PAIR_FORMATS = {"RI", "MA", "DB"}
PARAMS = {"S", "Y", "Z", "H", "G"}


class ParseError(ValueError):
    """The file is not a Touchstone network we can plot."""


@dataclass
class Network:
    path: str
    ports: int
    param: str
    fmt: str
    z0: float
    freq_hz: list[float]
    s: list[list[list[complex]]]  # [freq][row][col], 0-based, S-parameters

    def s_at(self, i: int, j: int) -> list[complex]:
        """Sij traces, 1-based port indices."""
        return [matrix[i - 1][j - 1] for matrix in self.s]


def parse_touchstone(path: str | Path, ports: int | None = None) -> Network:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return parse_touchstone_text(text, path=str(path), ports=ports)


def parse_touchstone_text(
    text: str,
    path: str = "<memory>",
    ports: int | None = None,
) -> Network:
    if text.startswith("\ufeff"):
        text = text[1:]
    if ports is None:
        ports = _ports_from_name(path)

    option = None
    numbers: list[float] = []
    saw_version = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("!"):
            continue
        if line.startswith("["):
            saw_version = True
            key = line.split("]", 1)[0][1:].strip().lower()
            rest = line.split("]", 1)[1].strip() if "]" in line else ""
            if key == "number of ports" and rest:
                try:
                    ports = int(rest.split()[0])
                except ValueError as exc:
                    raise ParseError(f"{path}: bad [Number of Ports] line") from exc
            if key in {"noise data", "end"}:
                break
            continue
        if line.startswith("#"):
            if option is not None:
                raise ParseError(f"{path}: more than one option line")
            option = _parse_option(line, path)
            continue
        if "!" in line:
            line = line[: line.index("!")].strip()
            if not line:
                continue
        try:
            numbers.extend(float(tok) for tok in line.split())
        except ValueError as exc:
            raise ParseError(f"{path}: not a number in data line {line!r}") from exc

    if option is None:
        raise ParseError(f"{path}: no Touchstone option line starting with #")
    if option["param"] != "S":
        raise ParseError(
            f"{path}: this file stores {option['param']}-parameters; "
            "export S-parameters from the VNA or simulator and retry"
        )
    if ports is None:
        ports = 2 if saw_version else _infer_ports(len(numbers), option["fmt"])
    if ports < 1:
        raise ParseError(f"{path}: port count must be >= 1")

    pair = 2
    cells = ports * ports
    # 2-port v1 is column-major: N11 N21 N12 N22. Others are row-major.
    width = 1 + pair * cells
    if len(numbers) < width:
        raise ParseError(f"{path}: not enough numbers for a {ports}-port network")
    if len(numbers) % width:
        raise ParseError(
            f"{path}: {len(numbers)} numbers is not a multiple of {width} "
            f"(freq + {cells} complex pairs)"
        )

    freq_hz: list[float] = []
    s: list[list[list[complex]]] = []
    scale = option["freq_scale"]
    fmt = option["fmt"]
    for base in range(0, len(numbers), width):
        row = numbers[base : base + width]
        freq_hz.append(row[0] * scale)
        pairs = [_pair_to_complex(row[1 + 2 * k], row[2 + 2 * k], fmt) for k in range(cells)]
        s.append(_pairs_to_matrix(pairs, ports))

    if any(freq_hz[i] >= freq_hz[i + 1] for i in range(len(freq_hz) - 1)):
        raise ParseError(f"{path}: frequencies must be strictly increasing")

    return Network(
        path=path,
        ports=ports,
        param="S",
        fmt=fmt,
        z0=option["z0"],
        freq_hz=freq_hz,
        s=s,
    )


def _parse_option(line: str, path: str) -> dict:
    tokens = line[1:].strip().split()
    freq_unit = "GHZ"
    param = "S"
    fmt = "MA"
    z0 = 50.0
    i = 0
    while i < len(tokens):
        tok = tokens[i].upper()
        if tok in FREQ_SCALE:
            freq_unit = tok
        elif tok in PARAMS:
            param = tok
        elif tok in PAIR_FORMATS:
            fmt = tok
        elif tok == "R":
            if i + 1 >= len(tokens):
                raise ParseError(f"{path}: option line has R without a value")
            try:
                z0 = float(tokens[i + 1])
            except ValueError as exc:
                raise ParseError(f"{path}: bad reference impedance") from exc
            i += 1
        else:
            raise ParseError(f"{path}: unknown option-line token {tokens[i]!r}")
        i += 1
    if z0 <= 0:
        raise ParseError(f"{path}: reference impedance must be positive")
    return {"freq_scale": FREQ_SCALE[freq_unit], "param": param, "fmt": fmt, "z0": z0}


def _pair_to_complex(a: float, b: float, fmt: str) -> complex:
    if fmt == "RI":
        return complex(a, b)
    angle = math.radians(b)
    mag = a if fmt == "MA" else 10 ** (a / 20.0)
    return mag * complex(math.cos(angle), math.sin(angle))


def _pairs_to_matrix(pairs: list[complex], ports: int) -> list[list[complex]]:
    matrix = [[0j] * ports for _ in range(ports)]
    if ports == 2:
        # Touchstone v1 two-port order is N11, N21, N12, N22.
        matrix[0][0], matrix[1][0], matrix[0][1], matrix[1][1] = pairs
        return matrix
    k = 0
    for row in range(ports):
        for col in range(ports):
            matrix[row][col] = pairs[k]
            k += 1
    return matrix


def _ports_from_name(path: str) -> int | None:
    match = re.search(r"\.s(\d+)p$", path, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _infer_ports(n_numbers: int, fmt: str) -> int:
    del fmt
    # freq + 2*n^2 numbers per point. Try n=1 then n=2.
    for ports in (1, 2):
        width = 1 + 2 * ports * ports
        if n_numbers >= width and n_numbers % width == 0:
            return ports
    raise ParseError("could not infer port count; pass a .s1p/.s2p name or --ports")


def mag_db(z: complex) -> float:
    mag = abs(z)
    if mag <= 0.0:
        return -400.0
    return 20.0 * math.log10(mag)


def phase_deg(z: complex) -> float:
    return math.degrees(math.atan2(z.imag, z.real))


def vswr(z: complex) -> float:
    gamma = abs(z)
    if gamma >= 1.0:
        return float("inf")
    return (1.0 + gamma) / (1.0 - gamma)
