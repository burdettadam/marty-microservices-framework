use std::cmp::Ordering;
use std::collections::BTreeMap;
use std::sync::{Arc, Mutex};

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::DataError;

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(tag = "operator", content = "value", rename_all = "snake_case")]
pub enum Filter {
    Eq(Value),
    Ne(Value),
    Gt(Value),
    Gte(Value),
    Lt(Value),
    Lte(Value),
    In(Vec<Value>),
    NotIn(Vec<Value>),
}

impl Filter {
    pub fn matches(&self, actual: &Value) -> Result<bool, DataError> {
        match self {
            Self::Eq(expected) => Ok(actual == expected),
            Self::Ne(expected) => Ok(actual != expected),
            Self::Gt(expected) => compare(actual, expected).map(Ordering::is_gt),
            Self::Gte(expected) => compare(actual, expected).map(Ordering::is_ge),
            Self::Lt(expected) => compare(actual, expected).map(Ordering::is_lt),
            Self::Lte(expected) => compare(actual, expected).map(Ordering::is_le),
            Self::In(values) => Ok(values.contains(actual)),
            Self::NotIn(values) => Ok(!values.contains(actual)),
        }
    }
}

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SortOrder {
    #[default]
    Ascending,
    Descending,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ReadModelQuery {
    #[serde(default)]
    pub filters: BTreeMap<String, Filter>,
    pub sort_by: Option<String>,
    #[serde(default)]
    pub sort_order: SortOrder,
    #[serde(default = "one")]
    pub page: usize,
    #[serde(default = "default_page_size")]
    pub page_size: usize,
}

const fn one() -> usize {
    1
}

const fn default_page_size() -> usize {
    20
}

impl Default for ReadModelQuery {
    fn default() -> Self {
        Self {
            filters: BTreeMap::new(),
            sort_by: None,
            sort_order: SortOrder::Ascending,
            page: one(),
            page_size: default_page_size(),
        }
    }
}

impl ReadModelQuery {
    pub fn validate(&self) -> Result<(), DataError> {
        if self.page == 0 || self.page_size == 0 || self.page_size > 10_000 {
            return Err(DataError::InvalidQuery(
                "page and bounded page size must be positive".into(),
            ));
        }
        Ok(())
    }
}

#[async_trait]
pub trait ReadModelStore: Send + Sync {
    async fn save(&self, model_type: &str, model_id: &str, data: Value) -> Result<(), DataError>;
    async fn get(&self, model_type: &str, model_id: &str) -> Result<Option<Value>, DataError>;
    async fn query(
        &self,
        model_type: &str,
        query: &ReadModelQuery,
    ) -> Result<Vec<Value>, DataError>;
    async fn delete(&self, model_type: &str, model_id: &str) -> Result<bool, DataError>;
    async fn count(
        &self,
        model_type: &str,
        filters: &BTreeMap<String, Filter>,
    ) -> Result<usize, DataError>;
}

#[derive(Clone, Default)]
pub struct InMemoryReadModelStore {
    models: Arc<Mutex<BTreeMap<String, BTreeMap<String, Value>>>>,
}

#[async_trait]
impl ReadModelStore for InMemoryReadModelStore {
    async fn save(&self, model_type: &str, model_id: &str, data: Value) -> Result<(), DataError> {
        validate_identity(model_type, model_id)?;
        if !data.is_object() {
            return Err(DataError::InvalidQuery(
                "read model must be an object".into(),
            ));
        }
        self.lock()
            .entry(model_type.into())
            .or_default()
            .insert(model_id.into(), data);
        Ok(())
    }

    async fn get(&self, model_type: &str, model_id: &str) -> Result<Option<Value>, DataError> {
        validate_identity(model_type, model_id)?;
        Ok(self
            .lock()
            .get(model_type)
            .and_then(|models| models.get(model_id))
            .cloned())
    }

    async fn query(
        &self,
        model_type: &str,
        query: &ReadModelQuery,
    ) -> Result<Vec<Value>, DataError> {
        query.validate()?;
        let mut values = self
            .lock()
            .get(model_type)
            .into_iter()
            .flat_map(BTreeMap::values)
            .filter(|model| matches_filters(model, &query.filters).unwrap_or(false))
            .cloned()
            .collect::<Vec<_>>();
        if let Some(field) = &query.sort_by {
            let invalid = values
                .iter()
                .any(|value| value.get(field).is_none_or(|item| !sortable(item)));
            if invalid {
                return Err(DataError::InvalidQuery(format!(
                    "sort field {field} is missing or not scalar"
                )));
            }
            values.sort_by(|left, right| {
                let order = compare(
                    left.get(field).expect("validated sort field"),
                    right.get(field).expect("validated sort field"),
                )
                .unwrap_or(Ordering::Equal);
                if query.sort_order == SortOrder::Descending {
                    order.reverse()
                } else {
                    order
                }
            });
        }
        let start = query.page.saturating_sub(1).saturating_mul(query.page_size);
        Ok(values
            .into_iter()
            .skip(start)
            .take(query.page_size)
            .collect())
    }

    async fn delete(&self, model_type: &str, model_id: &str) -> Result<bool, DataError> {
        validate_identity(model_type, model_id)?;
        Ok(self
            .lock()
            .get_mut(model_type)
            .and_then(|models| models.remove(model_id))
            .is_some())
    }

    async fn count(
        &self,
        model_type: &str,
        filters: &BTreeMap<String, Filter>,
    ) -> Result<usize, DataError> {
        self.lock()
            .get(model_type)
            .into_iter()
            .flat_map(BTreeMap::values)
            .try_fold(0_usize, |count, model| {
                Ok(count + usize::from(matches_filters(model, filters)?))
            })
    }
}

impl InMemoryReadModelStore {
    fn lock(&self) -> std::sync::MutexGuard<'_, BTreeMap<String, BTreeMap<String, Value>>> {
        self.models
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
    }
}

#[async_trait]
pub trait Repository<T>: Send + Sync
where
    T: Send + Sync,
{
    async fn save(&self, entity: &T) -> Result<(), DataError>;
    async fn find_by_id(&self, id: &str) -> Result<Option<T>, DataError>;
    async fn delete(&self, id: &str) -> Result<bool, DataError>;
    async fn exists(&self, id: &str) -> Result<bool, DataError>;
}

fn validate_identity(model_type: &str, model_id: &str) -> Result<(), DataError> {
    if model_type.trim().is_empty() || model_id.trim().is_empty() {
        return Err(DataError::InvalidQuery(
            "read model type and id are required".into(),
        ));
    }
    Ok(())
}

fn matches_filters(model: &Value, filters: &BTreeMap<String, Filter>) -> Result<bool, DataError> {
    filters.iter().try_fold(true, |matched, (field, filter)| {
        if !matched {
            return Ok(false);
        }
        model
            .get(field)
            .map_or(Ok(false), |actual| filter.matches(actual))
    })
}

fn sortable(value: &Value) -> bool {
    value.is_number() || value.is_string() || value.is_boolean() || value.is_null()
}

fn compare(left: &Value, right: &Value) -> Result<Ordering, DataError> {
    match (left, right) {
        (Value::Number(left), Value::Number(right)) => left
            .as_f64()
            .zip(right.as_f64())
            .map(|(left, right)| left.total_cmp(&right))
            .ok_or_else(|| DataError::InvalidQuery("numeric comparison failed".into())),
        (Value::String(left), Value::String(right)) => Ok(left.cmp(right)),
        (Value::Bool(left), Value::Bool(right)) => Ok(left.cmp(right)),
        (Value::Null, Value::Null) => Ok(Ordering::Equal),
        _ => Err(DataError::InvalidQuery(
            "filter operands must have matching scalar types".into(),
        )),
    }
}
