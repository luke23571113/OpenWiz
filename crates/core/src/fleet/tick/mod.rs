mod rules;
pub use rules::{AgentRule, MergeRule, RequiredCheck, Rules};

mod action;
mod input;
pub use action::*;
pub use input::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PlanError {
    RepositoryUnread,
    SpecsUnread,
    InvalidSnapshot,
}

mod planner;
pub use planner::plan;
