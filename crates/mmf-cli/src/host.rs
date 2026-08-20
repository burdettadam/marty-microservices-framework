use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use crate::{
    CliError, DocumentationBundle, GeneratedArtifact, GeneratedProject, ProcessInvocation,
    SourceDocument,
};

pub trait HostEffects {
    fn read_sources(&self, roots: &[PathBuf]) -> Result<Vec<SourceDocument>, CliError>;
    fn write_artifacts(
        &self,
        root: &Path,
        artifacts: &[GeneratedArtifact],
        overwrite: bool,
    ) -> Result<Vec<PathBuf>, CliError>;
    fn run(&self, invocation: &ProcessInvocation) -> Result<ProcessOutput, CliError>;
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ProcessOutput {
    pub status: i32,
    pub stdout: String,
    pub stderr: String,
}

#[derive(Clone, Debug)]
pub struct NativeHost {
    scope: PathBuf,
}

impl NativeHost {
    pub fn new(scope: impl Into<PathBuf>) -> Result<Self, CliError> {
        let scope = scope.into();
        let scope = scope
            .canonicalize()
            .map_err(|error| CliError::Operation(format!("invalid host scope: {error}")))?;
        if scope.parent().is_none() {
            return Err(CliError::InvalidInput(
                "filesystem root cannot be a CLI host scope".into(),
            ));
        }
        Ok(Self { scope })
    }

    pub fn write_project(
        &self,
        project: &GeneratedProject,
        overwrite: bool,
    ) -> Result<Vec<PathBuf>, CliError> {
        project.validate()?;
        self.write_artifacts(&project.root, &project.files, overwrite)
    }

    pub fn write_documentation(
        &self,
        output_dir: &Path,
        bundle: &DocumentationBundle,
        overwrite: bool,
    ) -> Result<Vec<PathBuf>, CliError> {
        bundle.validate()?;
        self.write_artifacts(output_dir, &bundle.artifacts, overwrite)
    }

    fn scoped_path(&self, path: &Path) -> Result<PathBuf, CliError> {
        let resolved = if path.is_absolute() {
            path.to_path_buf()
        } else {
            self.scope.join(path)
        };
        let normalized = lexical_normalize(&resolved)?;
        if !normalized.starts_with(&self.scope) {
            return Err(CliError::InvalidInput(format!(
                "path is outside CLI host scope: {}",
                path.display()
            )));
        }
        Ok(normalized)
    }
}

impl HostEffects for NativeHost {
    fn read_sources(&self, roots: &[PathBuf]) -> Result<Vec<SourceDocument>, CliError> {
        let mut sources = Vec::new();
        for root in roots {
            let root = self.scoped_path(root)?;
            collect_sources(&root, &mut sources)?;
        }
        sources.sort_by(|left, right| left.path.cmp(&right.path));
        Ok(sources)
    }

    fn write_artifacts(
        &self,
        root: &Path,
        artifacts: &[GeneratedArtifact],
        overwrite: bool,
    ) -> Result<Vec<PathBuf>, CliError> {
        let root = self.scoped_path(root)?;
        let mut targets = Vec::with_capacity(artifacts.len());
        for artifact in artifacts {
            if artifact.relative_path.is_absolute()
                || artifact
                    .relative_path
                    .components()
                    .any(|component| matches!(component, std::path::Component::ParentDir))
            {
                return Err(CliError::InvalidInput(format!(
                    "artifact escapes output root: {}",
                    artifact.relative_path.display()
                )));
            }
            let target = self.scoped_path(&root.join(&artifact.relative_path))?;
            if target.exists() && !overwrite {
                return Err(CliError::Conflict(format!(
                    "refusing to overwrite {}",
                    target.display()
                )));
            }
            targets.push((target, artifact));
        }
        let mut written = Vec::with_capacity(targets.len());
        for (target, artifact) in targets {
            if let Some(parent) = target.parent() {
                fs::create_dir_all(parent).map_err(|error| {
                    CliError::Operation(format!("create {}: {error}", parent.display()))
                })?;
            }
            fs::write(&target, artifact.content.as_bytes()).map_err(|error| {
                CliError::Operation(format!("write {}: {error}", target.display()))
            })?;
            written.push(target);
        }
        Ok(written)
    }

    fn run(&self, invocation: &ProcessInvocation) -> Result<ProcessOutput, CliError> {
        invocation.validate()?;
        let mut command = Command::new(&invocation.program);
        command.args(&invocation.arguments);
        if let Some(directory) = &invocation.working_directory {
            command.current_dir(self.scoped_path(directory)?);
        } else {
            command.current_dir(&self.scope);
        }
        command.envs(&invocation.environment);
        let output = command.output().map_err(|error| {
            CliError::ProviderUnavailable(format!("{}: {error}", invocation.program))
        })?;
        Ok(ProcessOutput {
            status: output.status.code().unwrap_or(-1),
            stdout: String::from_utf8_lossy(&output.stdout).into_owned(),
            stderr: String::from_utf8_lossy(&output.stderr).into_owned(),
        })
    }
}

fn collect_sources(path: &Path, sources: &mut Vec<SourceDocument>) -> Result<(), CliError> {
    if path.is_file() {
        if matches!(
            path.extension().and_then(|value| value.to_str()),
            Some("py" | "proto")
        ) {
            let content = fs::read_to_string(path).map_err(|error| {
                CliError::Operation(format!("read {}: {error}", path.display()))
            })?;
            sources.push(SourceDocument {
                path: path.to_path_buf(),
                content,
            });
        }
        return Ok(());
    }
    if !path.is_dir() {
        return Err(CliError::NotFound(format!(
            "source path {}",
            path.display()
        )));
    }
    for entry in fs::read_dir(path)
        .map_err(|error| CliError::Operation(format!("scan {}: {error}", path.display())))?
    {
        let entry = entry.map_err(|error| CliError::Operation(error.to_string()))?;
        let file_type = entry
            .file_type()
            .map_err(|error| CliError::Operation(error.to_string()))?;
        if file_type.is_symlink() {
            continue;
        }
        if file_type.is_dir() {
            let name = entry.file_name();
            if matches!(
                name.to_str(),
                Some(".git" | ".venv" | "target" | "__pycache__")
            ) {
                continue;
            }
            collect_sources(&entry.path(), sources)?;
        } else if file_type.is_file() {
            collect_sources(&entry.path(), sources)?;
        }
    }
    Ok(())
}

fn lexical_normalize(path: &Path) -> Result<PathBuf, CliError> {
    let mut normalized = PathBuf::new();
    for component in path.components() {
        match component {
            std::path::Component::ParentDir => {
                if !normalized.pop() {
                    return Err(CliError::InvalidInput(format!(
                        "path escapes filesystem root: {}",
                        path.display()
                    )));
                }
            }
            std::path::Component::CurDir => {}
            component => normalized.push(component.as_os_str()),
        }
    }
    Ok(normalized)
}
