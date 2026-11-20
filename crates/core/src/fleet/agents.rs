use super::model::{
    ListOutcome, MergedPr, NonEmpty, Number, Outcome, PullRequest, Read, ReadKind, Reviewer,
    Thread, Unplaced, UnplacedReason, WorkedOut,
};

pub const REVIEWER_REASON: &str = "no verified chain places a reviewer in version 1";

pub fn reviewer() -> Reviewer {
    Reviewer::Undefined(NonEmpty::new(REVIEWER_REASON).expect("the reason is not empty"))
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Placements {
    chain: WorkedOut<Chain>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct Chain {
    builders: Vec<(Number, NonEmpty)>,
    unplaced: Vec<Unplaced>,
}

impl Placements {
    pub fn builder(&self, ticket: Number) -> WorkedOut<Option<NonEmpty>> {
        match &self.chain {
            WorkedOut::Known(chain) => WorkedOut::Known(
                chain
                    .builders
                    .iter()
                    .find(|(placed_on, _)| *placed_on == ticket)
                    .map(|(_, thread)| thread.clone()),
            ),
            WorkedOut::Unread(ids) => WorkedOut::Unread(ids.clone()),
        }
    }

    pub fn unplaced(&self) -> WorkedOut<Vec<Unplaced>> {
        match &self.chain {
            WorkedOut::Known(chain) => WorkedOut::Known(chain.unplaced.clone()),
            WorkedOut::Unread(ids) => WorkedOut::Unread(ids.clone()),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Needed {
    Projects,
    Threads,
    SubIssues(Number),
    PrDiscovery(Number),
    Workspace(NonEmpty),
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum RecordError {
    Missing(Needed),
    Repeated(Needed),
}

pub fn place(spec: Number, reads: &[Read]) -> Result<Placements, RecordError> {
    let found = Found::on(spec, reads)?;
    let mut unread: Vec<usize> = found.required.clone();
    unread.retain(|&at| !is_complete(&reads[at].kind));
    unread.sort_unstable();
    unread.dedup();
    let chain = match found.chain() {
        Some(chain) if unread.is_empty() => WorkedOut::Known(chain),
        _ => WorkedOut::Unread(unread.iter().map(|&at| reads[at].id).collect()),
    };
    Ok(Placements { chain })
}

struct Found<'a> {
    required: Vec<usize>,
    prs: Vec<(Number, &'a Outcome<Option<PullRequest>>)>,
    threads: Vec<(&'a NonEmpty, Branch<'a>)>,
}

enum Branch<'a> {
    Listed(Option<&'a NonEmpty>),
    Workspace(&'a Outcome<NonEmpty>),
}

impl<'a> Found<'a> {
    fn on(spec: Number, reads: &'a [Read]) -> Result<Self, RecordError> {
        let mut required = Vec::new();

        let (at, tickets) = one(reads, Needed::SubIssues(spec), |kind| match kind {
            ReadKind::SubIssues { spec: s, outcome } if *s == spec => Some(outcome),
            _ => None,
        })?;
        required.push(at);
        let mut prs = Vec::new();
        for &ticket in listed(tickets) {
            let (at, pr) = one(reads, Needed::PrDiscovery(ticket), |kind| match kind {
                ReadKind::PrDiscovery { issue, outcome } if *issue == ticket => Some(outcome),
                _ => None,
            })?;
            required.push(at);
            prs.push((ticket, pr));
        }

        let (at, _) = one(reads, Needed::Projects, |kind| match kind {
            ReadKind::Projects { outcome } => Some(outcome),
            _ => None,
        })?;
        required.push(at);
        let (at, listed_threads) = one(reads, Needed::Threads, |kind| match kind {
            ReadKind::Threads { outcome } => Some(outcome),
            _ => None,
        })?;
        required.push(at);
        let mut threads = Vec::new();
        for row in listed(listed_threads) {
            match row {
                Thread::Local { thread, branch, .. } => {
                    threads.push((thread, Branch::Listed(branch.as_ref())));
                }
                Thread::Cloud { thread, .. } => {
                    let need = Needed::Workspace(thread.clone());
                    let (at, branch) = one(reads, need, |kind| match kind {
                        ReadKind::Workspace { thread: t, outcome } if t == thread => Some(outcome),
                        _ => None,
                    })?;
                    required.push(at);
                    threads.push((thread, Branch::Workspace(branch)));
                }
            }
        }

        Ok(Self {
            required,
            prs,
            threads,
        })
    }

    fn chain(&self) -> Option<Chain> {
        let mut heads: Vec<(Number, &str, &[Number])> = Vec::new();
        for (ticket, pr) in &self.prs {
            let Outcome::Complete { value: pr } = pr else {
                return None;
            };
            if let Some(PullRequest::Open(fields) | PullRequest::Merged(MergedPr { fields, .. })) =
                pr
            {
                heads.push((
                    *ticket,
                    fields.head_branch.as_str(),
                    fields.closes.as_slice(),
                ));
            }
        }
        let mut branches: Vec<Option<&str>> = Vec::new();
        for (_, branch) in &self.threads {
            branches.push(match branch {
                Branch::Listed(branch) => branch.map(NonEmpty::as_str),
                Branch::Workspace(Outcome::Complete { value }) => Some(value.as_str()),
                Branch::Workspace(Outcome::Failed(_)) => return None,
            });
        }

        let mut chain = Chain {
            builders: Vec::new(),
            unplaced: Vec::new(),
        };
        for (i, (thread, _)) in self.threads.iter().enumerate() {
            let reason = match branches[i] {
                None => UnplacedReason::NoBranch,
                Some(branch) if shared(&branches, i, branch) => UnplacedReason::SharedBranch,
                Some(branch) => {
                    let headed: Vec<&(Number, &str, &[Number])> = heads
                        .iter()
                        .filter(|(_, head, _)| *head == branch)
                        .collect();
                    match headed.as_slice() {
                        [] => UnplacedReason::NoPullRequest,
                        [(ticket, _, closes)] if *closes == [*ticket] => {
                            chain.builders.push((*ticket, (*thread).clone()));
                            continue;
                        }
                        [_] => UnplacedReason::SeveralIssues,
                        _ => UnplacedReason::SeveralTickets,
                    }
                }
            };
            chain.unplaced.push(Unplaced {
                thread: (*thread).clone(),
                reason,
            });
        }
        Some(chain)
    }
}

fn shared(branches: &[Option<&str>], i: usize, branch: &str) -> bool {
    branches
        .iter()
        .enumerate()
        .any(|(j, other)| j != i && *other == Some(branch))
}

fn one<'a, T>(
    reads: &'a [Read],
    need: Needed,
    pick: impl Fn(&'a ReadKind) -> Option<&'a T>,
) -> Result<(usize, &'a T), RecordError> {
    let mut found = reads
        .iter()
        .enumerate()
        .filter_map(|(at, read)| pick(&read.kind).map(|outcome| (at, outcome)));
    match (found.next(), found.next()) {
        (Some(only), None) => Ok(only),
        (None, _) => Err(RecordError::Missing(need)),
        (Some(_), Some(_)) => Err(RecordError::Repeated(need)),
    }
}

fn listed<T>(outcome: &ListOutcome<T>) -> &[T] {
    match outcome {
        ListOutcome::Complete { value } | ListOutcome::Partial { value, .. } => value,
        ListOutcome::Failed(_) => &[],
    }
}

fn is_complete(kind: &ReadKind) -> bool {
    fn whole<T>(outcome: &Outcome<T>) -> bool {
        matches!(outcome, Outcome::Complete { .. })
    }
    fn whole_list<T>(outcome: &ListOutcome<T>) -> bool {
        matches!(outcome, ListOutcome::Complete { .. })
    }
    match kind {
        ReadKind::Version { outcome, .. } => whole(outcome),
        ReadKind::Repository { outcome } => whole(outcome),
        ReadKind::SpecList { outcome } => whole_list(outcome),
        ReadKind::Issue { outcome, .. } => whole(outcome),
        ReadKind::SubIssues { outcome, .. } => whole_list(outcome),
        ReadKind::BlockedBy { outcome, .. } => whole_list(outcome),
        ReadKind::PrDiscovery { outcome, .. } => whole(outcome),
        ReadKind::Checks { outcome, .. } => whole_list(outcome),
        ReadKind::Comments { outcome, .. } => whole(outcome),
        ReadKind::MergeReadback { outcome, .. } => whole(outcome),
        ReadKind::Projects { outcome } => whole_list(outcome),
        ReadKind::Threads { outcome } => whole_list(outcome),
        ReadKind::Workspace { outcome, .. } => whole(outcome),
    }
}
