# Archived Discovery Compatibility Shim

This file contains the archived discovery.py compatibility shim that was removed as part of the high-impact improvements to point linting and documentation to real entry points.

## Why it was archived:

1. **Re-export only**: The file only re-exported components from decomposed modules
2. **Confusing for users**: Linting and docs pointed to the shim instead of real entry points
3. **Testing improvements**: Per tests/TESTING_IMPROVEMENTS_PLAN.md:28, this was planned for removal

## Migration completed:

All imports have been updated to point directly to the decomposed modules:

- `from framework.discovery.discovery import` → `from framework.discovery.clients import`, `from framework.discovery.config import`, etc.
- Updated test files to import from the proper module locations
- Removed the re-export shim so linting and docs point to real entry points

The decomposed structure is now:
- `framework.discovery.cache` - Caching functionality
- `framework.discovery.clients` - Discovery client implementations
- `framework.discovery.config` - Configuration classes
- `framework.discovery.factory` - Factory functions
- `framework.discovery.results` - Result classes

## Date archived:
October 11, 2025
