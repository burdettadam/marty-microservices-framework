//! Canonical session state and event vocabulary shared by session modules.

use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SessionState {
    Active,
    Expired,
    Invalidated,
    Terminated,
    Suspended,
    Invalid,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SessionEventType {
    SessionCreated,
    SessionAccessed,
    SessionExtended,
    SessionExpired,
    SessionInvalidated,
    SessionTerminated,
    SessionRotated,
    IpAddressChanged,
    UserAgentChanged,
    ConcurrentSessionDetected,
    SuspiciousActivity,
    AuthenticationSuccess,
    AuthenticationFailure,
    MfaCompleted,
    PrivilegeEscalation,
    RoleChanged,
    SessionDataUpdated,
    SessionDataCleared,
    AdminSessionView,
    AdminSessionTerminate,
    SessionCleanup,
    Logout,
    Timeout,
    SecurityViolation,
    AdminTermination,
    PasswordChange,
}
