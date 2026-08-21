use std::collections::{BTreeMap, BTreeSet};

use regex::{Captures, Regex};
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::CliError;

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TemplateFormat {
    #[default]
    Jinja,
    Plain,
    Json,
    Yaml,
    Toml,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum InheritanceMode {
    Extend,
    Override,
    Merge,
    Compose,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct TemplateContext {
    #[serde(default)]
    pub variables: BTreeMap<String, Value>,
    #[serde(default)]
    pub globals: BTreeMap<String, Value>,
}

impl TemplateContext {
    #[must_use]
    pub fn with(mut self, name: impl Into<String>, value: impl Into<Value>) -> Self {
        self.variables.insert(name.into(), value.into());
        self
    }

    fn get(&self, name: &str) -> Option<&Value> {
        self.variables.get(name).or_else(|| self.globals.get(name))
    }
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct TemplateSpec {
    pub name: String,
    #[serde(default)]
    pub format: TemplateFormat,
    pub inheritance_mode: Option<InheritanceMode>,
    pub parent_template: Option<String>,
    #[serde(default)]
    pub includes: Vec<String>,
    #[serde(default)]
    pub variables: BTreeMap<String, Value>,
    #[serde(default)]
    pub required_variables: Vec<String>,
    #[serde(default)]
    pub optional_variables: Vec<String>,
    #[serde(default)]
    pub conditions: BTreeMap<String, bool>,
    #[serde(default)]
    pub transformations: Vec<String>,
}

impl TemplateSpec {
    pub fn validate(&self) -> Result<(), CliError> {
        if self.name.trim().is_empty() {
            return Err(CliError::InvalidInput("template name is required".into()));
        }
        let required = self.required_variables.iter().collect::<BTreeSet<_>>();
        let optional = self.optional_variables.iter().collect::<BTreeSet<_>>();
        if required.intersection(&optional).next().is_some() {
            return Err(CliError::InvalidInput(
                "template variable cannot be both required and optional".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Default)]
pub struct TemplateEngine {
    templates: BTreeMap<String, String>,
}

impl TemplateEngine {
    #[must_use]
    pub fn new(templates: BTreeMap<String, String>) -> Self {
        Self { templates }
    }

    pub fn register(
        &mut self,
        name: impl Into<String>,
        content: impl Into<String>,
    ) -> Result<(), CliError> {
        let name = name.into();
        if name.trim().is_empty() || name.contains("..") {
            return Err(CliError::InvalidInput("template name is invalid".into()));
        }
        if self
            .templates
            .insert(name.clone(), content.into())
            .is_some()
        {
            return Err(CliError::Conflict(format!(
                "template already registered: {name}"
            )));
        }
        Ok(())
    }

    pub fn render(
        &self,
        template_name: &str,
        context: &TemplateContext,
        spec: Option<&TemplateSpec>,
    ) -> Result<String, CliError> {
        let mut effective = context.clone();
        if let Some(spec) = spec {
            spec.validate()?;
            for (name, value) in &spec.variables {
                effective
                    .variables
                    .entry(name.clone())
                    .or_insert_with(|| value.clone());
            }
            for (name, value) in &spec.conditions {
                effective
                    .variables
                    .entry(name.clone())
                    .or_insert(Value::Bool(*value));
            }
            let missing = spec
                .required_variables
                .iter()
                .filter(|name| effective.get(name).is_none())
                .cloned()
                .collect::<Vec<_>>();
            if !missing.is_empty() {
                return Err(CliError::InvalidInput(format!(
                    "missing required template variables: {}",
                    missing.join(", ")
                )));
            }
        }
        let source = self
            .templates
            .get(template_name)
            .ok_or_else(|| CliError::NotFound(format!("template {template_name}")))?;
        let mut rendered = self.expand_includes(source, 0)?;
        rendered = expand_macros(&rendered)?;
        rendered = expand_conditionals(&rendered, &effective)?;
        rendered = expand_loops(&rendered, &effective)?;
        rendered = expand_variables(&rendered, &effective, true)?;
        Ok(rendered)
    }

    pub fn compose(
        &self,
        base: &str,
        mixins: &[String],
        context: &TemplateContext,
    ) -> Result<String, CliError> {
        let mut output = self.render(base, context, None)?;
        for mixin in mixins {
            output.push('\n');
            output.push_str(&self.render(mixin, context, None)?);
        }
        Ok(output)
    }

    fn expand_includes(&self, source: &str, depth: usize) -> Result<String, CliError> {
        if depth > 16 {
            return Err(CliError::InvalidInput(
                "template include depth exceeded".into(),
            ));
        }
        let expression = Regex::new(r#"\{%\s*include\s+[\"']([^\"']+)[\"']\s*%\}"#)
            .map_err(|error| CliError::Operation(error.to_string()))?;
        let mut output = source.to_owned();
        while let Some(captures) = expression.captures(&output) {
            let whole = captures.get(0).expect("include expression has whole match");
            let name = captures
                .get(1)
                .expect("include expression has name")
                .as_str();
            let included = self
                .templates
                .get(name)
                .ok_or_else(|| CliError::NotFound(format!("included template {name}")))?;
            let included = self.expand_includes(included, depth + 1)?;
            output.replace_range(whole.range(), &included);
        }
        Ok(output)
    }
}

fn expand_conditionals(source: &str, context: &TemplateContext) -> Result<String, CliError> {
    let expression = Regex::new(r"(?s)\{%\s*if\s+(\w+)\s*%\}(.*?)\{%\s*endif\s*%\}")
        .map_err(|error| CliError::Operation(error.to_string()))?;
    Ok(expression
        .replace_all(source, |captures: &Captures<'_>| {
            if context.get(&captures[1]).is_some_and(value_is_truthy) {
                captures[2].to_owned()
            } else {
                String::new()
            }
        })
        .into_owned())
}

fn expand_loops(source: &str, context: &TemplateContext) -> Result<String, CliError> {
    let expression = Regex::new(r"(?s)\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?)\{%\s*endfor\s*%\}")
        .map_err(|error| CliError::Operation(error.to_string()))?;
    Ok(expression
        .replace_all(source, |captures: &Captures<'_>| {
            context
                .get(&captures[2])
                .and_then(Value::as_array)
                .map_or_else(String::new, |items| {
                    items
                        .iter()
                        .map(|item| {
                            let mut scoped = context.clone();
                            scoped
                                .variables
                                .insert(captures[1].to_owned(), item.clone());
                            expand_variables(&captures[3], &scoped, false).unwrap_or_default()
                        })
                        .collect()
                })
        })
        .into_owned())
}

fn expand_macros(source: &str) -> Result<String, CliError> {
    let definition =
        Regex::new(r"(?s)\{%\s*macro\s+(\w+)\(([^)]*)\)\s*%\}(.*?)\{%\s*endmacro\s*%\}")
            .map_err(|error| CliError::Operation(error.to_string()))?;
    let mut macros = BTreeMap::<String, (Vec<String>, String)>::new();
    for captures in definition.captures_iter(source) {
        macros.insert(
            captures[1].to_owned(),
            (
                captures[2]
                    .split(',')
                    .map(str::trim)
                    .filter(|value| !value.is_empty())
                    .map(str::to_owned)
                    .collect(),
                captures[3].to_owned(),
            ),
        );
    }
    let without_definitions = definition.replace_all(source, "").into_owned();
    let call = Regex::new(r"\{\{\s*(\w+)\(([^)]*)\)\s*\}\}")
        .map_err(|error| CliError::Operation(error.to_string()))?;
    Ok(call
        .replace_all(&without_definitions, |captures: &Captures<'_>| {
            let Some((parameters, body)) = macros.get(&captures[1]) else {
                return captures[0].to_owned();
            };
            let arguments = split_arguments(&captures[2]);
            let mut expanded = body.clone();
            for (parameter, argument) in parameters.iter().zip(arguments) {
                expanded = expanded.replace(&format!("{{{{{parameter}}}}}"), &argument);
                expanded = expanded.replace(&format!("{{{{ {parameter} }}}}"), &argument);
            }
            expanded
        })
        .into_owned())
}

fn expand_variables(
    source: &str,
    context: &TemplateContext,
    strict: bool,
) -> Result<String, CliError> {
    let expression = Regex::new(r"\{\{\s*([A-Za-z_]\w*)(?:\|([A-Za-z_-]+))?\s*\}\}")
        .map_err(|error| CliError::Operation(error.to_string()))?;
    let mut missing = BTreeSet::new();
    let output = expression
        .replace_all(source, |captures: &Captures<'_>| {
            let Some(value) = context.get(&captures[1]) else {
                missing.insert(captures[1].to_owned());
                return String::new();
            };
            let raw = value_to_string(value);
            captures.get(2).map_or(raw.clone(), |filter| {
                apply_filter(filter.as_str(), &raw).unwrap_or(raw)
            })
        })
        .into_owned();
    if strict && !missing.is_empty() {
        return Err(CliError::InvalidInput(format!(
            "unknown template variables: {}",
            missing.into_iter().collect::<Vec<_>>().join(", ")
        )));
    }
    Ok(output)
}

fn apply_filter(filter: &str, value: &str) -> Option<String> {
    match filter {
        "slug" | "kebab" => Some(words(value).join("-")),
        "snake" => Some(words(value).join("_")),
        "pascal" => Some(
            words(value)
                .iter()
                .map(|word| {
                    let mut characters = word.chars();
                    characters.next().map_or_else(String::new, |first| {
                        format!("{}{}", first.to_ascii_uppercase(), characters.as_str())
                    })
                })
                .collect(),
        ),
        "upper" => Some(value.to_uppercase()),
        "lower" => Some(value.to_lowercase()),
        _ => None,
    }
}

fn words(value: &str) -> Vec<String> {
    value
        .split(|character: char| !character.is_ascii_alphanumeric())
        .filter(|word| !word.is_empty())
        .map(str::to_lowercase)
        .collect()
}

fn value_to_string(value: &Value) -> String {
    value
        .as_str()
        .map_or_else(|| value.to_string(), str::to_owned)
}

fn value_is_truthy(value: &Value) -> bool {
    match value {
        Value::Bool(value) => *value,
        Value::Number(value) => value.as_f64().is_some_and(|value| value != 0.0),
        Value::String(value) => {
            matches!(value.to_lowercase().as_str(), "true" | "1" | "yes" | "on")
        }
        Value::Array(value) => !value.is_empty(),
        Value::Object(value) => !value.is_empty(),
        Value::Null => false,
    }
}

fn split_arguments(arguments: &str) -> Vec<String> {
    arguments
        .split(',')
        .map(str::trim)
        .map(|argument| argument.trim_matches(['\'', '"']).to_owned())
        .filter(|argument| !argument.is_empty())
        .collect()
}
