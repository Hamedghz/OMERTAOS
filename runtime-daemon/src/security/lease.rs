use std::collections::HashMap;
use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use base64::engine::general_purpose::{STANDARD, URL_SAFE_NO_PAD};
use base64::Engine;
use hmac::{Hmac, Mac};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use thiserror::Error;

const DOMAIN: &[u8] = b"OMERTA_RUNTIME_LEASE_V1\0";
const KEY_MIN_BYTES: usize = 32;
const KEY_MAX_BYTES: usize = 64;
const TOKEN_PART_BYTES: usize = 32;
const STATE_VERSION: u8 = 1;
const MAX_FENCE_RECORDS: usize = 10_000;

type HmacSha256 = Hmac<Sha256>;

#[derive(Debug, Error, PartialEq, Eq)]
pub enum LeaseError {
    #[error("lease metadata is incomplete")]
    Incomplete,
    #[error("lease metadata is malformed")]
    Malformed,
    #[error("lease verification key is unavailable")]
    VerificationUnavailable,
    #[error("lease signature is invalid")]
    InvalidSignature,
    #[error("lease targets a different runtime node")]
    NodeMismatch,
    #[error("lease is expired")]
    Expired,
    #[error("lease expiry exceeds the runtime bound")]
    ExcessiveTtl,
    #[error("lease generation is stale or already claimed")]
    Stale,
    #[error("lease fence state is malformed")]
    StateCorrupt,
    #[error("lease fence state is unavailable")]
    StateUnavailable,
}

#[derive(Clone, PartialEq, Eq)]
pub struct LeaseHmacKey(Vec<u8>);

impl std::fmt::Debug for LeaseHmacKey {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str("LeaseHmacKey([REDACTED])")
    }
}

impl LeaseHmacKey {
    pub fn from_encoded(encoded: &str) -> Result<Self, LeaseError> {
        let decoded = STANDARD
            .decode(encoded)
            .map_err(|_| LeaseError::VerificationUnavailable)?;
        if !(KEY_MIN_BYTES..=KEY_MAX_BYTES).contains(&decoded.len()) {
            return Err(LeaseError::VerificationUnavailable);
        }
        Ok(Self(decoded))
    }

    fn verify(&self, claim: &LeaseClaim) -> Result<(), LeaseError> {
        let mut mac =
            HmacSha256::new_from_slice(&self.0).map_err(|_| LeaseError::VerificationUnavailable)?;
        mac.update(&claim.signature_payload());
        mac.verify_slice(&claim.signature)
            .map_err(|_| LeaseError::InvalidSignature)
    }

    #[cfg(test)]
    fn sign(&self, claim: &LeaseClaim) -> Vec<u8> {
        let mut mac = HmacSha256::new_from_slice(&self.0).unwrap();
        mac.update(&claim.signature_payload());
        mac.finalize().into_bytes().to_vec()
    }
}

#[derive(Clone, PartialEq, Eq)]
pub struct LeaseClaim {
    pub tenant_id: String,
    pub task_id: String,
    pub attempt_id: String,
    pub node_id: String,
    pub generation: u64,
    pub expires_at_ms: u64,
    nonce: Vec<u8>,
    signature: Vec<u8>,
}

impl std::fmt::Debug for LeaseClaim {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("LeaseClaim")
            .field("tenant_id", &self.tenant_id)
            .field("task_id", &self.task_id)
            .field("attempt_id", &self.attempt_id)
            .field("node_id", &self.node_id)
            .field("generation", &self.generation)
            .field("expires_at_ms", &self.expires_at_ms)
            .field("token", &"[REDACTED]")
            .finish()
    }
}

impl LeaseClaim {
    pub fn parse(
        tenant_id: &str,
        task_id: &str,
        attempt_id: &str,
        node_id: &str,
        token: &str,
        generation: &str,
        expires_at_ms: &str,
    ) -> Result<Self, LeaseError> {
        if [
            tenant_id,
            task_id,
            attempt_id,
            node_id,
            token,
            generation,
            expires_at_ms,
        ]
        .iter()
        .any(|value| value.is_empty())
        {
            return Err(LeaseError::Incomplete);
        }
        let (nonce, signature) = token.split_once('.').ok_or(LeaseError::Malformed)?;
        if signature.contains('.') {
            return Err(LeaseError::Malformed);
        }
        let nonce = URL_SAFE_NO_PAD
            .decode(nonce)
            .map_err(|_| LeaseError::Malformed)?;
        let signature = URL_SAFE_NO_PAD
            .decode(signature)
            .map_err(|_| LeaseError::Malformed)?;
        if nonce.len() != TOKEN_PART_BYTES || signature.len() != TOKEN_PART_BYTES {
            return Err(LeaseError::Malformed);
        }
        let generation = generation.parse().map_err(|_| LeaseError::Malformed)?;
        let expires_at_ms = expires_at_ms.parse().map_err(|_| LeaseError::Malformed)?;
        if generation == 0 || expires_at_ms == 0 {
            return Err(LeaseError::Malformed);
        }
        Ok(Self {
            tenant_id: tenant_id.to_owned(),
            task_id: task_id.to_owned(),
            attempt_id: attempt_id.to_owned(),
            node_id: node_id.to_owned(),
            generation,
            expires_at_ms,
            nonce,
            signature,
        })
    }

    fn signature_payload(&self) -> Vec<u8> {
        let mut payload = DOMAIN.to_vec();
        push_part(&mut payload, self.tenant_id.as_bytes());
        push_part(&mut payload, self.task_id.as_bytes());
        push_part(&mut payload, self.attempt_id.as_bytes());
        push_part(&mut payload, self.node_id.as_bytes());
        push_part(&mut payload, &self.nonce);
        payload.extend_from_slice(&self.generation.to_be_bytes());
        payload.extend_from_slice(&self.expires_at_ms.to_be_bytes());
        payload
    }

    fn fence_key(&self) -> String {
        let mut identity = Vec::new();
        push_part(&mut identity, self.tenant_id.as_bytes());
        push_part(&mut identity, self.task_id.as_bytes());
        URL_SAFE_NO_PAD.encode(Sha256::digest(identity))
    }
}

fn push_part(destination: &mut Vec<u8>, value: &[u8]) {
    destination.extend_from_slice(&(value.len() as u32).to_be_bytes());
    destination.extend_from_slice(value);
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
struct FenceRecord {
    generation: u64,
    expires_at_ms: u64,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct FenceState {
    version: u8,
    records: HashMap<String, FenceRecord>,
}

#[derive(Debug)]
pub struct LeaseFence {
    records: Mutex<HashMap<String, FenceRecord>>,
    state_path: Option<PathBuf>,
}

impl Default for LeaseFence {
    fn default() -> Self {
        Self {
            records: Mutex::new(HashMap::new()),
            state_path: None,
        }
    }
}

impl LeaseFence {
    pub fn open(state_path: Option<PathBuf>) -> Result<Self, LeaseError> {
        let records = match state_path.as_deref() {
            Some(path) => load_state(path)?,
            None => HashMap::new(),
        };
        Ok(Self {
            records: Mutex::new(records),
            state_path,
        })
    }

    pub fn claim(
        &self,
        claim: &LeaseClaim,
        verification_key: Option<&LeaseHmacKey>,
        expected_node_id: &str,
        now_ms: u64,
        max_ttl_seconds: u64,
    ) -> Result<(), LeaseError> {
        verification_key
            .ok_or(LeaseError::VerificationUnavailable)?
            .verify(claim)?;
        if claim.node_id != expected_node_id {
            return Err(LeaseError::NodeMismatch);
        }
        if claim.expires_at_ms <= now_ms {
            return Err(LeaseError::Expired);
        }
        let max_expiry = now_ms.saturating_add(max_ttl_seconds.saturating_mul(1000));
        if claim.expires_at_ms > max_expiry {
            return Err(LeaseError::ExcessiveTtl);
        }
        let mut records = self
            .records
            .lock()
            .map_err(|_| LeaseError::StateUnavailable)?;
        let mut candidate = records.clone();
        candidate.retain(|_, record| record.expires_at_ms > now_ms);
        let key = claim.fence_key();
        if candidate
            .get(&key)
            .is_some_and(|current| current.generation >= claim.generation)
        {
            return Err(LeaseError::Stale);
        }
        if candidate.len() >= MAX_FENCE_RECORDS && !candidate.contains_key(&key) {
            return Err(LeaseError::StateUnavailable);
        }
        candidate.insert(
            key,
            FenceRecord {
                generation: claim.generation,
                expires_at_ms: claim.expires_at_ms,
            },
        );
        if let Some(path) = self.state_path.as_deref() {
            persist_state(path, &candidate)?;
        }
        *records = candidate;
        Ok(())
    }
}

fn load_state(path: &Path) -> Result<HashMap<String, FenceRecord>, LeaseError> {
    if !path.exists() {
        return Ok(HashMap::new());
    }
    let bytes = fs::read(path).map_err(|_| LeaseError::StateUnavailable)?;
    let state: FenceState = serde_json::from_slice(&bytes).map_err(|_| LeaseError::StateCorrupt)?;
    if state.version != STATE_VERSION
        || state
            .records
            .values()
            .any(|record| record.generation == 0 || record.expires_at_ms == 0)
        || state.records.len() > MAX_FENCE_RECORDS
    {
        return Err(LeaseError::StateCorrupt);
    }
    Ok(state.records)
}

fn persist_state(path: &Path, records: &HashMap<String, FenceRecord>) -> Result<(), LeaseError> {
    let parent = path.parent().ok_or(LeaseError::StateUnavailable)?;
    fs::create_dir_all(parent).map_err(|_| LeaseError::StateUnavailable)?;
    let temporary = path.with_extension("tmp");
    let payload = serde_json::to_vec(&FenceState {
        version: STATE_VERSION,
        records: records.clone(),
    })
    .map_err(|_| LeaseError::StateUnavailable)?;
    let mut file = OpenOptions::new()
        .create(true)
        .truncate(true)
        .write(true)
        .open(&temporary)
        .map_err(|_| LeaseError::StateUnavailable)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        file.set_permissions(fs::Permissions::from_mode(0o600))
            .map_err(|_| LeaseError::StateUnavailable)?;
    }
    file.write_all(&payload)
        .and_then(|_| file.sync_all())
        .map_err(|_| LeaseError::StateUnavailable)?;
    fs::rename(&temporary, path).map_err(|_| LeaseError::StateUnavailable)?;
    File::open(parent)
        .and_then(|directory| directory.sync_all())
        .map_err(|_| LeaseError::StateUnavailable)
}

#[cfg(test)]
mod tests {
    use std::time::{SystemTime, UNIX_EPOCH};

    use super::*;

    fn key() -> LeaseHmacKey {
        LeaseHmacKey::from_encoded(&STANDARD.encode(b"kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk")).unwrap()
    }

    fn claim(generation: u64, expires_at_ms: u64) -> LeaseClaim {
        let key = key();
        let mut claim = LeaseClaim {
            tenant_id: "tenant-a".into(),
            task_id: "task-a".into(),
            attempt_id: format!("task-a:{generation}"),
            node_id: "runtime-a".into(),
            generation,
            expires_at_ms,
            nonce: vec![generation as u8; TOKEN_PART_BYTES],
            signature: vec![],
        };
        claim.signature = key.sign(&claim);
        claim
    }

    fn temporary_state(name: &str) -> PathBuf {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!("omerta-{name}-{}-{nonce}.json", std::process::id()))
    }

    #[test]
    fn claims_once_and_fences_older_generations() {
        let fence = LeaseFence::default();
        let first = claim(10, 20_000);
        let newer = claim(11, 20_000);

        assert_eq!(
            fence.claim(&first, Some(&key()), "runtime-a", 10_000, 30),
            Ok(())
        );
        assert_eq!(
            fence.claim(&first, Some(&key()), "runtime-a", 10_000, 30),
            Err(LeaseError::Stale)
        );
        assert_eq!(
            fence.claim(&newer, Some(&key()), "runtime-a", 10_000, 30),
            Ok(())
        );
        assert_eq!(
            fence.claim(&first, Some(&key()), "runtime-a", 10_000, 30),
            Err(LeaseError::Stale)
        );
    }

    #[test]
    fn verifies_the_control_signature_vector() {
        let claim = LeaseClaim::parse(
            "tenant-a",
            "task-a",
            "task-a:0",
            "runtime-a",
            "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8.pDKR8czXaUyYsAv_qBTKz4re6Bgw0utl1i9B6vCfKpA",
            "7",
            "2000000000000",
        )
        .unwrap();

        assert_eq!(key().verify(&claim), Ok(()));
    }

    #[test]
    fn rejects_forged_expired_wrong_node_and_excessive_ttl_claims() {
        let fence = LeaseFence::default();
        let mut forged = claim(1, 20_000);
        forged.task_id = "forged-task".into();
        let expired = claim(2, 10_000);
        let future = claim(3, 100_000);

        assert_eq!(
            fence.claim(&forged, Some(&key()), "runtime-a", 10_000, 30),
            Err(LeaseError::InvalidSignature)
        );
        assert_eq!(
            fence.claim(&expired, Some(&key()), "runtime-a", 10_000, 30),
            Err(LeaseError::Expired)
        );
        assert_eq!(
            fence.claim(&future, Some(&key()), "runtime-b", 10_000, 120),
            Err(LeaseError::NodeMismatch)
        );
        assert_eq!(
            fence.claim(&future, Some(&key()), "runtime-a", 10_000, 30),
            Err(LeaseError::ExcessiveTtl)
        );
    }

    #[test]
    fn rejects_missing_key_and_malformed_metadata_without_exposing_token() {
        let valid = claim(1, 20_000);
        assert_eq!(
            LeaseFence::default().claim(&valid, None, "runtime-a", 10_000, 30),
            Err(LeaseError::VerificationUnavailable)
        );
        assert_eq!(
            LeaseClaim::parse("", "task", "attempt", "node", "token", "1", "2"),
            Err(LeaseError::Incomplete)
        );
        assert_eq!(
            LeaseClaim::parse("tenant", "task", "attempt", "node", "short", "one", "two"),
            Err(LeaseError::Malformed)
        );
        assert!(!format!("{valid:?}").contains(&URL_SAFE_NO_PAD.encode(&valid.signature)));
    }

    #[test]
    fn persistent_fence_rejects_replay_after_restart() {
        let path = temporary_state("lease-restart");
        let accepted = claim(10, 20_000);
        let encoded_signature = URL_SAFE_NO_PAD.encode(&accepted.signature);
        LeaseFence::open(Some(path.clone()))
            .unwrap()
            .claim(&accepted, Some(&key()), "runtime-a", 10_000, 30)
            .unwrap();

        let persisted = fs::read_to_string(&path).unwrap();
        assert!(!persisted.contains("tenant-a"));
        assert!(!persisted.contains("task-a"));
        assert!(!persisted.contains(&encoded_signature));
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            assert_eq!(
                fs::metadata(&path).unwrap().permissions().mode() & 0o777,
                0o600
            );
        }

        let restarted = LeaseFence::open(Some(path.clone())).unwrap();
        assert_eq!(
            restarted.claim(&accepted, Some(&key()), "runtime-a", 10_000, 30),
            Err(LeaseError::Stale)
        );

        fs::remove_file(path).unwrap();
    }

    #[test]
    fn corrupt_persistent_state_fails_closed() {
        let path = temporary_state("lease-corrupt");
        fs::write(&path, b"not-json").unwrap();

        assert_eq!(
            LeaseFence::open(Some(path.clone())).unwrap_err(),
            LeaseError::StateCorrupt
        );

        fs::remove_file(path).unwrap();
    }
}
