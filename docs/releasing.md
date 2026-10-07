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

## PyPI (automatic on tags once enabled)

Modelled on [lizard](https://github.com/terryyin/lizard/deployments/pypi): every version
tag builds once, publishes the GitHub Release, and — when enabled — uploads the same
wheel + sdist to PyPI from the `pypi` GitHub environment using **Trusted Publishing
(OIDC)**: no PyPI password or long-lived token is stored in GitHub. Deployments show
up under the repository's *Environments → pypi* tab, exactly like lizard's.

Status (2026-10-07): the name `turingtongue` is free on PyPI and TestPyPI; the `pypi`
GitHub environment exists; the workflow is ready. Publishing is **off** until the owner
does the one-time setup — PyPI only lets an account owner register a publisher, so this
step cannot be automated from the repository:

1. Log in to PyPI → *Your account → Publishing* → **Add a pending publisher** (GitHub):
   - PyPI project name: `turingtongue`
   - Owner: `marcelpetrick` · Repository: `TuringTongue`
   - Workflow name: `release.yml` · Environment name: `pypi`
2. Enable the job: `gh variable set PYPI_PUBLISH --body true`
3. Publish: either push the next tag (`scripts/release.sh`) or re-run an existing tag via
   *Actions → Release → Run workflow* (tag `v0.5.x`, `publish_pypi` = true).

The first successful upload turns the pending publisher into the real project. Fallback
(as in lizard): if a `PYPI_API_TOKEN` repository secret exists, the publish step uses it
instead of OIDC. Afterwards add the PyPI version badge to the README (only then is it a
real badge).
