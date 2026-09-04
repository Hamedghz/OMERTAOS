use std::collections::HashSet;

use thiserror::Error;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum BlankPolicy {
    Unset,
    #[allow(dead_code)]
    Preserve,
    Reject,
}

#[derive(Debug, Clone, Copy)]
pub(crate) struct EnvironmentSpec<'a> {
    canonical_name: &'a str,
    aliases: &'a [&'a str],
    default: Option<&'a str>,
    required: bool,
    blank: BlankPolicy,
}

impl<'a> EnvironmentSpec<'a> {
    pub(crate) const fn new(canonical_name: &'a str) -> Self {
        Self {
            canonical_name,
            aliases: &[],
            default: None,
            required: false,
            blank: BlankPolicy::Unset,
        }
    }

    pub(crate) const fn aliases(mut self, aliases: &'a [&'a str]) -> Self {
        self.aliases = aliases;
        self
    }

    pub(crate) const fn default(mut self, default: &'a str) -> Self {
        self.default = Some(default);
        self
    }

    #[allow(dead_code)]
    pub(crate) const fn required(mut self) -> Self {
        self.required = true;
        self
    }

    #[allow(dead_code)]
    pub(crate) const fn blank(mut self, blank: BlankPolicy) -> Self {
        self.blank = blank;
        self
    }
}

#[derive(Debug, Error)]
pub(crate) enum EnvironmentResolutionError {
    #[error("{canonical_name} conflicts with deprecated {legacy_names}")]
    Conflict {
        canonical_name: String,
        legacy_names: String,
    },
    #[error("{name} may not be blank")]
    Blank { name: String },
    #[error("{name} is required")]
    Required { name: String },
    #[error("{name} is invalid")]
    Invalid { name: String },
    #[error("environment resolver definition is invalid")]
    InvalidDefinition,
}

pub(crate) fn resolve_environment<T, Parser>(
    spec: EnvironmentSpec<'_>,
    parser: Parser,
) -> Result<Option<T>, EnvironmentResolutionError>
where
    Parser: Fn(&str) -> Result<T, ()>,
{
    resolve_from_source(spec, |name| std::env::var(name).ok(), parser)
}

pub(crate) fn resolve_from_source<T, Source, Parser>(
    spec: EnvironmentSpec<'_>,
    source: Source,
    parser: Parser,
) -> Result<Option<T>, EnvironmentResolutionError>
where
    Source: Fn(&str) -> Option<String>,
    Parser: Fn(&str) -> Result<T, ()>,
{
    validate_spec(spec)?;

    let mut present = Vec::new();
    for name in std::iter::once(spec.canonical_name).chain(spec.aliases.iter().copied()) {
        if let Some(value) = normalize_value(name, source(name), spec.blank)? {
            present.push((name, value));
        }
    }

    let (selected_name, raw_value) = if present.is_empty() {
        if let Some(default) = spec.default {
            (spec.canonical_name, default.to_owned())
        } else if spec.required {
            return Err(EnvironmentResolutionError::Required {
                name: spec.canonical_name.to_owned(),
            });
        } else {
            return Ok(None);
        }
    } else {
        if present.iter().any(|(_, value)| value != &present[0].1) {
            let legacy_names = present
                .iter()
                .filter_map(|(name, _)| (*name != spec.canonical_name).then_some(*name))
                .collect::<Vec<_>>()
                .join(", ");
            return Err(EnvironmentResolutionError::Conflict {
                canonical_name: spec.canonical_name.to_owned(),
                legacy_names,
            });
        }

        if let Some((name, value)) = present
            .iter()
            .find(|(name, _)| *name == spec.canonical_name)
        {
            (*name, value.clone())
        } else {
            for (legacy_name, _) in &present {
                tracing::warn!(
                    canonical_name = spec.canonical_name,
                    legacy_name = *legacy_name,
                    "deprecated environment alias used"
                );
            }
            (present[0].0, present[0].1.clone())
        }
    };

    parser(&raw_value)
        .map(Some)
        .map_err(|_| EnvironmentResolutionError::Invalid {
            name: selected_name.to_owned(),
        })
}

fn validate_spec(spec: EnvironmentSpec<'_>) -> Result<(), EnvironmentResolutionError> {
    let names = std::iter::once(spec.canonical_name)
        .chain(spec.aliases.iter().copied())
        .collect::<Vec<_>>();
    let unique = names.iter().copied().collect::<HashSet<_>>();
    if names.iter().any(|name| name.is_empty())
        || names.len() != unique.len()
        || (spec.required && spec.default.is_some())
    {
        return Err(EnvironmentResolutionError::InvalidDefinition);
    }
    Ok(())
}

fn normalize_value(
    name: &str,
    value: Option<String>,
    blank: BlankPolicy,
) -> Result<Option<String>, EnvironmentResolutionError> {
    match value {
        Some(value) if value.is_empty() && blank == BlankPolicy::Unset => Ok(None),
        Some(value) if value.is_empty() && blank == BlankPolicy::Reject => {
            Err(EnvironmentResolutionError::Blank {
                name: name.to_owned(),
            })
        }
        value => Ok(value),
    }
}

#[cfg(test)]
mod tests {
    use std::collections::HashMap;

    use super::{resolve_from_source, BlankPolicy, EnvironmentResolutionError, EnvironmentSpec};

    const CANONICAL: &str = "OMERTA_TEST_CANONICAL";
    const LEGACY: &str = "AION_TEST_LEGACY";

    fn resolve_string(
        spec: EnvironmentSpec<'_>,
        values: &[(&str, &str)],
    ) -> Result<Option<String>, EnvironmentResolutionError> {
        let source = values
            .iter()
            .map(|(name, value)| ((*name).to_owned(), (*value).to_owned()))
            .collect::<HashMap<_, _>>();
        resolve_from_source(
            spec,
            |name| source.get(name).cloned(),
            |value| Ok(value.to_owned()),
        )
    }

    #[test]
    fn resolves_canonical_legacy_and_equal_values() {
        let spec = EnvironmentSpec::new(CANONICAL).aliases(&[LEGACY]);

        assert_eq!(
            resolve_string(spec, &[(CANONICAL, "new")]).unwrap(),
            Some("new".to_owned())
        );
        assert_eq!(
            resolve_string(spec, &[(LEGACY, "old")]).unwrap(),
            Some("old".to_owned())
        );
        assert_eq!(
            resolve_string(spec, &[(CANONICAL, "equal"), (LEGACY, "equal")]).unwrap(),
            Some("equal".to_owned())
        );
    }

    #[test]
    fn rejects_conflict_without_exposing_values() {
        let spec = EnvironmentSpec::new(CANONICAL).aliases(&[LEGACY]);
        let error = resolve_string(
            spec,
            &[(CANONICAL, "canonical-secret"), (LEGACY, "legacy-secret")],
        )
        .unwrap_err();
        let rendered = format!("{error} {error:?}");

        assert!(rendered.contains(CANONICAL));
        assert!(rendered.contains(LEGACY));
        assert!(!rendered.contains("canonical-secret"));
        assert!(!rendered.contains("legacy-secret"));
    }

    #[test]
    fn applies_explicit_unset_blank_and_required_policies() {
        assert_eq!(
            resolve_string(EnvironmentSpec::new(CANONICAL).default("fallback"), &[]).unwrap(),
            Some("fallback".to_owned())
        );
        assert_eq!(
            resolve_string(EnvironmentSpec::new(CANONICAL), &[]).unwrap(),
            None
        );
        assert_eq!(
            resolve_string(
                EnvironmentSpec::new(CANONICAL).default("fallback"),
                &[(CANONICAL, "")],
            )
            .unwrap(),
            Some("fallback".to_owned())
        );
        assert_eq!(
            resolve_string(
                EnvironmentSpec::new(CANONICAL).blank(BlankPolicy::Preserve),
                &[(CANONICAL, "")],
            )
            .unwrap(),
            Some(String::new())
        );
        assert!(matches!(
            resolve_string(
                EnvironmentSpec::new(CANONICAL).blank(BlankPolicy::Reject),
                &[(CANONICAL, "")],
            ),
            Err(EnvironmentResolutionError::Blank { .. })
        ));
        assert!(matches!(
            resolve_string(EnvironmentSpec::new(CANONICAL).required(), &[]),
            Err(EnvironmentResolutionError::Required { .. })
        ));
    }

    #[test]
    fn typed_parser_rejects_malformed_and_out_of_range_values_without_echo() {
        for value in ["not-a-number-sensitive", "7", "33"] {
            let source = HashMap::from([(CANONICAL.to_owned(), value.to_owned())]);
            let error = resolve_from_source(
                EnvironmentSpec::new(CANONICAL),
                |name| source.get(name).cloned(),
                |raw| {
                    let parsed = raw.parse::<u64>().map_err(|_| ())?;
                    (8..=32).contains(&parsed).then_some(parsed).ok_or(())
                },
            )
            .unwrap_err();
            let rendered = format!("{error} {error:?}");

            assert!(rendered.contains(CANONICAL));
            assert!(!rendered.contains(value));
        }
    }
}
