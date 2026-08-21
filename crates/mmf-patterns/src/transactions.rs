use std::collections::BTreeMap;
use std::sync::Mutex;

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::PatternError;

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TransactionState {
    Started,
    Preparing,
    Prepared,
    Committing,
    Committed,
    Aborting,
    Aborted,
    Failed,
    TimedOut,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct TransactionParticipant {
    pub id: String,
    pub service_name: String,
    pub endpoint: String,
    pub state: TransactionState,
    pub prepared_at_ms: Option<u64>,
    pub committed_at_ms: Option<u64>,
    pub aborted_at_ms: Option<u64>,
    pub error: Option<String>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct DistributedTransaction {
    pub id: String,
    pub coordinator_id: String,
    pub participants: Vec<TransactionParticipant>,
    pub state: TransactionState,
    pub timeout_ms: u64,
    pub created_at_ms: u64,
    pub updated_at_ms: u64,
    #[serde(default)]
    pub context: Value,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ParticipantRegistration {
    pub id: String,
    pub service_name: String,
    pub endpoint: String,
}

#[async_trait]
pub trait TransactionParticipantProvider: Send + Sync {
    async fn prepare(
        &self,
        transaction_id: &str,
        participant: &TransactionParticipant,
        context: &Value,
    ) -> Result<(), PatternError>;
    async fn commit(
        &self,
        transaction_id: &str,
        participant: &TransactionParticipant,
    ) -> Result<(), PatternError>;
    async fn abort(
        &self,
        transaction_id: &str,
        participant: &TransactionParticipant,
    ) -> Result<(), PatternError>;
}

#[derive(Debug, Default)]
pub struct DistributedTransactionCoordinator {
    transactions: Mutex<BTreeMap<String, DistributedTransaction>>,
}

impl DistributedTransactionCoordinator {
    pub fn begin(
        &self,
        transaction_id: impl Into<String>,
        coordinator_id: impl Into<String>,
        participants: Vec<ParticipantRegistration>,
        timeout_ms: u64,
        now_ms: u64,
        context: Value,
    ) -> Result<String, PatternError> {
        let transaction_id = transaction_id.into();
        if transaction_id.trim().is_empty()
            || timeout_ms == 0
            || participants.is_empty()
            || participants.iter().any(|participant| {
                participant.id.trim().is_empty()
                    || participant.service_name.trim().is_empty()
                    || participant.endpoint.trim().is_empty()
            })
        {
            return Err(PatternError::InvalidConfiguration(
                "transaction requires IDs, participants, endpoints, and timeout".to_owned(),
            ));
        }
        let transaction = DistributedTransaction {
            id: transaction_id.clone(),
            coordinator_id: coordinator_id.into(),
            participants: participants
                .into_iter()
                .map(|participant| TransactionParticipant {
                    id: participant.id,
                    service_name: participant.service_name,
                    endpoint: participant.endpoint,
                    state: TransactionState::Started,
                    prepared_at_ms: None,
                    committed_at_ms: None,
                    aborted_at_ms: None,
                    error: None,
                })
                .collect(),
            state: TransactionState::Started,
            timeout_ms,
            created_at_ms: now_ms,
            updated_at_ms: now_ms,
            context,
        };
        let mut transactions = self
            .transactions
            .lock()
            .map_err(|_| PatternError::Operation("transaction store poisoned".to_owned()))?;
        if transactions.contains_key(&transaction_id) {
            return Err(PatternError::Duplicate(transaction_id));
        }
        transactions.insert(transaction_id.clone(), transaction);
        Ok(transaction_id)
    }

    pub async fn prepare(
        &self,
        transaction_id: &str,
        provider: &dyn TransactionParticipantProvider,
        now_ms: u64,
    ) -> Result<bool, PatternError> {
        let transaction = self.transition_and_clone(
            transaction_id,
            TransactionState::Started,
            TransactionState::Preparing,
            now_ms,
        )?;
        let mut results = Vec::with_capacity(transaction.participants.len());
        for participant in &transaction.participants {
            results.push(
                provider
                    .prepare(transaction_id, participant, &transaction.context)
                    .await,
            );
        }
        let mut transactions = self.lock()?;
        let transaction = transactions
            .get_mut(transaction_id)
            .ok_or_else(|| PatternError::Operation("transaction disappeared".to_owned()))?;
        for (participant, result) in transaction.participants.iter_mut().zip(results) {
            match result {
                Ok(()) => {
                    participant.state = TransactionState::Prepared;
                    participant.prepared_at_ms = Some(now_ms);
                }
                Err(error) => {
                    participant.state = TransactionState::Failed;
                    participant.error = Some(error.to_string());
                }
            }
        }
        let success = transaction
            .participants
            .iter()
            .all(|participant| participant.state == TransactionState::Prepared);
        transaction.state = if success {
            TransactionState::Prepared
        } else {
            TransactionState::Failed
        };
        transaction.updated_at_ms = now_ms;
        Ok(success)
    }

    pub async fn commit(
        &self,
        transaction_id: &str,
        provider: &dyn TransactionParticipantProvider,
        now_ms: u64,
    ) -> Result<bool, PatternError> {
        let transaction = self.transition_and_clone(
            transaction_id,
            TransactionState::Prepared,
            TransactionState::Committing,
            now_ms,
        )?;
        let mut results = Vec::with_capacity(transaction.participants.len());
        for participant in &transaction.participants {
            results.push(provider.commit(transaction_id, participant).await);
        }
        self.finish_participant_operation(
            transaction_id,
            results,
            TransactionState::Committed,
            now_ms,
        )
    }

    pub async fn abort(
        &self,
        transaction_id: &str,
        provider: &dyn TransactionParticipantProvider,
        now_ms: u64,
    ) -> Result<bool, PatternError> {
        let transaction = {
            let mut transactions = self.lock()?;
            let transaction = transactions
                .get_mut(transaction_id)
                .ok_or_else(|| PatternError::Operation("unknown transaction".to_owned()))?;
            if transaction.state == TransactionState::Aborted {
                return Ok(true);
            }
            if transaction.state == TransactionState::Committed {
                return Err(PatternError::InvalidTransactionTransition {
                    from: transaction.state,
                    to: TransactionState::Aborting,
                });
            }
            transaction.state = TransactionState::Aborting;
            transaction.updated_at_ms = now_ms;
            transaction.clone()
        };
        let mut results = Vec::with_capacity(transaction.participants.len());
        for participant in &transaction.participants {
            if matches!(
                participant.state,
                TransactionState::Prepared | TransactionState::Failed
            ) {
                results.push(provider.abort(transaction_id, participant).await);
            } else {
                results.push(Ok(()));
            }
        }
        self.finish_participant_operation(
            transaction_id,
            results,
            TransactionState::Aborted,
            now_ms,
        )
    }

    pub fn expire(&self, now_ms: u64) -> Result<Vec<String>, PatternError> {
        let mut transactions = self.lock()?;
        let mut expired = Vec::new();
        for transaction in transactions.values_mut() {
            if !matches!(
                transaction.state,
                TransactionState::Committed
                    | TransactionState::Aborted
                    | TransactionState::TimedOut
            ) && now_ms.saturating_sub(transaction.created_at_ms) >= transaction.timeout_ms
            {
                transaction.state = TransactionState::TimedOut;
                transaction.updated_at_ms = now_ms;
                expired.push(transaction.id.clone());
            }
        }
        Ok(expired)
    }

    pub fn get(
        &self,
        transaction_id: &str,
    ) -> Result<Option<DistributedTransaction>, PatternError> {
        Ok(self.lock()?.get(transaction_id).cloned())
    }

    pub fn statistics(&self) -> Result<BTreeMap<TransactionState, usize>, PatternError> {
        let mut statistics = BTreeMap::new();
        for transaction in self.lock()?.values() {
            *statistics.entry(transaction.state).or_default() += 1;
        }
        Ok(statistics)
    }

    fn transition_and_clone(
        &self,
        transaction_id: &str,
        expected: TransactionState,
        next: TransactionState,
        now_ms: u64,
    ) -> Result<DistributedTransaction, PatternError> {
        let mut transactions = self.lock()?;
        let transaction = transactions
            .get_mut(transaction_id)
            .ok_or_else(|| PatternError::Operation("unknown transaction".to_owned()))?;
        if transaction.state != expected {
            return Err(PatternError::InvalidTransactionTransition {
                from: transaction.state,
                to: next,
            });
        }
        transaction.state = next;
        transaction.updated_at_ms = now_ms;
        Ok(transaction.clone())
    }

    fn finish_participant_operation(
        &self,
        transaction_id: &str,
        results: Vec<Result<(), PatternError>>,
        success_state: TransactionState,
        now_ms: u64,
    ) -> Result<bool, PatternError> {
        let mut transactions = self.lock()?;
        let transaction = transactions
            .get_mut(transaction_id)
            .ok_or_else(|| PatternError::Operation("transaction disappeared".to_owned()))?;
        for (participant, result) in transaction.participants.iter_mut().zip(results) {
            match result {
                Ok(()) => {
                    participant.state = success_state;
                    match success_state {
                        TransactionState::Committed => participant.committed_at_ms = Some(now_ms),
                        TransactionState::Aborted => participant.aborted_at_ms = Some(now_ms),
                        _ => {}
                    }
                }
                Err(error) => {
                    participant.state = TransactionState::Failed;
                    participant.error = Some(error.to_string());
                }
            }
        }
        let success = transaction
            .participants
            .iter()
            .all(|participant| participant.state == success_state);
        transaction.state = if success {
            success_state
        } else {
            TransactionState::Failed
        };
        transaction.updated_at_ms = now_ms;
        Ok(success)
    }

    fn lock(
        &self,
    ) -> Result<std::sync::MutexGuard<'_, BTreeMap<String, DistributedTransaction>>, PatternError>
    {
        self.transactions
            .lock()
            .map_err(|_| PatternError::Operation("transaction store poisoned".to_owned()))
    }
}
