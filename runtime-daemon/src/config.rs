use std::path::PathBuf;

use crate::security::lease::LeaseHmacKey;

const LEASE_HMAC_ENV: &str = "OMERTA_RUNTIME_LEASE_HMAC_KEY";
const LEASE_HMAC_FILE_ENV: &str = "OMERTA_RUNTIME_LEASE_HMAC_KEY_FILE";
const LEASE_MAX_TTL_ENV: &str = "OMERTA_RUNTIME_LEASE_MAX_TTL_SECONDS";
const LEGACY_LEASE_MAX_TTL_ENV: &str = "AION_RUNTIME_LEASE_MAX_TTL_SECONDS";
const LEASE_STATE_PATH_ENV: &str = "OMERTA_RUNTIME_LEASE_STATE_PATH";
const LEGACY_LEASE_STATE_PATH_ENV: &str = "AION_RUNTIME_LEASE_STATE_PATH";
const MAX_ENCODED_KEY_FILE_BYTES: usize = 256;

fn compatible_environment_value(
    canonical_name: &str,
    legacy_name: &str,
) -> anyhow::Result<Option<String>> {
    let canonical_value = std::env::var(canonical_name)
        .ok()
        .filter(|value| !value.is_empty());
    let legacy_value = std::env::var(legacy_name)
        .ok()
        .filter(|value| !value.is_empty());
    if let (Some(canonical), Some(legacy)) = (&canonical_value, &legacy_value) {
        if canonical != legacy {
            anyhow::bail!("{canonical_name} conflicts with deprecated {legacy_name}");
        }
    }
    Ok(canonical_value.or(legacy_value))
}

fn lease_max_ttl_from_environment() -> anyhow::Result<u64> {
    let Some(value) = compatible_environment_value(LEASE_MAX_TTL_ENV, LEGACY_LEASE_MAX_TTL_ENV)?
    else {
        return Ok(120);
    };
    let parsed = value
        .parse::<u64>()
        .map_err(|_| anyhow::anyhow!("{LEASE_MAX_TTL_ENV} must be an integer"))?;
    if !(5..=300).contains(&parsed) {
        anyhow::bail!("{LEASE_MAX_TTL_ENV} must be between 5 and 300");
    }
    Ok(parsed)
}

fn lease_hmac_key_from_environment() -> Option<LeaseHmacKey> {
    let encoded = std::env::var(LEASE_HMAC_ENV)
        .ok()
        .filter(|value| !value.is_empty());
    let key_file = std::env::var(LEASE_HMAC_FILE_ENV)
        .ok()
        .filter(|value| !value.is_empty());
    match (encoded, key_file) {
        (Some(_), Some(_)) => None,
        (Some(value), None) => LeaseHmacKey::from_encoded(&value).ok(),
        (None, Some(path)) => std::fs::read(path)
            .ok()
            .and_then(|contents| lease_hmac_key_from_file_contents(&contents)),
        (None, None) => None,
    }
}

fn lease_hmac_key_from_file_contents(contents: &[u8]) -> Option<LeaseHmacKey> {
    if contents.len() > MAX_ENCODED_KEY_FILE_BYTES {
        return None;
    }
    let encoded = std::str::from_utf8(contents)
        .ok()?
        .trim_end_matches(['\r', '\n']);
    LeaseHmacKey::from_encoded(encoded).ok()
}

#[derive(Debug, Clone)]
pub struct RuntimeConfig {
    pub bind_addr: String,
    pub profile: String,
    pub node_id: String,
    pub lease_max_ttl_seconds: u64,
    pub lease_hmac_key: Option<LeaseHmacKey>,
    pub lease_state_path: Option<PathBuf>,
}

impl RuntimeConfig {
    pub fn from_environment() -> anyhow::Result<Self> {
        Ok(Self {
            bind_addr: std::env::var("AION_RUNTIME_BIND_ADDR")
                .unwrap_or_else(|_| "127.0.0.1:50051".to_string()),
            profile: std::env::var("OMERTA_PROFILE").unwrap_or_else(|_| "lite".to_string()),
            node_id: std::env::var("AION_RUNTIME_NODE_ID")
                .unwrap_or_else(|_| "runtime-local-1".to_string()),
            lease_max_ttl_seconds: lease_max_ttl_from_environment()?,
            lease_hmac_key: lease_hmac_key_from_environment(),
            lease_state_path: compatible_environment_value(
                LEASE_STATE_PATH_ENV,
                LEGACY_LEASE_STATE_PATH_ENV,
            )?
            .map(PathBuf::from),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::{
        compatible_environment_value, lease_hmac_key_from_file_contents,
        lease_max_ttl_from_environment,
    };

    #[test]
    fn lease_hmac_key_file_accepts_base64_with_a_trailing_newline() {
        let encoded = b"MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=\n";

        assert!(lease_hmac_key_from_file_contents(encoded).is_some());
    }

    #[test]
    fn lease_hmac_key_file_rejects_invalid_or_oversized_material() {
        assert!(lease_hmac_key_from_file_contents(b"not-base64").is_none());
        assert!(lease_hmac_key_from_file_contents(&vec![b'A'; 257]).is_none());
    }

    #[test]
    fn compatible_value_rejects_conflicting_names_without_values_in_error() {
        std::env::set_var("OMERTA_TEST_CANONICAL", "canonical-secret");
        std::env::set_var("AION_TEST_LEGACY", "legacy-secret");

        let error = compatible_environment_value("OMERTA_TEST_CANONICAL", "AION_TEST_LEGACY")
            .expect_err("conflicting names must fail closed")
            .to_string();

        std::env::remove_var("OMERTA_TEST_CANONICAL");
        std::env::remove_var("AION_TEST_LEGACY");
        assert!(error.contains("OMERTA_TEST_CANONICAL"));
        assert!(error.contains("AION_TEST_LEGACY"));
        assert!(!error.contains("canonical-secret"));
        assert!(!error.contains("legacy-secret"));
    }

    #[test]
    fn compatible_value_prefers_canonical_and_accepts_legacy_alias() {
        std::env::set_var("OMERTA_TEST_CANONICAL_VALUE", "canonical");
        std::env::remove_var("AION_TEST_LEGACY_VALUE");
        assert_eq!(
            compatible_environment_value("OMERTA_TEST_CANONICAL_VALUE", "AION_TEST_LEGACY_VALUE")
                .unwrap(),
            Some("canonical".to_string())
        );

        std::env::remove_var("OMERTA_TEST_CANONICAL_VALUE");
        std::env::set_var("AION_TEST_LEGACY_VALUE", "legacy");
        assert_eq!(
            compatible_environment_value("OMERTA_TEST_CANONICAL_VALUE", "AION_TEST_LEGACY_VALUE")
                .unwrap(),
            Some("legacy".to_string())
        );
        std::env::remove_var("AION_TEST_LEGACY_VALUE");
    }

    #[test]
    fn lease_max_ttl_rejects_malformed_canonical_value() {
        std::env::set_var("OMERTA_RUNTIME_LEASE_MAX_TTL_SECONDS", "invalid");
        std::env::remove_var("AION_RUNTIME_LEASE_MAX_TTL_SECONDS");

        let error = lease_max_ttl_from_environment()
            .expect_err("malformed TTL must fail closed")
            .to_string();

        std::env::remove_var("OMERTA_RUNTIME_LEASE_MAX_TTL_SECONDS");
        assert!(error.contains("OMERTA_RUNTIME_LEASE_MAX_TTL_SECONDS"));
        assert!(!error.contains("invalid"));
    }
}
