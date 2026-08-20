//! Fail-closed HMAC JWT codec for first-party service tokens.

use base64::Engine as _;
use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use hmac::{Hmac, Mac};
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value, json};
use sha2::{Sha256, Sha384, Sha512};
use uuid::Uuid;

use crate::SecurityError;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub enum HmacJwtAlgorithm {
    HS256,
    HS384,
    HS512,
}

impl HmacJwtAlgorithm {
    const fn name(self) -> &'static str {
        match self {
            Self::HS256 => "HS256",
            Self::HS384 => "HS384",
            Self::HS512 => "HS512",
        }
    }
}

#[derive(Clone, Debug)]
pub struct HmacJwtCodec {
    key: Vec<u8>,
    algorithm: HmacJwtAlgorithm,
    issuer: String,
    audience: String,
    lifetime_seconds: u64,
}

impl HmacJwtCodec {
    #[must_use]
    pub const fn lifetime_seconds(&self) -> u64 {
        self.lifetime_seconds
    }

    pub fn new(
        key: impl AsRef<[u8]>,
        algorithm: HmacJwtAlgorithm,
        issuer: impl Into<String>,
        audience: impl Into<String>,
        lifetime_seconds: u64,
    ) -> Result<Self, SecurityError> {
        let key = key.as_ref().to_vec();
        let issuer = issuer.into();
        let audience = audience.into();
        if key.len() < 32 || issuer.trim().is_empty() || audience.trim().is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "HMAC JWT requires at least 256 bits of key material, issuer, and audience".into(),
            ));
        }
        if lifetime_seconds == 0 {
            return Err(SecurityError::InvalidConfiguration(
                "HMAC JWT lifetime must be greater than zero".into(),
            ));
        }
        Ok(Self {
            key,
            algorithm,
            issuer,
            audience,
            lifetime_seconds,
        })
    }

    pub fn issue(
        &self,
        mut claims: Map<String, Value>,
        now_seconds: u64,
    ) -> Result<String, SecurityError> {
        let expires = now_seconds
            .checked_add(self.lifetime_seconds)
            .ok_or_else(|| SecurityError::InvalidConfiguration("JWT expiration overflow".into()))?;
        for reserved in ["alg", "iss", "aud", "iat", "nbf", "exp", "jti"] {
            if claims.contains_key(reserved) {
                return Err(SecurityError::InvalidConfiguration(format!(
                    "caller cannot override reserved JWT claim {reserved}"
                )));
            }
        }
        claims.insert("iss".into(), Value::String(self.issuer.clone()));
        claims.insert("aud".into(), Value::String(self.audience.clone()));
        claims.insert("iat".into(), Value::from(now_seconds));
        claims.insert("nbf".into(), Value::from(now_seconds));
        claims.insert("exp".into(), Value::from(expires));
        claims.insert("jti".into(), Value::String(Uuid::new_v4().to_string()));
        let encoded_header = encode_json(&json!({
            "alg": self.algorithm.name(),
            "typ": "JWT"
        }))?;
        let encoded_claims = encode_json(&Value::Object(claims))?;
        let signing_input = format!("{encoded_header}.{encoded_claims}");
        let signature = self.sign(signing_input.as_bytes())?;
        Ok(format!(
            "{signing_input}.{}",
            URL_SAFE_NO_PAD.encode(signature)
        ))
    }

    pub fn verify(
        &self,
        token: &str,
        now_seconds: u64,
    ) -> Result<Map<String, Value>, SecurityError> {
        let mut segments = token.split('.');
        let header_segment = segments.next().unwrap_or_default();
        let claims_segment = segments.next().unwrap_or_default();
        let signature_segment = segments.next().unwrap_or_default();
        if header_segment.is_empty()
            || claims_segment.is_empty()
            || signature_segment.is_empty()
            || segments.next().is_some()
        {
            return Err(SecurityError::Unauthorized(
                "JWT must contain exactly three non-empty segments".into(),
            ));
        }
        let header = decode_json(header_segment)?;
        if header.get("typ").and_then(Value::as_str) != Some("JWT")
            || header.get("alg").and_then(Value::as_str) != Some(self.algorithm.name())
        {
            return Err(SecurityError::Unauthorized(
                "JWT type or algorithm is not allowed".into(),
            ));
        }
        let signature = URL_SAFE_NO_PAD
            .decode(signature_segment)
            .map_err(|_| SecurityError::Unauthorized("JWT signature encoding is invalid".into()))?;
        self.verify_signature(
            format!("{header_segment}.{claims_segment}").as_bytes(),
            &signature,
        )?;
        let claims = decode_json(claims_segment)?
            .as_object()
            .cloned()
            .ok_or_else(|| SecurityError::Unauthorized("JWT claims must be an object".into()))?;
        if claims.get("iss").and_then(Value::as_str) != Some(self.issuer.as_str())
            || !audience_matches(claims.get("aud"), &self.audience)
        {
            return Err(SecurityError::Unauthorized(
                "JWT issuer or audience is invalid".into(),
            ));
        }
        let issued_at = integer_claim(&claims, "iat")?;
        let not_before = integer_claim(&claims, "nbf")?;
        let expires = integer_claim(&claims, "exp")?;
        if issued_at > now_seconds || not_before > now_seconds || expires <= now_seconds {
            return Err(SecurityError::Unauthorized(
                "JWT is not currently valid".into(),
            ));
        }
        if claims
            .get("jti")
            .and_then(Value::as_str)
            .is_none_or(str::is_empty)
        {
            return Err(SecurityError::Unauthorized("JWT jti is required".into()));
        }
        Ok(claims)
    }

    fn sign(&self, input: &[u8]) -> Result<Vec<u8>, SecurityError> {
        macro_rules! sign {
            ($digest:ty) => {{
                let mut mac = Hmac::<$digest>::new_from_slice(&self.key)
                    .map_err(|_| SecurityError::InvalidConfiguration("invalid HMAC key".into()))?;
                mac.update(input);
                Ok(mac.finalize().into_bytes().to_vec())
            }};
        }
        match self.algorithm {
            HmacJwtAlgorithm::HS256 => sign!(Sha256),
            HmacJwtAlgorithm::HS384 => sign!(Sha384),
            HmacJwtAlgorithm::HS512 => sign!(Sha512),
        }
    }

    fn verify_signature(&self, input: &[u8], signature: &[u8]) -> Result<(), SecurityError> {
        macro_rules! verify {
            ($digest:ty) => {{
                let mut mac = Hmac::<$digest>::new_from_slice(&self.key)
                    .map_err(|_| SecurityError::InvalidConfiguration("invalid HMAC key".into()))?;
                mac.update(input);
                mac.verify_slice(signature)
                    .map_err(|_| SecurityError::Unauthorized("JWT signature is invalid".into()))
            }};
        }
        match self.algorithm {
            HmacJwtAlgorithm::HS256 => verify!(Sha256),
            HmacJwtAlgorithm::HS384 => verify!(Sha384),
            HmacJwtAlgorithm::HS512 => verify!(Sha512),
        }
    }
}

fn encode_json(value: &Value) -> Result<String, SecurityError> {
    serde_json::to_vec(value)
        .map(|bytes| URL_SAFE_NO_PAD.encode(bytes))
        .map_err(|_| SecurityError::InvalidConfiguration("JWT JSON encoding failed".into()))
}

fn decode_json(segment: &str) -> Result<Value, SecurityError> {
    let bytes = URL_SAFE_NO_PAD
        .decode(segment)
        .map_err(|_| SecurityError::Unauthorized("JWT segment encoding is invalid".into()))?;
    serde_json::from_slice(&bytes)
        .map_err(|_| SecurityError::Unauthorized("JWT segment JSON is invalid".into()))
}

fn integer_claim(claims: &Map<String, Value>, name: &str) -> Result<u64, SecurityError> {
    claims.get(name).and_then(Value::as_u64).ok_or_else(|| {
        SecurityError::Unauthorized(format!("JWT {name} claim is missing or invalid"))
    })
}

fn audience_matches(value: Option<&Value>, expected: &str) -> bool {
    value.is_some_and(|value| {
        value.as_str() == Some(expected)
            || value
                .as_array()
                .is_some_and(|values| values.iter().any(|value| value.as_str() == Some(expected)))
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hmac_jwt_round_trip_expiry_and_tampering_fail_closed() {
        for algorithm in [
            HmacJwtAlgorithm::HS256,
            HmacJwtAlgorithm::HS384,
            HmacJwtAlgorithm::HS512,
        ] {
            let codec = HmacJwtCodec::new(
                b"0123456789abcdef0123456789abcdef",
                algorithm,
                "issuer",
                "audience",
                60,
            )
            .expect("codec");
            let token = codec
                .issue(
                    Map::from_iter([("sub".into(), Value::String("user-1".into()))]),
                    100,
                )
                .expect("issue");
            assert_eq!(codec.verify(&token, 101).expect("verify")["sub"], "user-1");
            assert!(codec.verify(&token, 160).is_err());
            let mut tampered = token.into_bytes();
            let index = tampered.len() - 1;
            tampered[index] = if tampered[index] == b'A' { b'B' } else { b'A' };
            assert!(
                codec
                    .verify(&String::from_utf8(tampered).expect("UTF-8"), 101)
                    .is_err()
            );
        }
    }
}
