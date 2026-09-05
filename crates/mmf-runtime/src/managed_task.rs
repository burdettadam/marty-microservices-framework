//! Owned async operation cancellation followed by awaited resource cleanup.
//!
//! `join` acknowledges completion only after the operation has exited (including
//! cancellation unwinding) and cleanup has finished. Cancellation never aborts
//! cleanup. Operation and cleanup failures remain separate, so neither is lost.
//! Callers must own their operation's children; arbitrary detached tasks are not
//! discovered or joined by this owner.

use std::{convert::Infallible, error::Error, fmt, future::Future};

use tokio::{sync::watch, task::JoinHandle};

#[derive(Debug, Eq, PartialEq)]
pub enum TaskOutcome<T, E> {
    Completed(T),
    Failed(E),
    Cancelled,
    Panicked,
}

#[derive(Debug, Eq, PartialEq)]
pub enum CleanupOutcome<E> {
    Completed,
    Failed(E),
    Cancelled,
    Panicked,
}

#[derive(Debug, Eq, PartialEq)]
pub struct TaskCompletion<T, E, C = Infallible> {
    pub outcome: TaskOutcome<T, E>,
    pub cleanup: CleanupOutcome<C>,
}

/// Failure to observe the supervisor, not evidence of successful cleanup.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TaskJoinError {
    SupervisorCancelled,
    SupervisorPanicked,
}

impl fmt::Display for TaskJoinError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            Self::SupervisorCancelled => "managed task supervisor was cancelled",
            Self::SupervisorPanicked => "managed task supervisor panicked",
        })
    }
}

impl Error for TaskJoinError {}

/// A cancellation request is not a completion acknowledgment; await `join`.
#[derive(Clone)]
pub struct TaskCancellation(watch::Sender<bool>);

impl TaskCancellation {
    /// Returns whether the operation owner still accepts requests. An operation
    /// that completes concurrently can win the race. Once cleanup starts, this
    /// returns false: cleanup cannot be cancelled through this handle.
    #[must_use]
    pub fn cancel(&self) -> bool {
        self.0.send(true).is_ok()
    }
}

/// An initialized resource owner whose completion includes asynchronous cleanup.
///
/// Dropping this handle (including dropping an in-progress `join` future)
/// requests cancellation but cannot synchronously await cleanup. The supervisor
/// continues on the runtime; use `cancel` followed by `join` when acknowledgment
/// matters. Keep the Tokio runtime alive until `join` completes. Runtime
/// shutdown, process abort and host failure cannot promise async cleanup.
pub struct ManagedTask<T, E, C = Infallible> {
    cancellation: TaskCancellation,
    supervisor: JoinHandle<TaskCompletion<T, E, C>>,
}

impl<T: Send + 'static, E: Send + 'static, C: Send + 'static> ManagedTask<T, E, C> {
    /// Start an operation and retain its initialized resource cleanup owner.
    /// Neither errors nor panic payloads are logged by this primitive.
    /// The process panic hook still applies to panicking user code.
    ///
    /// ```
    /// use std::convert::Infallible;
    /// use mmf_runtime::managed_task::{ManagedTask, TaskOutcome, CleanupOutcome};
    /// # #[tokio::main]
    /// # async fn main() {
    /// let task = ManagedTask::spawn(
    ///     async { Ok::<_, &'static str>(42) },
    ///     || async { Ok::<(), Infallible>(()) },
    /// );
    /// let completion = task.join().await.expect("supervisor completed");
    /// assert_eq!(completion.outcome, TaskOutcome::Completed(42));
    /// assert_eq!(completion.cleanup, CleanupOutcome::Completed);
    /// # }
    /// ```
    ///
    /// # Panics
    /// Panics if called outside a running Tokio runtime.
    pub fn spawn<W, D, DF>(operation: W, cleanup: D) -> Self
    where
        W: Future<Output = Result<T, E>> + Send + 'static,
        D: FnOnce() -> DF + Send + 'static,
        DF: Future<Output = Result<(), C>> + Send + 'static,
    {
        let (cancel_tx, mut cancel_rx) = watch::channel(false);
        let supervisor = tokio::spawn(async move {
            let pre_cancelled = *cancel_rx.borrow();
            let mut operation = tokio::spawn(async move {
                if pre_cancelled {
                    // Even an unpolled future's destructor can panic. Keep
                    // that unwinding inside the observed operation task.
                    drop(operation);
                    None
                } else {
                    Some(operation.await)
                }
            });
            let result = tokio::select! {
                biased;
                result = &mut operation => result,
                _ = cancel_rx.changed() => {
                    operation.abort();
                    // Abort requests alone are insufficient: await the
                    // operation's destructor before disposing its resources.
                    operation.await
                }
            };
            let outcome = match result {
                Ok(Some(Ok(value))) => TaskOutcome::Completed(value),
                Ok(Some(Err(error))) => TaskOutcome::Failed(error),
                Ok(None) => TaskOutcome::Cancelled,
                Err(error) if error.is_cancelled() => TaskOutcome::Cancelled,
                Err(_) => TaskOutcome::Panicked,
            };
            drop(cancel_rx);
            // Invoke the factory inside the supervised cleanup task too, so a
            // synchronous factory panic cannot erase the operation's outcome.
            let cleanup = match tokio::spawn(async move { cleanup().await }).await {
                Ok(Ok(())) => CleanupOutcome::Completed,
                Ok(Err(error)) => CleanupOutcome::Failed(error),
                Err(error) if error.is_cancelled() => CleanupOutcome::Cancelled,
                Err(_) => CleanupOutcome::Panicked,
            };
            TaskCompletion { outcome, cleanup }
        });
        Self {
            cancellation: TaskCancellation(cancel_tx),
            supervisor,
        }
    }

    #[must_use]
    pub fn cancellation_handle(&self) -> TaskCancellation {
        self.cancellation.clone()
    }

    /// Request cancellation; await `join` for operation and cleanup completion.
    #[must_use]
    pub fn cancel(&self) -> bool {
        self.cancellation.cancel()
    }

    /// Await both phases. Inspect both returned outcomes before declaring the
    /// resource disposed or the operation successful.
    pub async fn join(mut self) -> Result<TaskCompletion<T, E, C>, TaskJoinError> {
        (&mut self.supervisor).await.map_err(|error| {
            if error.is_cancelled() {
                TaskJoinError::SupervisorCancelled
            } else {
                TaskJoinError::SupervisorPanicked
            }
        })
    }
}

impl<T, E, C> Drop for ManagedTask<T, E, C> {
    fn drop(&mut self) {
        let _ = self.cancellation.cancel();
    }
}
