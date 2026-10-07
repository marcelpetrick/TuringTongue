<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Contract-test fixtures

Sanitized provider responses used by `tests/contract/`. Unless a file name says
otherwise, each fixture is copied from the provider's **official documentation
example** (researched 2026-10-07, see `docs/providers.md`), with long strings
shortened. No fixture contains credentials or user text beyond the docs' own
sample sentences.

When a live run reveals schema drift, add the sanitized real response as a new
fixture (`<provider>/<case>-<yyyy-mm-dd>.json`) plus a regression test.
