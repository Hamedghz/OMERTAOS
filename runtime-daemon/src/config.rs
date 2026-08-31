use std::path::PathBuf;

use crate::security::lease::LeaseHmacKey;

const LEASE_HMAC_ENV: &str = "OMERTA_RUNTIME_LEASE_HMAC_KEY";
const LEASE_HMAC_FILE_ENV: &str = "OMERTA_RUNTIME_LEASE_HMAC_KEY_FILE";
const MAX_ENCODED_KEY_FILE_BYTES: usize = 256;

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

impl Default for RuntimeConfig {
    fn default() -> Self {
        Self {
            bind_addr: std::env::var("AION_RUNTIME_BIND_ADDR")
                .unwrap_or_else(|_| "127.0.0.1:50051".to_string()),
            profile: std::env::var("OMERTA_PROFILE").unwrap_or_else(|_| "lite".to_string()),
            node_id: std::env::var("AION_RUNTIME_NODE_ID")
                .unwrap_or_else(|_| "runtime-local-1".to_string()),
            lease_max_ttl_seconds: std::env::var("AION_RUNTIME_LEASE_MAX_TTL_SECONDS")
                .ok()
                .and_then(|value| value.parse().ok())
                .filter(|value| (5..=300).contains(value))
                .unwrap_or(120),
            lease_hmac_key: lease_hmac_key_from_environment(),
            lease_state_path: std::env::var("AION_RUNTIME_LEASE_STATE_PATH")
                .ok()
                .filter(|value| !value.is_empty())
                .map(PathBuf::from),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::lease_hmac_key_from_file_contents;

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
}
