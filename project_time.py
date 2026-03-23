"""
Shared clock helpers so date-sensitive code can be patched in tests.
"""

from datetime import date


def today() -> date:
    """Return the current local date."""
    return date.today()


def current_year() -> int:
    """Return the current local calendar year."""
    return today().year
