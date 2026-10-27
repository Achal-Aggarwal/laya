#!/usr/bin/env python3
"""Fail a JUnit XML test report in which any test skipped, failed, or went missing.

A lane that exits 0 having skipped its tests proves nothing, and GoogleTest and CTest both treat a
skip as success. This reads the report (GoogleTest `--gtest_output=xml:` or `ctest --output-junit`)
and counts instead of trusting the exit status.

    ctest --test-dir build/debug --output-junit junit.xml
    python laya-cpp/scripts/check_test_xml.py junit.xml --min-tests 2

Exit 0 only when no test skipped, none failed or errored, and at least --min-tests ran. A disabled
test (`status="notrun"`) counts as skipped. Several report files may be given; counts add up.
"""
import argparse
import os
import sys
# XXE and entity bombs need a DTD, and summarise() refuses any report that has one, so the stdlib
# parser is safe here and the checker keeps to the standard library.
import xml.etree.ElementTree as ET  # nosemgrep: use-defused-xml


def summarise(path):
    """(tests, problems) for one report file. Raises ValueError on a malformed report."""
    try:
        with open(path, "rb") as handle:
            data = handle.read()
        if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
            raise ValueError("%s: a DTD is not allowed in a test report" % path)
        root = ET.fromstring(data)
    except (ET.ParseError, OSError) as err:
        raise ValueError("%s is not a readable XML report: %s" % (path, err))
    if root.tag not in ("testsuites", "testsuite"):
        raise ValueError("%s: unexpected root element <%s>" % (path, root.tag))
    tests, problems = 0, []
    for case in root.iter("testcase"):
        tests += 1
        name = "%s.%s" % (case.get("classname") or "", case.get("name") or "?")
        children = {child.tag for child in case}
        if "skipped" in children or case.get("status") == "notrun":
            problems.append("skipped: " + name)
        if "failure" in children or "error" in children or case.get("status") == "fail":
            problems.append("failed: " + name)
    return tests, problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("reports", nargs="+", help="JUnit XML report file(s)")
    parser.add_argument("--min-tests", type=int, default=1,
                        help="fail when fewer tests than this ran")
    args = parser.parse_args(argv)
    total, problems = 0, []
    for path in args.reports:
        if not os.path.isfile(path):
            print("check_test_xml: %s does not exist: the step that writes it did not run or "
                  "failed before producing it" % path, file=sys.stderr)
            return 1
        try:
            tests, found = summarise(path)
        except ValueError as err:
            print("check_test_xml: %s" % err, file=sys.stderr)
            return 1
        total += tests
        problems += found
    if total < args.min_tests:
        problems.append("only %d tests ran, floor is %d" % (total, args.min_tests))
    for problem in problems:
        print("check_test_xml: " + problem, file=sys.stderr)
    print("check_test_xml: %d tests, %d problems" % (total, len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
