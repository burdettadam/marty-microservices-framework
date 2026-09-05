use serde_json::Value;

/// Object ordering for the legacy spaced-JSON wire convention.
#[derive(Clone, Copy)]
pub enum JsonObjectOrder {
    /// Sort keys regardless of `serde_json`'s map feature configuration.
    Sorted,
    /// Preserve the order exposed by `serde_json`'s map.
    Map,
}

/// Encode JSON with comma/colon spaces while preserving serde's scalar encoding.
/// This is the framework's compatibility format, not a general Python serializer.
#[must_use]
pub fn spaced_json(value: &Value, order: JsonObjectOrder) -> String {
    match value {
        Value::Array(values) => format!(
            "[{}]",
            values
                .iter()
                .map(|v| spaced_json(v, order))
                .collect::<Vec<_>>()
                .join(", ")
        ),
        Value::Object(values) => {
            let mut entries = values.iter().collect::<Vec<_>>();
            if matches!(order, JsonObjectOrder::Sorted) {
                entries.sort_by_key(|(key, _)| *key);
            }
            format!(
                "{{{}}}",
                entries
                    .into_iter()
                    .map(|(key, value)| format!(
                        "{}: {}",
                        Value::String(key.clone()),
                        spaced_json(value, order)
                    ))
                    .collect::<Vec<_>>()
                    .join(", ")
            )
        }
        _ => value.to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn nested_wire_bytes_and_scalars_are_stable() {
        let value = json!({"z": [null, true, false, -7, 1.25], "a": "é\n\"\\"});
        assert_eq!(
            spaced_json(&value, JsonObjectOrder::Sorted),
            "{\"a\": \"é\\n\\\"\\\\\", \"z\": [null, true, false, -7, 1.25]}"
        );
        for value in [json!(null), json!(true), json!(1.0), json!("text")] {
            assert_eq!(spaced_json(&value, JsonObjectOrder::Map), value.to_string());
        }
    }

    #[test]
    fn ordering_policy_is_explicit_even_with_preserve_order() {
        let value: Value = serde_json::from_str(r#"{"z": {"b": 1, "a": 2}, "a": 0}"#).unwrap();
        assert_eq!(
            spaced_json(&value, JsonObjectOrder::Sorted),
            r#"{"a": 0, "z": {"a": 2, "b": 1}}"#
        );
        let encoded = spaced_json(&value, JsonObjectOrder::Map);
        let decoded: Value = serde_json::from_str(&encoded).unwrap();
        assert_eq!(decoded, value);
        let first = value.as_object().unwrap().keys().next().unwrap();
        assert!(encoded.starts_with(&format!("{{\"{first}\": ")));
    }
}
