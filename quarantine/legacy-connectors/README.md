# Archived External Connectors Original

This directory contains the archived pre-decomposition module `external_connectors_original.py` that was removed as part of the migration to the new decomposed package structure.

## Why it was archived:

1. **Size**: 1.3K lines monolithic file
2. **Undeclared dependencies**: Imported heavy opt-in libs like `pyodbc` that weren't declared in `pyproject.toml`
3. **Duplication**: Largely duplicated the new decomposed package structure
4. **Risk**: Keeping it around risked import errors and confused users

## Migration completed:

All components have been successfully migrated to the new decomposed package structure in `src/framework/integration/external_connectors/`:

- DatabaseConnector → `connectors/database.py`
- FileSystemConnector → `connectors/filesystem.py`
- ExternalSystemManager → `connectors/manager.py`
- create_external_integration_platform → `connectors/manager.py`

The main `external_connectors.py` file now serves as a compatibility shim that imports everything from the decomposed package.

## Date archived:
October 11, 2025
