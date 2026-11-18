"""Conversion of settings overrides from older addon versions."""
from typing import Any


def _convert_auto_key_default_key_time(overrides: dict[str, Any]) -> None:
    """Move the stored value from ``defualt_key_time`` to the fixed key.

    The auto key default frame was stored under the misspelled key
    ``defualt_key_time`` until the typo was fixed. Move any stored override
    to ``default_key_time`` so studios and projects keep the value they
    configured instead of silently falling back to the default.

    A value already stored under the corrected key wins, so this is safe to
    run more than once.
    """
    auto_key_default = overrides.get("auto_key_default")
    if not auto_key_default:
        return

    if "defualt_key_time" not in auto_key_default:
        return

    key_time = auto_key_default.pop("defualt_key_time")
    auto_key_default.setdefault("default_key_time", key_time)


def convert_settings_overrides(
    source_version: str,
    overrides: dict[str, Any],
) -> dict[str, Any]:
    """Convert studio settings overrides created by an older version.

    Args:
        source_version (str): Version the overrides were stored with.
        overrides (dict[str, Any]): Stored overrides, modified in place.

    Returns:
        dict[str, Any]: The converted overrides.
    """
    _convert_auto_key_default_key_time(overrides)
    return overrides
