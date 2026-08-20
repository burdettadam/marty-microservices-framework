"""
Core Security Module

This module provides the core security infrastructure for the MMF framework.
It follows hexagonal architecture with clear separation of domain, ports, and adapters.

Key components:
- ports/: Interface definitions (IKMSProvider, IAuthKeyStore, etc.)
- domain/: Security domain models and logic

Session management, request security coordination, and ECDH session-key
establishment are implemented by the canonical ``mmf-security`` Rust crate.

Key ID Namespacing:
- auth:* - Authentication keys (MMF infrastructure)
- cred:* - Credential keys (application layer)
"""
