#!/usr/bin/env python3
"""Test GEPrep, then build the release zip.

    python build.py                run every test, then build dist/geprep-<version>.zip
    python build.py --tests-only   run the tests, build nothing
    python build.py --skip-blender plain tests only (the zip is still built, with a warning)
    python build.py --headless     run Blender without a window (export.py and origin.py are skipped)
    python build.py --blender /path/to/blender

Nothing is built unless every test passes.

Blender runs with its own temporary settings folder (BLENDER_USER_* variables),
so your real Blender config and installed add-ons are never read or changed.
Each Blender test gets a fresh Blender process.
"""
import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ADDON = ROOT / "geprep"
TESTS = ROOT / "tests"
DIST = ROOT / "dist"

SKIP_DIRS = {"__pycache__", ".git", ".ruff_cache", ".pytest_cache", ".mypy_cache"}
SKIP_SUFFIXES = {".pyc", ".pyo"}
SKIP_NAMES = {".DS_Store", "Thumbs.db"}
BLENDER_FALLBACKS = ("/usr/bin/blender", "/usr/local/bin/blender", "/opt/blender/blender")


def step(title):
    print(f"\n=== {title} ===")


def fail(message):
    print(f"\nBUILD STOPPED: {message}")
    sys.exit(1)


def addon_version():
    """Read bl_info['version'] without importing the add-on."""
    tree = ast.parse((ADDON / "__init__.py").read_text(encoding="utf-8"))

    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "bl_info":
            info = ast.literal_eval(node.value)
            return ".".join(str(part) for part in info["version"])

    fail("bl_info not found in geprep/__init__.py")


def copy_addon(destination):
    """Copy the add-on without caches, so tests and the zip see the same files."""
    def ignore(directory, names):
        return [
            name for name in names
            if name in SKIP_DIRS or name in SKIP_NAMES or Path(name).suffix in SKIP_SUFFIXES
        ]

    shutil.copytree(ADDON, destination, ignore=ignore)


# ------------------------------------------------------------ plain tests
def run_plain_tests():
    step("Plain Python tests")
    runner = TESTS / "plain" / "_run_all.py"

    if not runner.exists():
        fail(f"{runner} is missing")

    if subprocess.run([sys.executable, str(runner)]).returncode:
        fail("plain tests failed")


# ----------------------------------------------------------- Blender tests
def find_blender(given):
    candidates = [given, os.environ.get("BLENDER"), shutil.which("blender"), *BLENDER_FALLBACKS]

    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate

    return None


def run_blender_tests(blender, headless, timeout):
    step("Blender tests" + (" (headless)" if headless else ""))
    tests = sorted(path for path in (TESTS / "blender").glob("*.py") if not path.name.startswith("_"))
    runner = TESTS / "blender" / "_run_in_blender.py"

    if not tests or not runner.exists():
        fail("no Blender tests found in tests/blender")

    work = Path(tempfile.mkdtemp(prefix="geprep-blender-"))
    addon_copy = work / "scripts" / "addons" / "geprep"
    copy_addon(addon_copy)

    env = os.environ.copy()
    env.update({
        "BLENDER_USER_SCRIPTS": str(work / "scripts"),
        "BLENDER_USER_CONFIG": str(work / "config"),
        "BLENDER_USER_DATAFILES": str(work / "datafiles"),
        "BLENDER_USER_EXTENSIONS": str(work / "extensions"),
        "GEPREP_ADDON": str(addon_copy),
    })

    results = []

    try:
        for test in tests:
            result_file = work / f"{test.stem}.json"
            env["GEPREP_RESULT"] = str(result_file)
            command = [blender]

            if headless:
                command.append("--background")

            command += ["--python", str(runner), "--", str(test)]
            print(f"\n--- {test.name}")
            started = time.time()

            try:
                process = subprocess.run(command, env=env, timeout=timeout,
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         text=True)
                log = process.stdout
            except subprocess.TimeoutExpired as error:
                log = (error.stdout or b"")
                log = log.decode(errors="replace") if isinstance(log, bytes) else log
                results.append((test.name, "failed", 0, f"Timed out after {timeout} s"))
                print(log[-1500:])
                continue

            if result_file.exists():
                data = json.loads(result_file.read_text(encoding="utf-8"))
                status, passes, error = data["status"], data["passes"], data["error"]
            else:
                status, passes = "failed", 0
                error = f"Blender ended without a result (exit code {process.returncode})"

            if status != "passed":
                print(log[-2500:])

            results.append((test.name, status, passes, error))
            print(f"    {status.upper()} in {time.time() - started:.1f} s")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print()

    for name, status, passes, error in results:
        detail = f"{passes} checks" if status == "passed" else error.strip().splitlines()[-1] if error.strip() else ""
        print(f"{status:8} {name}  {detail}")

    if any(status == "failed" for _, status, _, _ in results):
        fail("Blender tests failed")

    skipped = [name for name, status, _, _ in results if status == "skipped"]

    if skipped:
        print(f"\nWARNING: not run (need a window): {', '.join(skipped)}")


# ------------------------------------------------------------------ build
def git_dirty():
    try:
        out = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True)
        return bool(out.stdout.strip()) if out.returncode == 0 else False
    except FileNotFoundError:
        return False


def build_zip():
    step("Build")
    version = addon_version()
    DIST.mkdir(exist_ok=True)
    target = DIST / f"geprep-{version}.zip"

    if git_dirty():
        print("WARNING: there are uncommitted changes, so this zip is not an exact commit")

    stage = Path(tempfile.mkdtemp(prefix="geprep-build-"))

    try:
        copy_addon(stage / "geprep")
        target.unlink(missing_ok=True)

        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted((stage / "geprep").rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(stage).as_posix())
    finally:
        shutil.rmtree(stage, ignore_errors=True)

    with zipfile.ZipFile(target) as archive:
        names = archive.namelist()

    if "geprep/__init__.py" not in names or any(n.startswith("tests/") for n in names):
        fail("the zip does not look right")

    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    print(f"Built {target.relative_to(ROOT)}  ({target.stat().st_size / 1024:.0f} KB, {len(names)} files)")
    print(f"sha256 {digest}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tests-only", action="store_true", help="run the tests, build nothing")
    parser.add_argument("--skip-blender", action="store_true", help="skip the Blender tests")
    parser.add_argument("--headless", action="store_true", help="no Blender window (export.py and origin.py are skipped)")
    parser.add_argument("--blender", help="path to the Blender executable")
    parser.add_argument("--timeout", type=int, default=240, help="seconds allowed per Blender test")
    args = parser.parse_args()

    print(f"GEPrep {addon_version()}")
    run_plain_tests()

    if args.skip_blender:
        print("\nWARNING: Blender tests skipped")
    else:
        blender = find_blender(args.blender)

        if blender is None:
            fail("Blender not found. Use --blender PATH, set BLENDER, or --skip-blender")

        print(f"\nUsing {blender}")
        run_blender_tests(blender, args.headless, args.timeout)

    if args.tests_only:
        print("\nAll tests passed. Nothing built (--tests-only)")
        return

    build_zip()


if __name__ == "__main__":
    main()
