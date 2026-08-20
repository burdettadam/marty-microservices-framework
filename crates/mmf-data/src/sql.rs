use serde_json::Value;

use crate::DataError;

pub struct PostgresSql;

impl PostgresSql {
    pub fn quote_identifier(identifier: &str) -> Result<String, DataError> {
        if identifier.is_empty()
            || identifier.split('.').any(|part| {
                let mut chars = part.chars();
                chars
                    .next()
                    .is_none_or(|first| !first.is_ascii_alphabetic() && first != '_')
                    || chars.any(|character| !character.is_ascii_alphanumeric() && character != '_')
            })
        {
            return Err(DataError::InvalidQuery(format!(
                "invalid SQL identifier: {identifier}"
            )));
        }
        Ok(identifier
            .split('.')
            .map(|part| format!("\"{part}\""))
            .collect::<Vec<_>>()
            .join("."))
    }

    pub fn literal(value: &Value) -> Result<String, DataError> {
        match value {
            Value::Null => Ok("NULL".into()),
            Value::Bool(value) => Ok(if *value { "TRUE" } else { "FALSE" }.into()),
            Value::Number(value) => Ok(value.to_string()),
            Value::String(value) => Ok(format!("'{}'", value.replace(char::from(39), "''"))),
            Value::Array(_) | Value::Object(_) => serde_json::to_string(value)
                .map(|json| format!("'{}'::jsonb", json.replace(char::from(39), "''")))
                .map_err(|error| DataError::Serialization(error.to_string())),
        }
    }

    pub fn insert(
        table: &str,
        columns: &[String],
        rows: &[Vec<Value>],
    ) -> Result<String, DataError> {
        if columns.is_empty()
            || rows.is_empty()
            || rows.iter().any(|row| row.len() != columns.len())
        {
            return Err(DataError::InvalidQuery(
                "insert requires equally sized columns and rows".into(),
            ));
        }
        let table = Self::quote_identifier(table)?;
        let columns = columns
            .iter()
            .map(|column| Self::quote_identifier(column))
            .collect::<Result<Vec<_>, _>>()?
            .join(", ");
        let rows = rows
            .iter()
            .map(|row| {
                row.iter()
                    .map(Self::literal)
                    .collect::<Result<Vec<_>, _>>()
                    .map(|values| format!("({})", values.join(", ")))
            })
            .collect::<Result<Vec<_>, _>>()?
            .join(",\n");
        Ok(format!("INSERT INTO {table} ({columns}) VALUES\n{rows};"))
    }
}
