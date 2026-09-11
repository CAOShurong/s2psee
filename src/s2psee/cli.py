from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TextIO

from s2psee import __version__
from s2psee.demo import demo_network
from s2psee.parse import ParseError, parse_touchstone
from s2psee.plot import render_network


def _force_utf8(stream: TextIO) -> None:
    """Windows cp1252 consoles raise on Ω/█; UTF-8 with replace does not."""
    reconfigure = getattr(stream, "reconfigure", None)
    if not callable(reconfigure):
        return
    try:
        reconfigure(encoding="utf-8", errors="replace")
    except (OSError, ValueError, AttributeError):
        return


def emit(text: str, stream: TextIO | None = None) -> None:
    stream = sys.stdout if stream is None else stream
    encoding = getattr(stream, "encoding", None) or "utf-8"
    buf = getattr(stream, "buffer", None)
    payload = text.encode(encoding, errors="replace")
    if buf is not None:
        try:
            buf.write(payload)
            buf.flush()
            return
        except (OSError, ValueError, AttributeError):
            pass
    stream.write(payload.decode(encoding, errors="replace"))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="s2psee",
        description="Open a Touchstone .s1p/.s2p file and plot S-parameters in the terminal.",
    )
    p.add_argument("file", nargs="?", help="Touchstone file (.s1p, .s2p, …)")
    p.add_argument(
        "--demo",
        action="store_true",
        help="plot a built-in series 100 nH inductor (no file needed)",
    )
    p.add_argument(
        "--ports",
        type=int,
        default=None,
        help="override port count when the filename is not .sNp",
    )
    p.add_argument(
        "--trace",
        action="append",
        default=[],
        metavar="Sij",
        help="trace to plot, e.g. S11 or S21 (repeatable). Default: S11 and S21",
    )
    p.add_argument(
        "--phase",
        action="store_true",
        help="plot phase in degrees instead of magnitude in dB",
    )
    p.add_argument(
        "--vswr",
        action="store_true",
        help="plot VSWR instead of magnitude in dB",
    )
    p.add_argument(
        "--smith",
        action="store_true",
        help="plot an ASCII Smith chart of the trace (default S11)",
    )
    p.add_argument("--width", type=int, default=64, help="plot width in characters")
    p.add_argument("--version", action="version", version=f"s2psee {__version__}")
    return p


def _parse_trace(token: str) -> tuple[int, int]:
    t = token.strip().upper()
    if t.startswith("S"):
        t = t[1:]
    if len(t) != 2 or not t.isdigit():
        raise argparse.ArgumentTypeError(f"bad trace {token!r}; expected S11 or S21")
    return int(t[0]), int(t[1])


def main(argv: list[str] | None = None) -> int:
    _force_utf8(sys.stdout)
    _force_utf8(sys.stderr)
    args = build_parser().parse_args(argv)
    modes = [
        name
        for name, on in (("phase", args.phase), ("vswr", args.vswr), ("smith", args.smith))
        if on
    ]
    if len(modes) > 1:
        print("s2psee: choose at most one of --phase, --vswr, --smith", file=sys.stderr)
        return 2
    if not args.demo and not args.file:
        print("s2psee: pass a .s2p file, or --demo", file=sys.stderr)
        return 2

    try:
        if args.demo and not args.file:
            net = demo_network()
        else:
            path = Path(args.file)
            if not path.is_file():
                print(f"s2psee: {path} is not a file", file=sys.stderr)
                return 2
            net = parse_touchstone(path, ports=args.ports)
    except (OSError, ParseError) as exc:
        print(f"s2psee: {exc}", file=sys.stderr)
        return 1

    try:
        traces = [_parse_trace(t) for t in args.trace] or None
    except argparse.ArgumentTypeError as exc:
        print(f"s2psee: {exc}", file=sys.stderr)
        return 2
    if args.smith and traces is None:
        traces = [(1, 1)]
    mode = "smith" if args.smith else "phase" if args.phase else "vswr" if args.vswr else "db"
    try:
        text = render_network(net, traces=traces, mode=mode, width=args.width)
    except ValueError as exc:
        print(f"s2psee: {exc}", file=sys.stderr)
        return 2
    emit(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
