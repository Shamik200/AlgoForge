"""Adapter to optional external Fundamental-System project.

Attempts to locate a sibling folder named 'Fundamental-System/src' and import
its `tools` and `main` helpers. Exposes simple wrappers used by the
`algoforge.fundamental` pipeline so the trading repo can reuse the user's
standalone Fundamental-System implementation when present.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_loaded = False
_tools = None
_main = None


def _call_tool(tool: Any, *args: Any, **kwargs: Any) -> Any:
    if hasattr(tool, "invoke"):
        payload = kwargs if kwargs else (args[0] if len(args) == 1 else args)
        return tool.invoke(payload)
    return tool(*args, **kwargs)


def _locate_and_import() -> None:
    global _loaded, _tools, _main
    if _loaded:
        return

    # Search upwards for the workspace root, then look for a sibling
    # Fundamental-System/src directory next to the trading repo.
    path = Path(__file__).resolve()
    for base in path.parents:
        candidate = base.parent / "Fundamental-System" / "src"
        if not candidate.exists():
            continue

        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)

        try:
            _tools = importlib.import_module("tools")
        except Exception:
            _tools = None
        try:
            _main = importlib.import_module("main")
        except Exception:
            _main = None
        _loaded = True
        return

    # Not found; mark loaded to avoid repeated searches
    _loaded = True


def available() -> bool:
    _locate_and_import()
    return _tools is not None or _main is not None


def fetch_market_context(assets: List[str]) -> Optional[Dict[str, Any]]:
    """Call the external project's `fetch_market_context` if available.

    Returns the dict returned by the external tool or None if unavailable.
    """
    _locate_and_import()
    if _tools and hasattr(_tools, "fetch_market_context"):
        try:
            return _call_tool(_tools.fetch_market_context, assets)
        except Exception:
            return None
    return None


def fetch_macro_data() -> Optional[Dict[str, Any]]:
    _locate_and_import()
    if _tools and hasattr(_tools, "fetch_macro_data"):
        try:
            return _call_tool(_tools.fetch_macro_data)
        except Exception:
            return None

    # Try main.fetch_live_news as a last-ditch source for news (not macro)
    return None


def fetch_live_news() -> Optional[List[Dict[str, Any]]]:
    """Return a list of news dicts if the external project's `main.fetch_live_news` exists."""
    _locate_and_import()
    if _main and hasattr(_main, "fetch_live_news"):
        try:
            return _main.fetch_live_news()
        except Exception:
            return None
    return None
