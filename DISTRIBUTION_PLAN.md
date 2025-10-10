# Marty Microservices Framework - Packaging and Distribution Plan

## Overview

This document outlines the plan for packaging the Marty Microservices Framework as a distributable pip package, allowing Marty and other projects to eliminate internal framework copies and use the framework as a proper dependency.

## Current Status ✅

The framework has been successfully enhanced with:

1. **Unified Service Launcher** - `marty runservice` command that eliminates custom startup code
2. **Standardized Configuration** - YAML-based service configuration
3. **Migration Templates** - Updated FastAPI service templates using framework patterns
4. **CLI Infrastructure** - Comprehensive CLI with project management and service execution
5. **Migration Guide** - Complete documentation for migrating existing services

## Distribution Goals

### Primary Objectives

1. **Eliminate Code Duplication**: Remove the need for projects to maintain internal copies of `marty-microservices-framework/`
2. **Centralized Updates**: Framework improvements benefit all services immediately
3. **Standardized Dependencies**: Consistent framework versions across all projects
4. **Simplified Deployment**: Services can specify framework version in requirements
5. **Developer Experience**: Easy installation and updates via pip

### Distribution Channels

#### 1. Private PyPI Repository (Recommended for Enterprise)
- Host on internal PyPI server (e.g., JFrog Artifactory, Azure Artifacts)
- Secure access control for enterprise packages
- Version management and release control

#### 2. GitHub Packages
- Use GitHub's package registry
- Integrate with existing GitHub workflows
- Private packages with access control

#### 3. Git Dependencies (Development/Testing)
- Direct pip installation from Git repository
- Useful for development and testing
- Branch and tag-based versioning

## Implementation Plan

### Phase 1: Package Preparation ✅

- [x] Fix pyproject.toml configuration
- [x] Ensure proper entry points for CLI
- [x] Python 3.9+ compatibility
- [x] Comprehensive dependency management
- [x] License and metadata setup

### Phase 2: CI/CD Pipeline Setup

#### GitHub Actions Workflow

```yaml
# .github/workflows/package-release.yml
name: Package and Release

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11, 3.12]

    steps:
    - uses: actions/checkout@v4
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e .[dev,test]

    - name: Run tests
      run: pytest tests/

    - name: Run linting
      run: |
        ruff check .
        mypy marty_cli/

  build:
    needs: test
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: 3.11

    - name: Install build dependencies
      run: |
        python -m pip install --upgrade pip
        pip install build twine

    - name: Build package
      run: python -m build

    - name: Check package
      run: twine check dist/*

    - name: Upload artifacts
      uses: actions/upload-artifact@v4
      with:
        name: dist
        path: dist/

  release:
    needs: build
    runs-on: ubuntu-latest
    if: startsWith(github.ref, 'refs/tags/')

    steps:
    - name: Download artifacts
      uses: actions/download-artifact@v4
      with:
        name: dist
        path: dist/

    - name: Publish to PyPI
      env:
        TWINE_USERNAME: __token__
        TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
      run: twine upload dist/*

    - name: Create GitHub Release
      uses: actions/create-release@v1
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      with:
        tag_name: ${{ github.ref }}
        release_name: Release ${{ github.ref }}
        draft: false
        prerelease: false
```

### Phase 3: Version Management Strategy

#### Semantic Versioning
- **Major (X.0.0)**: Breaking changes to CLI or service interfaces
- **Minor (1.X.0)**: New features, backward compatible
- **Patch (1.0.X)**: Bug fixes, security updates

#### Release Branches
- `main`: Development branch
- `release/vX.Y.Z`: Release preparation
- `hotfix/vX.Y.Z`: Critical fixes

#### Version Automation
```bash
# Scripts for version management
scripts/
├── bump-version.sh     # Automated version bumping
├── prepare-release.sh  # Release preparation
└── validate-package.sh # Package validation
```

### Phase 4: Migration Process for Existing Projects

#### For Marty Repository

1. **Update pyproject.toml/requirements.txt**:
   ```toml
   [project]
   dependencies = [
       "marty-microservices-framework>=1.0.0,<2.0.0",
       # ... other dependencies
   ]
   ```

2. **Remove internal framework copy**:
   ```bash
   rm -rf marty-microservices-framework/
   ```

3. **Update service configurations**:
   - Ensure all services have `config.yaml`
   - Update Dockerfiles to use `marty runservice`
   - Update deployment scripts

4. **Update CI/CD pipelines**:
   ```yaml
   # Update GitHub Actions
   - name: Install dependencies
     run: |
       pip install marty-microservices-framework
   ```

#### For Other Projects

1. **Add framework dependency**:
   ```bash
   pip install marty-microservices-framework
   ```

2. **Follow migration guide**:
   - Refactor main.py files
   - Add service configurations
   - Update deployment scripts

### Phase 5: Distribution Deployment

#### PyPI Deployment

1. **Register PyPI account** (if using public PyPI)
2. **Configure API tokens** in GitHub secrets
3. **Test deployment** on TestPyPI first
4. **Automated releases** via GitHub Actions

#### Private Repository Setup

1. **Choose private registry** (Artifactory, Azure Artifacts, etc.)
2. **Configure authentication**
3. **Update pip configuration** in projects
4. **Document access procedures**

## Installation Methods

### Standard Installation
```bash
pip install marty-microservices-framework
```

### Development Installation
```bash
pip install -e git+https://github.com/marty-framework/marty-microservices-framework.git@main
```

### Specific Version
```bash
pip install marty-microservices-framework==1.2.3
```

### With Optional Features
```bash
pip install marty-microservices-framework[dev,test,monitoring]
```

## Project Structure After Distribution

```
your-microservice-project/
├── pyproject.toml              # Framework as dependency
├── main.py                     # Simplified using framework
├── config.yaml                 # Service configuration
├── requirements.txt            # Or in pyproject.toml
└── src/
    └── your_service/
        ├── __init__.py
        ├── api.py
        ├── models.py
        └── services.py

# No more internal marty-microservices-framework/ copy!
```

## Benefits After Migration

### For Developers
- **Simplified setup**: No more framework git submodules
- **Consistent tooling**: Same CLI across all projects
- **Easy updates**: `pip install --upgrade marty-microservices-framework`
- **Better IDE support**: Framework as proper package dependency

### For Operations
- **Standardized deployments**: All services use same patterns
- **Version consistency**: Control framework versions centrally
- **Security updates**: Framework security patches applied everywhere
- **Monitoring**: Uniform observability across services

### For Architecture
- **Reduced coupling**: Services depend on stable framework interface
- **Better testing**: Framework can be mocked/stubbed in tests
- **Cleaner dependencies**: Explicit framework version requirements
- **Modular updates**: Framework and business logic evolve independently

## Migration Timeline

### Week 1: Package Preparation
- [x] Finalize pyproject.toml
- [x] Set up CI/CD pipeline
- [ ] Create release documentation
- [ ] Test package building

### Week 2: Initial Release
- [ ] Release v1.0.0 to TestPyPI
- [ ] Test installation in isolated environment
- [ ] Validate CLI functionality
- [ ] Create migration branch in Marty repository

### Week 3: Marty Migration
- [ ] Update Marty repository dependencies
- [ ] Remove internal framework copy
- [ ] Update all service configurations
- [ ] Test all services with packaged framework
- [ ] Update deployment scripts

### Week 4: Documentation and Rollout
- [ ] Update all documentation
- [ ] Create video tutorials for migration
- [ ] Notify teams about new patterns
- [ ] Monitor production deployments

## Success Metrics

1. **Code Duplication Elimination**: 0 internal framework copies
2. **Deployment Consistency**: All services use `marty runservice`
3. **Update Efficiency**: Framework updates applied in < 1 day
4. **Developer Satisfaction**: Improved development experience surveys
5. **Maintenance Reduction**: Less time spent on framework maintenance per project

## Risk Mitigation

### Dependency Management
- Pin framework versions in production
- Test framework updates in staging first
- Maintain compatibility matrix documentation

### Backward Compatibility
- Provide migration tools for breaking changes
- Maintain LTS versions for critical services
- Clear deprecation warnings and timelines

### Distribution Reliability
- Multiple distribution channels (PyPI + Git)
- Private package mirrors for critical deployments
- Automated health checks for package availability

## Conclusion

The distribution of the Marty Microservices Framework as a proper pip package represents a significant step toward eliminating code duplication and standardizing microservice development patterns. The unified service launcher (`marty runservice`) and standardized configuration approach will dramatically simplify service development and deployment while ensuring consistency across all projects.

The implementation has been designed with enterprise needs in mind, providing flexibility in distribution channels while maintaining security and control over framework versions. The migration process is designed to be incremental and low-risk, allowing teams to adopt the new patterns at their own pace while immediately benefiting from the improved developer experience.
