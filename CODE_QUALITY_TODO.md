# Code Quality Improvement TODO

This document tracks code quality issues that have been temporarily ignored in the ruff configuration to enable successful commits. These should be addressed in future iterations.

## Current Ignored Issues (as of 2025-10-09)

### 1. Line Length (E501) - 133 occurrences
- **Issue**: Lines exceeding 100 characters (configured line-length in ruff)
- **Priority**: Low
- **Action**: Review and refactor long lines, consider if 88 char limit (Black default) vs 100 char limit is appropriate
- **Files**: Widespread across the codebase

### 2. Exception Handling (B904) - 28 occurrences
- **Issue**: `raise` statements without `from` inside except blocks
- **Priority**: Medium
- **Action**: Add proper exception chaining using `raise ... from ...` syntax
- **Example**: `raise CustomError("message") from original_exception`
- **Benefits**: Better error traceability and debugging

### 3. Import Sorting (I001) - 18 occurrences
- **Issue**: Unsorted imports not following isort/ruff standards
- **Priority**: Low
- **Action**: Run `ruff --fix` to auto-fix import sorting
- **Note**: This conflicts with the separate isort pre-commit hook

### 4. Unused Imports (F401) - 15 occurrences
- **Issue**: Imported modules/functions that are not used
- **Priority**: Medium
- **Action**: Remove unused imports or add `# noqa: F401` if intentionally exposed
- **Benefits**: Cleaner code, reduced memory usage

### 5. Undefined Names (F821) - 13 occurrences
- **Issue**: Missing type annotations imports (remaining after bulk fix)
- **Priority**: High
- **Action**: Add missing imports from `typing` module or fix type annotations
- **Example**: Add `from typing import Dict, List` etc.

### 6. Deprecated Imports (UP035) - 5 occurrences
- **Issue**: Using deprecated typing imports (e.g., `typing.Dict` instead of `dict`)
- **Priority**: Medium
- **Action**: Update to modern Python 3.9+ native types
- **Example**: `Dict[str, int]` → `dict[str, int]`

### 7. Assert Exception Handling (B017) - 4 occurrences
- **Issue**: `assert` raises exception without proper handling
- **Priority**: Medium
- **Action**: Review assertions and improve exception handling patterns

### 8. Redefined Names (F811) - 1 occurrence
- **Issue**: Variable/function redefined while previous definition unused
- **Priority**: High
- **Action**: Remove duplicate definitions or rename appropriately

## Implementation Plan

### Phase 1: Critical Issues (High Priority)
1. Fix remaining F821 undefined names - complete typing imports
2. Resolve F811 redefined names
3. Address B904 exception chaining for better error handling

### Phase 2: Code Cleanliness (Medium Priority)
1. Remove unused imports (F401)
2. Update deprecated imports (UP035)
3. Fix assert exception handling (B017)

### Phase 3: Style Consistency (Low Priority)
1. Resolve import sorting conflicts between ruff and isort
2. Review and fix line length issues (E501)
3. Standardize line length configuration

## Configuration Notes

The current ruff configuration in `marty_chassis/pyproject.toml` has been updated to:
- Use the new `[tool.ruff.lint]` section format
- Ignore current issues temporarily with TODO comments
- Maintain development velocity while planning systematic improvements

## Monitoring Progress

To track progress on these issues:

```bash
# Check current status
uv run ruff check --statistics

# Fix auto-fixable issues
uv run ruff check --fix

# Check specific rule
uv run ruff check --select F821  # Example for undefined names
```

Last updated: 2025-10-09
