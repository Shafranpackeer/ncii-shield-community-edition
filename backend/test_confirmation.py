#!/usr/bin/env python
"""Run confirmation module tests."""

import subprocess
import sys

def main():
    """Run all confirmation module tests."""
    print("Running confirmation module tests...")
    print("=" * 60)

    # Run unit tests
    print("\n1. Running unit tests...")
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "tests/unit/confirmation/",
        "-v",
        "--tb=short"
    ])

    if result.returncode != 0:
        print("\n❌ Unit tests failed!")
        return 1

    print("\n✅ Unit tests passed!")

    # Run integration tests
    print("\n2. Running integration tests...")
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "tests/integration/test_confirmation.py",
        "-v",
        "--tb=short"
    ])

    if result.returncode != 0:
        print("\n❌ Integration tests failed!")
        return 1

    print("\n✅ Integration tests passed!")

    # Run coverage report
    print("\n3. Generating coverage report...")
    subprocess.run([
        sys.executable, "-m", "pytest",
        "tests/unit/confirmation/",
        "tests/integration/test_confirmation.py",
        "--cov=app.confirmation",
        "--cov-report=term-missing"
    ])

    print("\n🎉 All confirmation module tests passed!")
    return 0

if __name__ == "__main__":
    sys.exit(main())