# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Optional browser-automation fallback (``pip install turingtongue[browser]``).

API-only users never import Playwright: it is loaded lazily inside a browser run.
See docs/adr/0003-browser-fallback.md for why no site adapter ships today.
"""
