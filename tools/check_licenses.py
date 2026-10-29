#!/usr/bin/env python
"""Fail if any installed dependency is under a strong copyleft license.

Runs `pip-licenses` against the current Python environment and classifies
each dependency's license. Strong copyleft licenses (GPL, AGPL, SSPL, ...)
require derivative/linked works to be released under the same license and
are not compatible with this project's distribution model, so the script
exits non-zero if any are found. Permissive licenses (MIT, BSD, Apache, ...)
and weak/"file-level" copyleft licenses (LGPL, MPL, EPL) are allowed.

Packages with license metadata that can't be classified (e.g. "UNKNOWN")
are printed as warnings for manual review but do not fail the build, since
that usually reflects missing/incomplete PyPI metadata rather than an
actual copyleft license.

Known false positives can be silenced via an exceptions file (one package
name per line, '#' comments allowed) after manual review of the package's
actual license, see --exceptions. Every entry in the default exceptions
file (license_exceptions.txt) is documented in LICENSE_EXCEPTIONS.md.

Requires the `pip-licenses` package (`pip install pip-licenses`).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

DEFAULT_EXCEPTIONS_FILE = Path(__file__).parent / "license_exceptions.txt"

# Substrings are matched case-insensitively against the license string(s)
# reported by pip-licenses. Order matters: weak copyleft is checked first
# so that e.g. "LGPL" is not misclassified as strong "GPL" copyleft.
WEAK_COPYLEFT_MARKERS = (
    "LGPL",
    "LESSER GENERAL PUBLIC",
    "MPL",
    "MOZILLA PUBLIC",
    "EPL",
    "ECLIPSE PUBLIC",
)

STRONG_COPYLEFT_MARKERS = (
    "GPL",  # also matches AGPL / GNU GENERAL PUBLIC LICENSE
    "GENERAL PUBLIC LICENSE",
    "SSPL",
    "SERVER SIDE PUBLIC LICENSE",
    "OSL",
    "OPEN SOFTWARE LICENSE",
    "EUPL",
    "EUROPEAN UNION PUBLIC LICENCE",
    "CECILL",
    "RECIPROCAL PUBLIC LICENSE",
    "CPAL",
    "COMMON PUBLIC ATTRIBUTION",
    "SLEEPYCAT",
    "Q PUBLIC LICENSE",
)

UNKNOWN_MARKERS = ("UNKNOWN", "")


def classify_license(license_str):
    """Classify a license string as 'weak-copyleft', 'strong-copyleft',
    'unknown' or 'other' (permissive/unrestricted)."""
    text = license_str.strip().upper()
    if text in UNKNOWN_MARKERS:
        return "unknown"
    if any(marker in text for marker in WEAK_COPYLEFT_MARKERS):
        return "weak-copyleft"
    if any(marker in text for marker in STRONG_COPYLEFT_MARKERS):
        return "strong-copyleft"
    return "other"


def _run_pip_licenses():
    try:
        output = subprocess.run(
            ["pip-licenses", "--format=json", "--with-system"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except FileNotFoundError as ex:
        raise SystemExit(
            "pip-licenses is not installed. Install it with `pip install pip-licenses`."
        ) from ex
    except subprocess.CalledProcessError as ex:
        raise SystemExit(f"pip-licenses failed:\n{ex.stderr}") from ex
    return json.loads(output)


def _load_exceptions(exceptions_file):
    if not exceptions_file.exists():
        return set()
    lines = exceptions_file.read_text().splitlines()
    return {
        line.strip().lower() for line in lines if line.strip() and not line.strip().startswith("#")
    }


def main():
    """Main method for the scan"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exceptions",
        type=Path,
        default=DEFAULT_EXCEPTIONS_FILE,
        help="Path to a file listing package names to exclude from the check "
        "(one per line, after manual license review).",
    )
    args = parser.parse_args()

    exceptions = _load_exceptions(args.exceptions)
    packages = _run_pip_licenses()

    strong_copyleft = []
    unknown = []
    exempted = []

    for package in packages:
        name = package["Name"]
        license_str = package["License"]
        if name.lower() in exceptions:
            exempted.append((name, license_str))
            continue
        classification = classify_license(license_str)
        if classification == "strong-copyleft":
            strong_copyleft.append((name, package["Version"], license_str))
        elif classification == "unknown":
            unknown.append((name, package["Version"]))

    if unknown:
        print(
            f"WARNING: {len(unknown)} package(s) with unresolved license metadata "
            "(please review manually):"
        )
        for name, version in sorted(unknown):
            print(f"  - {name}=={version}")
        print()

    if exempted:
        print(f"NOTE: {len(exempted)} package(s) exempted via {args.exceptions}:")
        for name, license_str in sorted(exempted):
            print(f"  - {name}: {license_str}")
        print()

    if strong_copyleft:
        print(f"FAIL: {len(strong_copyleft)} package(s) under a strong copyleft license:")
        for name, version, license_str in sorted(strong_copyleft):
            print(f"  - {name}=={version}: {license_str}")
        print(
            "\nIf a package is misclassified (e.g. dual-licensed under a permissive "
            f"license too), add it to {args.exceptions} after manual review."
        )
        return 1

    print(f"OK: no strong copyleft licenses found among {len(packages)} packages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
