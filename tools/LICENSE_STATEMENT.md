# Statement: does any strong copyleft dependency reach this repository's source tree?

Date: 2026-09-16
Scope: `gsy-e` (this repository) only.
Author: dev@gridsingularity.com, assisted scan via `pip-licenses` + `tools/check_licenses.py`.

## Question

For the planned relicensing of `gsy-e`, does any strong-copyleft-licensed
third-party component reach source control (i.e. does any GPL/AGPL/SSPL/etc.
source end up committed or vendored into this repository), as opposed to
being used only as an external, separately-distributed tool?

## Finding

**No.** No strong-copyleft source code is vendored, copied, or otherwise
committed into this repository's source tree.

Basis for this conclusion:

1. **No vendoring.** All of `gsy-e`'s dependencies are resolved externally at
   install time via `pip`/`requirements/*.txt` (or, for `gsy-framework` and
   the optional `gsy-dex` extra, via `git+https` install from separate
   repositories). A repo-wide search found no `vendor/`, `third_party/`, or
   similar directory, and no embedded `LICENSE`/`COPYING` file anywhere under
   `src/` — the two reliable signs of vendored third-party source. Every
   third-party package lives in a virtualenv's `site-packages`, never inside
   this repository's `src/` tree or its git history.

2. **The three strong-copyleft packages present are all lint/dev tooling,
   never installed as part of the shipped package.** `pylint`,
   `pylint-plugin-utils` (GPL-2.0-or-later) and `pylint-pydantic` (GPLv3) are
   declared only in `requirements/dev.txt` and `requirements/tests.txt`, not
   in `requirements/base.txt` (the file that defines what actually ships with
   `gsy-e`, per `setup.py`'s `REQUIREMENTS`). They run as external CLI
   processes over the source during linting/CI and are never `import`ed by
   any `gsy_e` module. See `tools/LICENSE_EXCEPTIONS.md` for the full
   per-package reasoning.

3. **The one strong-copyleft *label* on a runtime dependency is a
   metadata artifact, not a real dual license.** `text-unidecode` (a
   transitive runtime dependency of `python-slugify`, in `base.txt`) is
   reported by `pip-licenses`' default mode as "Artistic License; GNU
   General Public License (GPL); GNU General Public License v2 or later
   (GPLv2+)" because that tool concatenates *all* PyPI trove classifiers.
   Its actual package metadata `License` field — the authoritative,
   package-author-declared value — is `Artistic License` only
   (`pip-licenses --from=meta` confirms this). Artistic License is
   permissive, not copyleft.

4. **Every other copyleft hit is weak/file-level (LGPL, MPL), not strong.**
   `psycopg2`/`psycopg2-binary`, `chardet` (LGPL) and `certifi` (MPL) are
   runtime dependencies (`base.txt`); `astroid`, `paramiko` (LGPL) and
   `hypothesis` (MPL) are dev/test-only. Weak copyleft's obligations attach
   only to modifications of the library itself, not to code that merely
   imports/links it, so these do not implicate this repository's own source
   either way.

## Conclusion

On the evidence of this scan, no strong-copyleft component reaches this
repository's source control — nothing GPL/AGPL/SSPL-licensed is vendored,
committed, or otherwise part of the `gsy-e` git tree. The three strong-copyleft
packages that do appear (`pylint`, `pylint-plugin-utils`, `pylint-pydantic`)
are external dev/lint tools only, declared exclusively in
`requirements/dev.txt`/`tests.txt`, and are not installed with, linked into,
or shipped alongside the `gsy-e` product.
