use std::time::Duration;

pub const PURPOSE_MAX_CHARS: usize = 120;

pub const FINAL_OUTPUT_MAX_BYTES: usize = 4 * 1024;

pub const MAX_CONCURRENT_DETAIL_READS: usize = 4;

pub const RUN_BUDGET: Duration = Duration::from_secs(30);

pub const READ_TIMEOUT: Duration = Duration::from_secs(15);

pub fn fleet_tick_planning_allowance(work_items: usize) -> Duration {
    let batches = work_items.div_ceil(4);
    READ_TIMEOUT.saturating_mul(u32::try_from(batches).unwrap_or(u32::MAX))
}

pub const DEFAULT_LIMIT: usize = 100;

pub const MAX_LIMIT: usize = 200;

pub const FIELD_MAX_CHARS: usize = 200;

pub fn cap_field(text: &str) -> String {
    if text.chars().count() <= FIELD_MAX_CHARS {
        return text.to_owned();
    }
    let mut kept: String = text.chars().take(FIELD_MAX_CHARS - 1).collect();
    kept.push('…');
    kept
}
