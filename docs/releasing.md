<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Releasing

Versioning: SemVer. Every commit bumps the patch version (`scripts/commit.sh`), major
features bump the minor version (`--minor`).

1. Make sure `main` is green (CI, Docker) and the working tree is clean.
2. Tag the current version and push the tag:

   ```bash
   scripts/release.sh            # tags v<pyproject version> and pushes it
   ```

3. The **Release** workflow re-runs the full `localPipeline.sh`, checks that the tag
   matches `pyproject.toml`, builds sdist + wheel and creates the GitHub Release with
   both files attached. The **Docker** workflow publishes
   `ghcr.io/marcelpetrick/turingtongue:<version>` and `:latest`.

## PyPI (prepared, not active)

The release workflow contains a `pypi` job using **Trusted Publishing (OIDC)** — no
long-lived token. It only runs from a manual *Run workflow* with `publish_pypi = true`.
Before using it the owner must confirm the distribution name and register the trusted
publisher on PyPI (project `turingtongue`, workflow `release.yml`, environment `pypi`).
