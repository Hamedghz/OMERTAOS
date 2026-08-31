use std::path::PathBuf;

use crate::security::lease::LeaseHmacKey;

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
            lease_hmac_key: std::env::var("OMERTA_RUNTIME_LEASE_HMAC_KEY")
                .ok()
                .filter(|value| !value.is_empty())
                .and_then(|value| LeaseHmacKey::from_encoded(&value).ok()),
            lease_state_path: std::env::var("AION_RUNTIME_LEASE_STATE_PATH")
                .ok()
                .filter(|value| !value.is_empty())
                .map(PathBuf::from),
        }
    }
}
