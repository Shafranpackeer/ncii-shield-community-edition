# Technical Debt

This document tracks known technical debt and areas for improvement in the NCII Shield project.

## Dependency Management

- **Audit all AI-generated dependency files against real registries before pinning.**
  - Issue: AI assistants may suggest packages that don't exist on npm/PyPI
  - Example: `blockhash-js@^0.3.0` was suggested but doesn't exist on npm
  - Solution: Always verify package existence and version availability before adding to dependency files
  - Impact: Build failures, missing lockfiles, dependency conflicts

## Test Infrastructure

- **Recovery integration tests have SQLAlchemy compatibility issues**
  - Issue: Tests use `.astext` which is PostgreSQL-specific and not compatible with SQLAlchemy 2.0
  - Fixed: Changed to `.as_string()` for JSON field queries
  - Issue: Enum values need to use proper Python enums, not strings
  - Fixed: Import and use CaseStatus.ACTIVE and TargetStatus.DISCOVERED
  - Remaining: JSON payload updates in tests may not persist properly due to SQLAlchemy change tracking

## Port Conflicts

- **Local development port conflicts documented**
  - PostgreSQL: Changed from 5432 → 5433
  - Backend API: Changed from 8000 → 8001
  - Frontend: Changed from 3000 → 3001
  - Note: Update any local tools/scripts that reference these ports

## Future Improvements

- [ ] Implement automated dependency verification in CI/CD pipeline
- [ ] Add pre-commit hooks to validate package.json and requirements.txt
- [ ] Create a script to audit all dependencies against their respective registries
- [ ] Fix Alembic migration to avoid duplicate enum creation
- [ ] Update tests to properly handle JSON field mutations in SQLAlchemy