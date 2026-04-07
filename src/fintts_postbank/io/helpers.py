"""Shared I/O helper functions for IOAdapter-based output and input."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fintts_postbank.io import IOAdapter


def io_output(io: IOAdapter | None, message: str) -> None:
    """Output message using IOAdapter or print."""
    if io is not None:
        io.output(message)
    else:
        print(message)


def io_input(io: IOAdapter | None, prompt: str) -> str:
    """Get input using IOAdapter or input()."""
    if io is not None:
        return io.input(prompt)
    return input(prompt)
