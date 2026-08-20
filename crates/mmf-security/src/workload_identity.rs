//! Fail-closed workload identity authorization shared by MMF gRPC servers.

use std::collections::{BTreeMap, BTreeSet};

use serde::{Deserialize, Serialize};

use crate::SecurityError;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum WorkloadAuthorizationDecision {
    Allow,
    Unauthenticated,
    Forbidden,
}

#[derive(Clone, Debug)]
pub struct WorkloadIdentityPolicy {
    allowed_identities_by_method: BTreeMap<String, BTreeSet<String>>,
}

impl WorkloadIdentityPolicy {
    pub fn new(
        allowed_identities_by_method: BTreeMap<String, BTreeSet<String>>,
    ) -> Result<Self, SecurityError> {
        if allowed_identities_by_method.is_empty()
            || allowed_identities_by_method
                .iter()
                .any(|(method, identities)| {
                    !valid_method(method)
                        || identities.is_empty()
                        || identities.iter().any(|identity| !valid_identity(identity))
                })
        {
            return Err(SecurityError::InvalidConfiguration(
                "workload authorization requires exact gRPC methods and SPIFFE URI identities"
                    .into(),
            ));
        }
        Ok(Self {
            allowed_identities_by_method,
        })
    }

    #[must_use]
    pub fn authorize<'a>(
        &self,
        method: &str,
        peer_identities: impl IntoIterator<Item = &'a str>,
    ) -> WorkloadAuthorizationDecision {
        let peer_identities = peer_identities.into_iter().collect::<BTreeSet<_>>();
        if peer_identities.is_empty() {
            return WorkloadAuthorizationDecision::Unauthenticated;
        }
        self.allowed_identities_by_method
            .get(method)
            .filter(|allowed| {
                peer_identities
                    .iter()
                    .any(|identity| allowed.contains(*identity))
            })
            .map_or(WorkloadAuthorizationDecision::Forbidden, |_| {
                WorkloadAuthorizationDecision::Allow
            })
    }
}

#[must_use]
pub fn constant_time_secret_eq(expected: &[u8], candidate: &[u8]) -> bool {
    let mut difference = expected.len() ^ candidate.len();
    let maximum = expected.len().max(candidate.len());
    for index in 0..maximum {
        difference |= usize::from(
            expected.get(index).copied().unwrap_or_default()
                ^ candidate.get(index).copied().unwrap_or_default(),
        );
    }
    difference == 0
}

fn valid_method(value: &str) -> bool {
    let mut segments = value.split('/');
    segments.next() == Some("")
        && segments.next().is_some_and(|value| !value.is_empty())
        && segments.next().is_some_and(|value| !value.is_empty())
        && segments.next().is_none()
}

fn valid_identity(value: &str) -> bool {
    value.starts_with("spiffe://")
        && value.len() <= 2_048
        && !value.chars().any(char::is_whitespace)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn policy() -> WorkloadIdentityPolicy {
        WorkloadIdentityPolicy::new(BTreeMap::from([(
            "/marty.test.v1.Verifier/Evaluate".into(),
            BTreeSet::from(["spiffe://marty.internal/service/flow".into()]),
        )]))
        .unwrap()
    }

    #[test]
    fn exact_authenticated_identity_is_required() {
        let policy = policy();
        assert_eq!(
            policy.authorize(
                "/marty.test.v1.Verifier/Evaluate",
                ["spiffe://marty.internal/service/flow"],
            ),
            WorkloadAuthorizationDecision::Allow
        );
        assert_eq!(
            policy.authorize("/marty.test.v1.Verifier/Evaluate", []),
            WorkloadAuthorizationDecision::Unauthenticated
        );
        assert_eq!(
            policy.authorize(
                "/marty.test.v1.Verifier/Evaluate",
                ["spiffe://marty.internal/service/notification"],
            ),
            WorkloadAuthorizationDecision::Forbidden
        );
        assert_eq!(
            policy.authorize(
                "/marty.test.v1.Verifier/Other",
                ["spiffe://marty.internal/service/flow"],
            ),
            WorkloadAuthorizationDecision::Forbidden
        );
    }

    #[test]
    fn malformed_policy_and_secret_comparisons_fail_closed() {
        assert!(WorkloadIdentityPolicy::new(BTreeMap::new()).is_err());
        assert!(
            WorkloadIdentityPolicy::new(BTreeMap::from([(
                "Evaluate".into(),
                BTreeSet::from(["bearer-token".into()]),
            )]))
            .is_err()
        );
        assert!(constant_time_secret_eq(b"same", b"same"));
        assert!(!constant_time_secret_eq(b"same", b"different"));
        assert!(!constant_time_secret_eq(b"same", b"samf"));
    }
}
