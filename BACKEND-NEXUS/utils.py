# 版本号转换为数字，如1.0.0 -> 100
from typing import List


def version2Number(version_str: str) -> int:
    try:
        parts = version_str.split(".")
        if len(parts) == 3:
            major, minor, patch = parts
            return int(major) * 100 + int(minor) * 10 + int(patch)
        return 0
    except (ValueError, AttributeError):
        return 0


def string2Bool(value) -> bool:
    """Parse bool from query/body values (Robyn may yield str or bool)."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).lower() == "true"