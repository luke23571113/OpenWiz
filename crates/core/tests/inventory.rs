//! The inventory's core rules, through `openwiz_core::ops::list` and a
//! scripted in-process source, with no adapter, client or `room-cli`:
//! duplicate and conflicting rows (P1), paging, detail reads and the run
//! budget (P5), the row cap (P7) and visibility (P11). Moved here from
//! `tests/proof` by #805; the proof cases that cross crates stay there.

#[path = "support/scripted.rs"]
mod scripted;

use std::sync::atomic::Ordering;
use std::time::{Duration, Instant};

use openwiz_core::envelope::{Completeness, GapKind};
use openwiz_core::limits::{FIELD_MAX_CHARS, MAX_CONCURRENT_DETAIL_READS, MAX_LIMIT, RUN_BUDGET};
use openwiz_core::model::{Fact, Grouping, ProjectId};
use openwiz_core::ops::{Detail, ListRequest, OpError};
use openwiz_core::source::ProjectRecord;

use scripted::*;

fn page(offset: usize, limit: usize, detail: Detail) -> ListRequest {
    ListRequest {
        detail,
        offset,
        limit,
        ..ListRequest::default()
    }
}

#[test]
fn a_session_listed_twice_appears_once_with_a_gap() {
    let mut records = ScriptedSource::new(3).records;
    records.push(records[0].clone());
    let source = ScriptedSource::with_records(records);
    let env = list_scripted(&source, &ListRequest::default()).expect("list");
    let listed = ids(&env);
    assert_eq!(
        listed.iter().filter(|id| *id == "thr_syn_0001").count(),
        1,
        "{listed:?}"
    );
    assert_eq!(listed.len(), 3);
    reconcile(env.coverage.counts.as_ref().expect("counts"));
    assert!(
        env.gaps
            .iter()
            .any(|g| g.subject.as_deref() == Some("thr_syn_0001")
                || g.detail.contains("thr_syn_0001")),
        "the duplicate has a gap: {:?}",
        env.gaps
    );
}

#[test]
fn conflicting_unknown_session_statuses_stay_unknown_in_either_order() {
    let known = Fact::Known("idle".to_owned());
    let missing = Fact::Unknown("not reported".to_owned());
    let unreadable = Fact::Unknown("unreadable".to_owned());
    for statuses in [vec![known, missing.clone()], vec![missing, unreadable]] {
        for reverse in [false, true] {
            let mut records: Vec<_> = statuses
                .iter()
                .map(|status| {
                    let mut record = scripted_record(1);
                    record.status = status.clone();
                    record
                })
                .collect();
            if reverse {
                records.reverse();
            }
            let source = ScriptedSource::with_records(records);
            for request in [ListRequest::default(), long()] {
                let env = list_scripted(&source, &request).expect("list");
                assert_eq!(env.data.sessions.len(), 1);
                assert_eq!(
                    unknown_reason(&env.data.sessions[0].status),
                    "session list returned conflicting status facts for this session id"
                );
                assert_eq!(env.coverage.state, Completeness::Partial);
                assert_eq!(env.gaps.len(), 2);
                reconcile(env.coverage.counts.as_ref().expect("counts"));
            }
        }
    }
}

#[test]
fn conflicting_project_names_are_unknown_with_partial_coverage_in_either_order() {
    let a = Fact::Known("Synthetic project A".to_owned());
    let b = Fact::Known("Synthetic project B".to_owned());
    let unknown = Fact::Unknown("name not reported".to_owned());
    let prefix = "x".repeat(FIELD_MAX_CHARS);
    for names in [
        vec![a.clone(), b.clone()],
        vec![a.clone(), unknown.clone()],
        vec![unknown, Fact::Unknown("name unreadable".to_owned())],
        vec![a.clone(), b, a],
        vec![
            Fact::Known(format!("{prefix}A")),
            Fact::Known(format!("{prefix}B")),
        ],
    ] {
        let check = |names: Vec<Fact<String>>| {
            let mut projects: Vec<_> = names
                .into_iter()
                .map(|name| ProjectRecord {
                    id: ProjectId("prj_syn_0001".to_owned()),
                    name,
                })
                .collect();
            projects.push(ProjectRecord {
                id: ProjectId("prj_syn_0002".to_owned()),
                name: Fact::Known("Unaffected project".to_owned()),
            });
            let mut source = ScriptedSource::new(3).with_projects(projects);
            source.records[2].project_id = Fact::Known(ProjectId("prj_syn_0002".to_owned()));
            let env = list_scripted(&source, &ListRequest::default()).expect("honest list");
            assert_eq!(ids(&env), ["thr_syn_0001", "thr_syn_0002", "thr_syn_0003"]);
            let counts = env.coverage.counts.as_ref().expect("counts");
            assert_eq!(
                (
                    counts.listed,
                    counts.matched,
                    counts.shown,
                    counts.unreadable
                ),
                (3, 3, 3, 0)
            );
            reconcile(counts);
            assert_eq!(env.coverage.state, Completeness::Partial);
            assert_eq!(env.gaps.len(), 1);
            assert_eq!(env.gaps[0].kind, GapKind::Malformed);
            assert_eq!(env.gaps[0].subject.as_deref(), Some("prj_syn_0001"));
            assert!(env.gaps[0].detail.contains("conflicting"));
            for row in &env.data.sessions[..2] {
                match &row.group {
                    Grouping::Project {
                        id,
                        name: Fact::Unknown(reason),
                    } => {
                        assert_eq!(id.0, "prj_syn_0001");
                        assert!(reason.contains("conflicting"), "{reason}");
                    }
                    other => panic!("conflicting project name must be unknown: {other:?}"),
                }
            }
            assert_eq!(
                env.data.sessions[2].group,
                Grouping::Project {
                    id: ProjectId("prj_syn_0002".to_owned()),
                    name: Fact::Known("Unaffected project".to_owned()),
                }
            );
            env
        };
        let forward = check(names.clone());
        let reverse = check(names.into_iter().rev().collect());
        assert_eq!(
            forward, reverse,
            "project row order must not change inventory"
        );
    }
}

#[test]
fn two_conflicting_project_ids_merge_into_one_gap_in_id_order() {
    let row = |id: &str, name: &str| ProjectRecord {
        id: ProjectId(id.to_owned()),
        name: Fact::Known(name.to_owned()),
    };
    let check = |rows: Vec<ProjectRecord>| {
        let mut source = ScriptedSource::new(2).with_projects(rows);
        source.records[1].project_id = Fact::Known(ProjectId("prj_syn_0002".to_owned()));
        let env = list_scripted(&source, &ListRequest::default()).expect("honest list");
        assert_eq!(ids(&env), ["thr_syn_0001", "thr_syn_0002"]);
        assert_eq!(env.coverage.state, Completeness::Partial);
        assert_eq!(env.gaps.len(), 1);
        assert_eq!(env.gaps[0].kind, GapKind::Malformed);
        assert_eq!(
            env.gaps[0].subject.as_deref(),
            Some("2 subjects: prj_syn_0001, prj_syn_0002")
        );
        env
    };
    let rows = vec![
        row("prj_syn_0001", "Conflicting A"),
        row("prj_syn_0002", "Conflicting B"),
        row("prj_syn_0001", "Conflicting A again"),
        row("prj_syn_0002", "Conflicting B again"),
    ];
    let forward = check(rows.clone());
    let reverse = check(rows.into_iter().rev().collect());
    assert_eq!(
        forward, reverse,
        "project row order must not change the merged gap's subjects"
    );
}

#[test]
fn identical_project_name_facts_keep_their_single_row_behavior() {
    for name in [
        Fact::Known("Synthetic project".to_owned()),
        Fact::Unknown("name not reported".to_owned()),
    ] {
        for count in [1, 3] {
            let project = ProjectRecord {
                id: ProjectId("prj_syn_0001".to_owned()),
                name: name.clone(),
            };
            let source = ScriptedSource::new(1).with_projects(vec![project; count]);
            let env = list_scripted(&source, &ListRequest::default()).expect("list");
            assert_eq!(ids(&env), ["thr_syn_0001"]);
            assert_eq!(env.coverage.state, Completeness::Complete);
            assert!(env.gaps.is_empty());
            assert_eq!(
                env.data.sessions[0].group,
                Grouping::Project {
                    id: ProjectId("prj_syn_0001".to_owned()),
                    name: name.clone(),
                }
            );
            reconcile(env.coverage.counts.as_ref().expect("counts"));
        }
    }
}

#[test]
fn limit_and_offset_select_the_page() {
    let source = ScriptedSource::new(25);
    let env = list_scripted(&source, &page(20, 10, Detail::Short)).expect("list");
    assert_eq!(env.data.sessions.len(), 5);
    let c = env.coverage.counts.as_ref().expect("counts");
    assert_eq!((c.matched, c.offset, c.limit, c.shown), (25, 20, 10, 5));

    let past_the_end = list_scripted(&source, &page(40, 10, Detail::Short)).expect("list");
    assert!(past_the_end.data.sessions.is_empty());
    assert_eq!(
        past_the_end.coverage.counts.as_ref().expect("counts").shown,
        0
    );
}

#[test]
fn short_listing_makes_no_detail_reads() {
    let source = ScriptedSource::new(10);
    list_scripted(&source, &page(0, 10, Detail::Short)).expect("list");
    assert!(source.detail_ids().is_empty(), "ls must not read details");
}

#[test]
fn at_most_four_detail_reads_run_at_once() {
    let source = ScriptedSource::new(20).with_delay(Duration::from_millis(100));
    list_scripted(&source, &page(0, 20, Detail::Long)).expect("list");
    let max = source.max_in_flight.load(Ordering::SeqCst);
    assert!(max >= 1, "details were read");
    assert_eq!(MAX_CONCURRENT_DETAIL_READS, 4, "the approved limit");
    assert!(max <= 4, "{max} detail reads ran at once");
}

#[test]
fn the_budget_bounds_the_whole_run() {
    // Five rounds of four reads at 200 ms each against a 300 ms budget
    // (#1260: one fifth of the earlier 1 s and 1.5 s, the same overrun).
    let source = ScriptedSource::new(20).with_delay(Duration::from_millis(200));
    let budget = Duration::from_millis(300);
    let started = Instant::now();
    let env = list_scripted(
        &source,
        &ListRequest {
            budget,
            ..page(0, 20, Detail::Long)
        },
    )
    .expect("honest partial list");
    assert!(
        started.elapsed() < budget + Duration::from_secs(1),
        "took {:?}",
        started.elapsed()
    );
    assert_eq!(env.coverage.state, Completeness::Partial);
    assert_eq!(
        env.data.sessions.len(),
        20,
        "unenriched rows are still listed"
    );
    assert!(
        env.gaps
            .iter()
            .any(|g| g.kind == GapKind::BudgetExhausted || g.kind == GapKind::TimedOut),
        "{:?}",
        env.gaps
    );
    let unenriched = env
        .data
        .sessions
        .iter()
        .filter(|s| {
            matches!(
                s.reported_configuration.model,
                openwiz_core::model::Fact::Unknown(_)
            )
        })
        .count();
    assert!(
        unenriched > 0,
        "rows not read in time have unknown configuration"
    );
}

#[test]
fn the_default_budget_is_thirty_seconds() {
    assert_eq!(RUN_BUDGET, Duration::from_secs(30), "the approved budget");
    let source = ScriptedSource::new(3);
    let started = Instant::now();
    list_scripted(&source, &page(0, 3, Detail::Long)).expect("list");
    let finished = Instant::now();
    let deadlines = source.deadlines.lock().unwrap().clone();
    assert!(!deadlines.is_empty(), "every read gets a deadline");
    for deadline in deadlines {
        // The run's deadline is set between the start and the end of the call.
        assert!(
            deadline >= started + RUN_BUDGET && deadline <= finished + RUN_BUDGET,
            "a read's deadline is {:?} after the start, not the 30-second run budget",
            deadline.duration_since(started)
        );
    }
}

#[test]
fn rows_are_capped() {
    let source = ScriptedSource::new(MAX_LIMIT + 10);
    match list_scripted(
        &source,
        &ListRequest {
            limit: MAX_LIMIT + 1,
            ..ListRequest::default()
        },
    ) {
        Ok(env) => assert!(env.data.sessions.len() <= MAX_LIMIT),
        Err(OpError::InvalidRequest(reason)) => assert!(!reason.is_empty()),
        Err(other) => panic!("a too-large limit is capped or refused, got {other:?}"),
    }
}

#[test]
fn hidden_or_archived_rows_are_excluded_even_if_the_source_returns_them() {
    let mut hidden = scripted_record(1);
    hidden.hidden = Fact::Known(true);
    let mut archived = scripted_record(2);
    archived.archived = Fact::Known(true);
    let visible = scripted_record(3);
    let source = ScriptedSource::with_records(vec![hidden, archived, visible]);
    let env = list_scripted(&source, &ListRequest::default()).expect("list");
    assert_eq!(ids(&env), ["thr_syn_0003"]);
    let c = env.coverage.counts.as_ref().expect("counts");
    assert_eq!(
        (c.listed, c.excluded_hidden, c.excluded_archived, c.matched),
        (3, 1, 1, 1)
    );
}
