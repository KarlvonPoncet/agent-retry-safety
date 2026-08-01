"""Entry point for the Agent Retry Safety Streamlit dashboard.

Run locally with:

    streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path


_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from retry_safety_dashboard import main  # noqa: E402


if __name__ == "__main__":
    main()
