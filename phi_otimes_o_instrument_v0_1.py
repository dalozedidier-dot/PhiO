"""Compatibility shim.

Tests and CI expect an executable instrument at repo root named:
  phi_otimes_o_instrument_v0_1.py

The reference implementation lives in scripts/phi_otimes_o_instrument_v0_1.py.
"""

from __future__ import annotations

from scripts.phi_otimes_o_instrument_v0_1 import main as _main  # noqa: F401

if __name__ == "__main__":
    raise SystemExit(_main())
