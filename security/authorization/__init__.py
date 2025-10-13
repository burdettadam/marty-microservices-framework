"""
Authorization Module

This module provides authorization management and policy evaluation for the security framework.
"""

from .manager import AuthorizationManager, PolicyEngine

__all__ = ["AuthorizationManager", "PolicyEngine"]
