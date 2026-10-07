<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Releasing

Versioning: SemVer. Every commit bumps the patch version (`scripts/commit.sh`), major
features bump the minor version (`--minor`).

1. Make sure `main` is green (CI, Docker) and the working tree is clean.
2. Tag the current version and push the tag:

   ```bash
   scripts/release.sh            # refreshes + commits the history chart, tags, pushes the tag
   ```

3. The **Release** workflow re-runs the full `localPipeline.sh`, checks that the tag
   matches `pyproject.toml`, builds sdist + wheel and creates the GitHub Release with
   both files attached. The **Docker** workflow publishes
   `ghcr.io/marcelpetrick/turingtongue:<version>` and `:latest`.

## Supply-chain hardening (industry practice)

Follows the PyPA guide [Publishing package distribution releases using GitHub
Actions](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/)
and PyPI's [Trusted Publishers](https://docs.pypi.org/trusted-publishers/) documentation:

| Control | Where | Effect |
| --- | --- | --- |
| Protected release tags | repository ruleset `protect-release-tags` | only admins can create, move or delete `v*` tags |
| Tag must equal package version | `release.yml` build job | no mislabelled releases |
| Full quality gate before any upload | `release.yml` runs `./localPipeline.sh` | tests, types, audit, wheel e2e, Docker smoke must pass |
| Build once, publish the same files | build job → artifact → release / PyPI jobs | GitHub Release and PyPI get identical bytes |
| Signed build provenance | `actions/attest-build-provenance` on `dist/*` | verify with `gh attestation verify <file> -R marcelpetrick/TuringTongue` |
| Trusted Publishing (OIDC) only | `pypi` job, `id-token: write` scoped to that job | no long-lived PyPI token exists anywhere |
| PEP 740 attestations on PyPI | `pypa/gh-action-pypi-publish` (automatic with OIDC) | PyPI shows verifiable provenance |
| Human approval before upload | environment `pypi`: required reviewer = owner | uploads are irreversible, so one click approves each |
| Deployments only from tags | environment `pypi`: deployment policy `v*` (tag) | a branch run can never publish |
| Image provenance + SBOM | `docker.yml`: `provenance: mode=max`, `sbom: true` | GHCR image carries SLSA provenance and an SBOM |

## PyPI publishing

Status (2026-10-07): the name `turingtongue` is free on PyPI and TestPyPI; the protected
`pypi` environment and the workflow are ready. Publishing stays **off** until the owner
does the one-time setup — PyPI only lets an account owner register a publisher:

1. Log in to PyPI → *Your account → Publishing* → **Add a pending publisher** (GitHub):
   - PyPI project name: `turingtongue`
   - Owner: `marcelpetrick` · Repository: `TuringTongue`
   - Workflow name: `release.yml` · Environment name: `pypi`
2. Enable the job: `gh variable set PYPI_PUBLISH --body true`
3. Publish: push the next tag (`scripts/release.sh`) or re-run an existing tag via
   *Actions → Release → Run workflow*; then **approve** the waiting `pypi` deployment.

The first successful upload turns the pending publisher into the real project.
Afterwards add the PyPI version badge to the README (only then is it a real badge).
