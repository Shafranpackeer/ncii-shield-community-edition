#!/usr/bin/env python
"""Script to create initial migration with all tables and triggers"""

import subprocess
import sys
import time

def main():
    # First, generate the migration with autogenerate
    print("Generating initial migration...")
    result = subprocess.run(
        ["alembic", "revision", "--autogenerate", "-m", "Initial schema with all tables"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"Error generating migration: {result.stderr}")
        sys.exit(1)

    print(result.stdout)
    print("\nMigration generated successfully!")

if __name__ == "__main__":
    main()