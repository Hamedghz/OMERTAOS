pub mod audit;
pub mod cluster {
    pub mod node_registration;
    pub mod resource_report;
}
pub mod config;
mod environment;
pub mod execution;
pub mod isolation {
    pub mod cpu;
    pub mod gpu;
    pub mod memory;
    pub mod quota;
}
pub mod observability {
    pub mod metrics;
}
pub mod sandbox {
    pub mod mount;
    pub mod namespace;
    pub mod process;
    pub mod seccomp;
}
pub mod security {
    pub mod capability;
    pub mod lease;
    pub mod signature;
}
pub mod server;

use config::RuntimeConfig;

pub async fn run() -> anyhow::Result<()> {
    if std::env::args().any(|arg| arg == "--healthcheck") {
        let address = std::env::var("AION_RUNTIME_HEALTH_ADDR")
            .unwrap_or_else(|_| "127.0.0.1:50051".to_string());
        tokio::net::TcpStream::connect(address).await?;
        return Ok(());
    }

    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .init();

    let config = RuntimeConfig::from_environment()?;
    tracing::info!(
        bind_addr = %config.bind_addr,
        profile = %config.profile,
        "runtime daemon starting"
    );
    server::run_server(config).await
}
