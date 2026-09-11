"""s2psee — open a Touchstone file and see S11/S21 in the terminal."""

from __future__ import annotations

__version__ = "0.2.0"
__all__ = ["Network", "ParseError", "__version__", "parse_touchstone"]

from s2psee.parse import Network, ParseError, parse_touchstone
