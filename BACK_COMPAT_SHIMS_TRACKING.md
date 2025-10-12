# Back-Compatibility Shims Tracking Document

This document tracks the backward compatibility shim files that duplicate the public API from decomposed packages. These shims are maintained to allow existing code to continue working while encouraging migration to the new package structure.

## Overview

During the framework decomposition process, several large monolithic modules were broken down into smaller, focused packages. To maintain backward compatibility, the original files were converted into "shims" that re-export all functionality from the new decomposed structure.

## Identified Back-Compat Shims

### 1. External Connectors Shim
- **File**: `src/framework/integration/external_connectors.py`
- **Target Package**: `src/framework/integration/external_connectors/` (package)
- **Status**: ✅ Has deprecation warnings
- **Line Count**: ~60 lines (shim only)
- **Original Size**: 1388 lines (before decomposition)
- **Legacy Import Usage**:
  - ❌ No files currently importing from the shim directly
  - ✅ All usage has been migrated to the package structure

### 2. Deployment Strategies Shim
- **File**: `src/framework/deployment/strategies.py`
- **Target Package**: `src/framework/deployment/strategies/` (package)
- **Status**: ✅ Has deprecation warnings (added during this analysis)
- **Line Count**: ~82 lines (shim only)
- **Original Size**: 1510 lines (before decomposition)
- **Legacy Import Usage**:
  - ❌ **2 test files still importing from shim**:
    - `tests/unit/framework/test_deployment_strategies.py`
    - `tests/unit/framework/test_deployment_strategies_simple.py`

## Import Usage Analysis

### Files Still Using Shims

#### Deployment Strategies Shim Users
1. **File**: `tests/unit/framework/test_deployment_strategies.py`
   - **Import**: `from src.framework.deployment.strategies import DeploymentStrategy`
   - **Import**: `from src.framework.deployment.strategies import (DeploymentOrchestrator, ...)`
   - **Action Required**: Update to import from `src.framework.deployment.strategies` package

2. **File**: `tests/unit/framework/test_deployment_strategies_simple.py`
   - **Multiple imports**: Various `DeploymentStrategy`, `DeploymentPhase`, `DeploymentStatus` imports
   - **Action Required**: Update to import from `src.framework.deployment.strategies` package

#### External Connectors Shim Users
- ✅ **No current usage found** - All consumers have been successfully migrated

## Migration Progress

### External Connectors Migration
- **Status**: ✅ **COMPLETE**
- **Migration Rate**: 100% (0/0 files using shim)
- **Ready for Removal**: ✅ Yes, pending final verification

### Deployment Strategies Migration
- **Status**: 🟡 **IN PROGRESS**
- **Migration Rate**: ~95% (2 test files remaining)
- **Ready for Removal**: ❌ No, test files need updating

## Shim Removal Timeline

### Phase 1: Immediate Actions (Completed)
- ✅ Add deprecation warnings to all shims
- ✅ Document all existing shims and their usage
- ✅ Identify files still using shims

### Phase 2: Consumer Migration (In Progress)
- 🟡 Update remaining test files to use new package imports
- 🟡 Verify no external consumers depend on shim files
- 🟡 Create migration script for automated import updates

### Phase 3: Shim Removal (Future)
- ⏳ Remove `src/framework/integration/external_connectors.py` (ready when verified)
- ⏳ Remove `src/framework/deployment/strategies.py` (after test file updates)
- ⏳ Update documentation to remove old import examples

## Recommended Actions

### Immediate (Next Release)
1. **Update test files** to use new package imports instead of shims
2. **Verify no external projects** depend on the shim files
3. **Create automated migration script** to help external consumers

### Medium Term (1-2 releases)
1. **Remove external_connectors.py shim** (appears ready for removal)
2. **Remove strategies.py shim** (after test file updates)
3. **Document the removal** in release notes with migration examples

### Long Term (Future Decompositions)
1. **Apply same pattern** to other large modules being decomposed
2. **Standardize shim lifecycle** process for future decompositions
3. **Create tooling** to automatically detect shim usage

## Migration Script

A migration script should be created to automatically update import statements:

```python
# Example transformations:
# FROM: from src.framework.deployment.strategies import DeploymentStrategy
# TO:   from src.framework.deployment.strategies import DeploymentStrategy

# FROM: from src.framework.integration.external_connectors import ConnectorType
# TO:   from src.framework.integration.external_connectors import ConnectorType
```

## Notes

- The shims serve an important purpose during the transition period
- Deprecation warnings help guide consumers to migrate
- Complete removal should only happen after verifying no external dependencies
- Consider keeping shims for one major version after migration completion

## Last Updated
- **Date**: October 11, 2025
- **By**: Analysis of back-compat shim removal request
- **Next Review**: After test file migrations are complete
