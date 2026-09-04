use crate::environment::{resolve_from_source, EnvironmentResolutionError, EnvironmentSpec};

const NODE_ID_ENV: &str = "OMERTA_RUNTIME_NODE_ID";
const LEGACY_NODE_ID_ENV: &str = "AION_RUNTIME_NODE_ID";
const MEMORY_MB_ENV: &str = "OMERTA_RUNTIME_MEMORY_MB";
const LEGACY_MEMORY_MB_ENV: &str = "AION_RUNTIME_MEMORY_MB";
const CAPABILITIES_ENV: &str = "OMERTA_RUNTIME_CAPABILITIES";
const LEGACY_CAPABILITIES_ENV: &str = "AION_RUNTIME_CAPABILITIES";

pub fn report_resources() -> String {
    report_resources_from_source(|name| std::env::var(name).ok())
        .expect("Runtime resource environment must be valid")
}

fn report_resources_from_source<Source>(
    source: Source,
) -> Result<String, EnvironmentResolutionError>
where
    Source: Fn(&str) -> Option<String> + Copy,
{
    let node_id = resolve_from_source(
        EnvironmentSpec::new(NODE_ID_ENV)
            .aliases(&[LEGACY_NODE_ID_ENV])
            .default("runtime-local-1"),
        source,
        |value| Ok(value.to_owned()),
    )?
    .expect("Runtime node id has a default");
    let profile = resolve_from_source(
        EnvironmentSpec::new("OMERTA_PROFILE").default("lite"),
        source,
        |value| Ok(value.to_owned()),
    )?
    .expect("Runtime profile has a default");
    let memory_mb = resolve_from_source(
        EnvironmentSpec::new(MEMORY_MB_ENV)
            .aliases(&[LEGACY_MEMORY_MB_ENV])
            .default("512"),
        source,
        |value| Ok(value.parse::<u64>().unwrap_or(512)),
    )?
    .expect("Runtime memory has a default");
    let cpu_millis = std::thread::available_parallelism()
        .map(|parallelism| parallelism.get() as u64 * 1000)
        .unwrap_or(1000);
    let capabilities = resolve_from_source(
        EnvironmentSpec::new(CAPABILITIES_ENV)
            .aliases(&[LEGACY_CAPABILITIES_ENV])
            .default("resource.allocate"),
        source,
        |value| Ok(value.to_owned()),
    )?
    .expect("Runtime capabilities have a default");
    let capability_json = capabilities
        .split(',')
        .map(str::trim)
        .filter(|capability| !capability.is_empty())
        .map(|capability| format!("\"{}\"", escape_json(capability)))
        .collect::<Vec<_>>()
        .join(",");

    Ok(format!(
        "{{\"node_id\":\"{}\",\"profile\":\"{}\",\"total_cpu_millis\":{},\"available_cpu_millis\":{},\"total_memory_mb\":{},\"available_memory_mb\":{},\"capabilities\":[{}]}}",
        escape_json(&node_id),
        escape_json(&profile),
        cpu_millis,
        cpu_millis,
        memory_mb,
        memory_mb,
        capability_json
    ))
}

fn escape_json(value: &str) -> String {
    value.replace('\\', "\\\\").replace('"', "\\\"")
}

#[cfg(test)]
mod tests {
    use std::collections::HashMap;

    use super::report_resources_from_source;

    #[test]
    fn canonical_runtime_settings_drive_resource_report() {
        let values = HashMap::from([
            ("OMERTA_RUNTIME_NODE_ID", "runtime-canonical"),
            ("OMERTA_RUNTIME_MEMORY_MB", "1024"),
            (
                "OMERTA_RUNTIME_CAPABILITIES",
                "terminal.execute,resource.allocate",
            ),
        ]);

        let report =
            report_resources_from_source(|name| values.get(name).map(|value| (*value).to_owned()))
                .unwrap();

        assert!(report.contains("\"node_id\":\"runtime-canonical\""));
        assert!(report.contains("\"total_memory_mb\":1024"));
        assert!(report.contains("\"terminal.execute\""));
        assert!(report.contains("\"resource.allocate\""));
    }

    #[test]
    fn resource_report_rejects_conflicting_aliases_without_values() {
        let values = HashMap::from([
            ("OMERTA_RUNTIME_NODE_ID", "canonical-sensitive-node"),
            ("AION_RUNTIME_NODE_ID", "legacy-sensitive-node"),
        ]);

        let error =
            report_resources_from_source(|name| values.get(name).map(|value| (*value).to_owned()))
                .unwrap_err();
        let rendered = format!("{error} {error:?}");

        assert!(rendered.contains("OMERTA_RUNTIME_NODE_ID"));
        assert!(rendered.contains("AION_RUNTIME_NODE_ID"));
        assert!(!rendered.contains("canonical-sensitive-node"));
        assert!(!rendered.contains("legacy-sensitive-node"));
    }
}
