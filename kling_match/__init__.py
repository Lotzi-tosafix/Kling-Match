"""
Kling-Match - offline desktop app for ringtone cutting
"""

import os as _os

__version__ = open(
    _os.path.join(_os.path.dirname(__file__), "..", "version.txt"),
    encoding="utf-8",
).read().strip()
