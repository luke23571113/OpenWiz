//! A6 (ClosedWiz#114): the CloudRoom fleet readers
//! (`openwiz_adapter_cloudroom::fleet`), on inline synthetic answers: a
//! table of good and bad answers for each read, with the gap each bad one
//! gets. A key given twice, a positional array, a tagged object, a missing
//! or extra key or a wrong type fails the read; nothing is guessed. Moved
//! here from `tests/fleet/a6_reads.rs` by TV4 (#806); the reads on the fake
//! `room-cli` stay there. Fixture tests only.

use openwiz_adapter_cloudroom::fleet::{
    Repository, parse_projects, parse_threads, parse_workspace,
};
use openwiz_core::envelope::GapKind;
use openwiz_core::fleet::model::{Failed, NonEmpty, Project, Thread};
use serde_json::{Value, json};

fn ne(s: &str) -> NonEmpty {
    NonEmpty::new(s).expect("not empty")
}

fn failed(gap: GapKind, reason: &str) -> Failed {
    Failed {
        gap,
        reason: ne(reason),
    }
}

fn repo() -> Repository {
    Repository::parse("synthetic-owner/synthetic-repo").expect("a repository")
}

const HEAD: &str = "0123456789abcdef0123456789abcdef01234567";

#[test]
fn cloudroom_read_contracts_preserve_original_cases() {
    let cases: [(&str, fn()); 5] = [
        (
            "a_repository_is_exactly_owner_and_name",
            a_repository_is_exactly_owner_and_name,
        ),
        (
            "only_this_repositorys_remote_names_it",
            only_this_repositorys_remote_names_it,
        ),
        (
            "the_project_reader_keeps_this_repositorys_projects_strictly",
            the_project_reader_keeps_this_repositorys_projects_strictly,
        ),
        (
            "the_thread_reader_keeps_these_projects_threads_strictly",
            the_thread_reader_keeps_these_projects_threads_strictly,
        ),
        (
            "the_workspace_reader_takes_only_its_exact_shape",
            the_workspace_reader_takes_only_its_exact_shape,
        ),
    ];
    for (name, proof) in cases {
        eprintln!("TA2 case: a6_agents::reads::{name}");
        proof();
    }
}

fn the_workspace_reader_takes_only_its_exact_shape() {
    let good = [
        (
            json!({"branch": "room/syn-a6-0941", "head": HEAD, "path": "/synthetic/work"}),
            "room/syn-a6-0941",
        ),
        (
            json!({"path": "/synthetic/work", "head": HEAD, "branch": "room/syn-a6-0942"}),
            "room/syn-a6-0942",
        ),
    ];
    for (answer, branch) in good {
        let text = format!("\n {answer} \n");
        assert_eq!(parse_workspace(text.as_bytes()), Ok(ne(branch)), "{text}");
    }

    let not_json = failed(
        GapKind::Malformed,
        "room-cli cloud thread-workspace printed something that is not JSON",
    );
    let twice = failed(
        GapKind::Malformed,
        "room-cli cloud thread-workspace gave a key twice",
    );
    let not_object = failed(
        GapKind::WrongType,
        "room-cli cloud thread-workspace: a workspace is not a JSON object",
    );
    let missing = |key: &str| {
        failed(
            GapKind::MissingField,
            &format!("room-cli cloud thread-workspace: a workspace has no {key}"),
        )
    };
    let wrong = |key: &str| {
        failed(
            GapKind::WrongType,
            &format!("room-cli cloud thread-workspace: a workspace's {key} has an unexpected type"),
        )
    };
    let unknown_key = failed(
        GapKind::Malformed,
        "room-cli cloud thread-workspace printed a key OpenWiz doesn't know",
    );
    let bad: Vec<(String, Failed)> = vec![
        (String::new(), not_json.clone()),
        ("room/syn-a6-0941".to_owned(), not_json.clone()),
        (
            format!(r#"{{"branch": "room/syn-a6-0941", "head": "{HEAD}", "path": "/synthetic/work""#),
            not_json.clone(),
        ),
        (
            format!(
                r#"{{"branch": "room/syn-x", "branch": "room/syn-a6-0941", "head": "{HEAD}", "path": "/synthetic/work"}}"#
            ),
            twice.clone(),
        ),
        (
            format!(
                r#"{{"branch": "room/syn-a6-0941", "head": "{HEAD}", "path": "/synthetic/work", "extra": {{"a": 1, "a": 2}}}}"#
            ),
            twice,
        ),
        (
            format!(r#"["room/syn-a6-0941", "{HEAD}", "/synthetic/work"]"#),
            not_object.clone(),
        ),
        (r#""room/syn-a6-0941""#.to_owned(), not_object.clone()),
        ("null".to_owned(), not_object),
        (
            json!({"head": HEAD, "path": "/synthetic/work"}).to_string(),
            missing("branch"),
        ),
        (
            json!({"branch": "room/syn-a6-0941", "path": "/synthetic/work"}).to_string(),
            missing("head"),
        ),
        (
            json!({"branch": "room/syn-a6-0941", "head": HEAD}).to_string(),
            missing("path"),
        ),
        (json!({}).to_string(), missing("head")),
        (
            json!({"branch": "room/syn-a6-0941", "head": HEAD, "path": "/synthetic/work", "pullRequest": null}).to_string(),
            unknown_key,
        ),
        (
            json!({"branch": 941, "head": HEAD, "path": "/synthetic/work"}).to_string(),
            wrong("branch"),
        ),
        (
            json!({"branch": null, "head": HEAD, "path": "/synthetic/work"}).to_string(),
            wrong("branch"),
        ),
        (
            json!({"branch": {"room/syn-a6-0941": null}, "head": HEAD, "path": "/synthetic/work"})
                .to_string(),
            wrong("branch"),
        ),
        (
            json!({"branch": ["room/syn-a6-0941"], "head": HEAD, "path": "/synthetic/work"})
                .to_string(),
            wrong("branch"),
        ),
        (
            json!({"branch": true, "head": HEAD, "path": "/synthetic/work"}).to_string(),
            wrong("branch"),
        ),
        (
            json!({"branch": "room/syn-a6-0941", "head": 1, "path": "/synthetic/work"}).to_string(),
            wrong("head"),
        ),
        (
            json!({"branch": "room/syn-a6-0941", "head": HEAD, "path": null}).to_string(),
            wrong("path"),
        ),
        (
            json!({"branch": "", "head": HEAD, "path": "/synthetic/work"}).to_string(),
            failed(
                GapKind::Malformed,
                "room-cli cloud thread-workspace: a workspace's branch is empty",
            ),
        ),
    ];
    for (answer, want) in bad {
        assert_eq!(parse_workspace(answer.as_bytes()), Err(want), "{answer}");
    }
}

fn a_repository_is_exactly_owner_and_name() {
    for good in [
        "synthetic-owner/synthetic-repo",
        "Synthetic_Owner/synthetic.repo-1",
        "o/n",
    ] {
        assert!(Repository::parse(good).is_some(), "{good}");
    }
    for bad in [
        "",
        "synthetic-repo",
        "synthetic-owner/",
        "/synthetic-repo",
        "synthetic-owner/synthetic-repo/x",
        "synthetic-owner/..",
        "./synthetic-repo",
        "synthetic owner/synthetic-repo",
        "synthetic-owner/synthetic-repo\n",
        "synthétique/synthetic-repo",
        "synthetic-owner:synthetic-repo",
    ] {
        assert!(Repository::parse(bad).is_none(), "{bad:?}");
    }
    let long = format!("{}/n", "o".repeat(101));
    assert!(Repository::parse(&long).is_none());
}

fn only_this_repositorys_remote_names_it() {
    let repo = repo();
    for remote in [
        "https://github.com/synthetic-owner/synthetic-repo",
        "https://github.com/synthetic-owner/synthetic-repo.git",
        "ssh://git@github.com/synthetic-owner/synthetic-repo.git",
        "git@github.com:synthetic-owner/synthetic-repo.git",
        "git@github.com:synthetic-owner/synthetic-repo",
        "https://github.com/Synthetic-Owner/Synthetic-Repo",
    ] {
        assert!(repo.is_remote(remote), "{remote}");
    }
    for remote in [
        "",
        "https://github.com/synthetic-owner/synthetic-repo-2",
        "https://github.com/synthetic-owner/synthetic-rep",
        "https://github.com/other-owner/synthetic-repo",
        "https://github.com/synthetic-owner/synthetic-repo/",
        "https://github.com/synthetic-owner/synthetic-repo.git.git",
        "https://github.com/synthetic-owner/synthetic-repo ",
        " https://github.com/synthetic-owner/synthetic-repo",
        "http://github.com/synthetic-owner/synthetic-repo",
        "https://gitlab.example.invalid/synthetic-owner/synthetic-repo",
        "https://github.com.example.invalid/synthetic-owner/synthetic-repo",
        "https://user@github.com/synthetic-owner/synthetic-repo",
        "https://github.com/synthetic-owner/synthetic-repo/tree/main",
        "git@github.com:/synthetic-owner/synthetic-repo",
        "synthetic-owner/synthetic-repo",
        "/synthetic/path/synthetic-repo",
    ] {
        assert!(!repo.is_remote(remote), "{remote:?}");
    }
}

fn project(id: &str, name: &str) -> Project {
    Project {
        id: ne(id),
        name: name.to_owned(),
    }
}

fn project_row(id: &str, remote: Option<&str>) -> Value {
    json!({
        "id": id,
        "kind": "standard",
        "name": format!("Synthetic {id}"),
        "gitRemoteUrl": remote,
        "createdAt": 1_793_000_000_000_i64,
        "updatedAt": 1_793_000_000_000_i64,
        "sources": []
    })
}

const OURS: &str = "https://github.com/synthetic-owner/synthetic-repo";

fn the_project_reader_keeps_this_repositorys_projects_strictly() {
    let rows = json!([
        project_row("prj_syn_0001", Some(OURS)),
        project_row("prj_syn_0002", Some("https://github.com/synthetic-owner/other-repo")),
        project_row("prj_syn_0003", None),
        project_row("prj_syn_0004", Some("git@github.com:synthetic-owner/synthetic-repo.git")),
        // Not this repository's, so its fields aren't read.
        {"gitRemoteUrl": null, "id": 4, "name": null},
    ]);
    assert_eq!(
        parse_projects(rows.to_string().as_bytes(), &repo()),
        Ok(vec![
            project("prj_syn_0001", "Synthetic prj_syn_0001"),
            project("prj_syn_0004", "Synthetic prj_syn_0004"),
        ])
    );
    assert_eq!(parse_projects(b"[]", &repo()), Ok(vec![]));

    let read = "room-cli project list";
    let bad: Vec<(String, Failed)> = vec![
        (
            "not json".to_owned(),
            failed(
                GapKind::Malformed,
                &format!("{read} printed something that is not JSON"),
            ),
        ),
        (
            json!({"projects": []}).to_string(),
            failed(
                GapKind::WrongType,
                &format!("{read} printed something that is not a JSON list"),
            ),
        ),
        (
            json!([["prj_syn_0001", "Synthetic", OURS]]).to_string(),
            failed(
                GapKind::WrongType,
                &format!("{read}: a project is not a JSON object"),
            ),
        ),
        (
            json!([{"id": "prj_syn_0001", "name": "Synthetic"}]).to_string(),
            failed(
                GapKind::MissingField,
                &format!("{read}: a project has no gitRemoteUrl"),
            ),
        ),
        (
            json!([{"id": "prj_syn_0001", "name": "Synthetic", "gitRemoteUrl": 1}]).to_string(),
            failed(
                GapKind::WrongType,
                &format!("{read}: a project's gitRemoteUrl has an unexpected type"),
            ),
        ),
        (
            json!([{"id": "prj_syn_0001", "name": "Synthetic", "gitRemoteUrl": {"url": OURS}}])
                .to_string(),
            failed(
                GapKind::WrongType,
                &format!("{read}: a project's gitRemoteUrl has an unexpected type"),
            ),
        ),
        (
            json!([{"name": "Synthetic", "gitRemoteUrl": OURS}]).to_string(),
            failed(
                GapKind::MissingField,
                &format!("{read}: a project has no id"),
            ),
        ),
        (
            json!([{"id": 1, "name": "Synthetic", "gitRemoteUrl": OURS}]).to_string(),
            failed(
                GapKind::WrongType,
                &format!("{read}: a project's id has an unexpected type"),
            ),
        ),
        (
            json!([{"id": "", "name": "Synthetic", "gitRemoteUrl": OURS}]).to_string(),
            failed(
                GapKind::Malformed,
                &format!("{read}: a project's id is empty"),
            ),
        ),
        (
            json!([{"id": "prj_syn_0001", "gitRemoteUrl": OURS}]).to_string(),
            failed(
                GapKind::MissingField,
                &format!("{read}: a project has no name"),
            ),
        ),
        (
            json!([
                project_row("prj_syn_0001", Some(OURS)),
                project_row("prj_syn_0001", Some(OURS))
            ])
            .to_string(),
            failed(
                GapKind::Malformed,
                &format!("{read} listed one of this repository's projects twice"),
            ),
        ),
        (
            // A key given twice, even in a project that isn't this
            // repository's, refuses the whole list.
            format!(
                r#"[{{"id": "prj_syn_0001", "name": "Synthetic", "gitRemoteUrl": "{OURS}"}}, {{"id": "prj_syn_0002", "name": "Synthetic", "gitRemoteUrl": null, "gitRemoteUrl": "{OURS}"}}]"#
            ),
            failed(GapKind::Malformed, &format!("{read} gave a key twice")),
        ),
    ];
    for (answer, want) in bad {
        assert_eq!(
            parse_projects(answer.as_bytes(), &repo()),
            Err(want),
            "{answer}"
        );
    }
}

fn cloud_row(id: &str, project: &str) -> Value {
    json!({
        "id": id,
        "projectId": project,
        "title": "Synthetic thread",
        "archivedAt": null,
        "executionTarget": "cloud",
        "environmentHostId": null,
        "environmentBranchName": null
    })
}

fn local_row(id: &str, project: &str, branch: Option<&str>) -> Value {
    json!({
        "id": id,
        "projectId": project,
        "title": "Synthetic thread",
        "archivedAt": null,
        "environmentHostId": "host_syn_0001",
        "environmentBranchName": branch
    })
}

fn ours() -> Vec<Project> {
    vec![
        project("prj_syn_0001", "Synthetic one"),
        project("prj_syn_0002", "Synthetic two"),
    ]
}

fn cloud(id: &str, project: &str) -> Thread {
    Thread::Cloud {
        thread: ne(id),
        project: ne(project),
    }
}

fn local(id: &str, project: &str, branch: Option<&str>) -> Thread {
    Thread::Local {
        thread: ne(id),
        project: ne(project),
        branch: branch.map(ne),
    }
}

fn the_thread_reader_keeps_these_projects_threads_strictly() {
    let mut archived = cloud_row("thr_syn_0005", "prj_syn_0001");
    archived["archivedAt"] = json!(1_793_000_000_000_i64);
    let rows = json!([
        cloud_row("thr_syn_0001", "prj_syn_0001"),
        local_row("thr_syn_0002", "prj_syn_0002", Some("room/syn-local-0002")),
        local_row("thr_syn_0003", "prj_syn_0001", None),
        archived,
        cloud_row("thr_syn_0006", "prj_syn_0099"),
        // Another project's, so nothing else of it is read.
        {"projectId": "prj_syn_0099", "id": 6, "executionTarget": "elsewhere"},
    ]);
    assert_eq!(
        parse_threads(rows.to_string().as_bytes(), &ours()),
        Ok(vec![
            cloud("thr_syn_0001", "prj_syn_0001"),
            local("thr_syn_0002", "prj_syn_0002", Some("room/syn-local-0002")),
            local("thr_syn_0003", "prj_syn_0001", None),
        ])
    );

    let read = "room-cli thread list";
    let with = |key: &str, value: Value| {
        let mut row = cloud_row("thr_syn_0001", "prj_syn_0001");
        row[key] = value;
        json!([row]).to_string()
    };
    let without = |row: Value, key: &str| {
        let mut row = row;
        row.as_object_mut().expect("a row").remove(key);
        json!([row]).to_string()
    };
    let local_with = |key: &str, value: Value| {
        let mut row = local_row("thr_syn_0001", "prj_syn_0001", Some("room/syn-local"));
        row[key] = value;
        json!([row]).to_string()
    };
    let wrong = |key: &str| {
        failed(
            GapKind::WrongType,
            &format!("{read}: a thread's {key} has an unexpected type"),
        )
    };
    let missing = |key: &str| {
        failed(
            GapKind::MissingField,
            &format!("{read}: a thread has no {key}"),
        )
    };
    let unsafe_id = failed(
        GapKind::Malformed,
        &format!("{read}: a thread id is not safe to pass to room-cli"),
    );
    let neither = failed(
        GapKind::MissingField,
        &format!("{read}: a thread has no executionTarget and no environmentHostId"),
    );
    let bad: Vec<(String, Failed)> = vec![
        (
            "[{".to_owned(),
            failed(GapKind::Malformed, &format!("{read} printed something that is not JSON")),
        ),
        (
            json!({"threads": []}).to_string(),
            failed(GapKind::WrongType, &format!("{read} printed something that is not a JSON list")),
        ),
        (
            json!([["thr_syn_0001", "prj_syn_0001", "cloud"]]).to_string(),
            failed(GapKind::WrongType, &format!("{read}: a thread is not a JSON object")),
        ),
        (
            without(cloud_row("thr_syn_0001", "prj_syn_0001"), "projectId"),
            missing("projectId"),
        ),
        (with("projectId", json!(1)), wrong("projectId")),
        (with("projectId", Value::Null), wrong("projectId")),
        (without(cloud_row("thr_syn_0001", "prj_syn_0001"), "id"), missing("id")),
        (with("id", json!(1)), wrong("id")),
        (
            with("id", json!("")),
            failed(GapKind::Malformed, &format!("{read}: a thread's id is empty")),
        ),
        (with("id", json!("--work-status")), unsafe_id.clone()),
        (with("id", json!("thr syn 0001")), unsafe_id.clone()),
        (with("id", json!("thr_syn_0001;x")), unsafe_id),
        (
            without(cloud_row("thr_syn_0001", "prj_syn_0001"), "archivedAt"),
            missing("archivedAt"),
        ),
        (with("archivedAt", json!("yesterday")), wrong("archivedAt")),
        (with("archivedAt", json!(1.5)), wrong("archivedAt")),
        (with("archivedAt", json!(false)), wrong("archivedAt")),
        (
            with("executionTarget", json!("local")),
            failed(
                GapKind::Malformed,
                &format!("{read}: a thread's executionTarget is not one OpenWiz knows"),
            ),
        ),
        (
            with("executionTarget", json!("Cloud")),
            failed(
                GapKind::Malformed,
                &format!("{read}: a thread's executionTarget is not one OpenWiz knows"),
            ),
        ),
        (with("executionTarget", Value::Null), wrong("executionTarget")),
        (
            with("executionTarget", json!({"cloud": null})),
            wrong("executionTarget"),
        ),
        (local_with("environmentHostId", Value::Null), neither.clone()),
        (
            without(
                local_row("thr_syn_0001", "prj_syn_0001", None),
                "environmentHostId",
            ),
            neither,
        ),
        (local_with("environmentHostId", json!(5)), wrong("environmentHostId")),
        (
            without(
                local_row("thr_syn_0001", "prj_syn_0001", None),
                "environmentBranchName",
            ),
            missing("environmentBranchName"),
        ),
        (
            local_with("environmentBranchName", json!("")),
            failed(
                GapKind::Malformed,
                &format!("{read}: a thread's environmentBranchName is empty"),
            ),
        ),
        (
            local_with("environmentBranchName", json!(5)),
            wrong("environmentBranchName"),
        ),
        (
            local_with("environmentBranchName", json!(["room/syn-local"])),
            wrong("environmentBranchName"),
        ),
        (
            json!([
                cloud_row("thr_syn_0001", "prj_syn_0001"),
                local_row("thr_syn_0001", "prj_syn_0002", None)
            ])
            .to_string(),
            failed(GapKind::Malformed, &format!("{read} listed one thread twice")),
        ),
        (
            r#"[{"id": "thr_syn_0001", "projectId": "prj_syn_0099", "projectId": "prj_syn_0001", "archivedAt": null, "executionTarget": "cloud"}]"#
                .to_owned(),
            failed(GapKind::Malformed, &format!("{read} gave a key twice")),
        ),
    ];
    for (answer, want) in bad {
        assert_eq!(
            parse_threads(answer.as_bytes(), &ours()),
            Err(want),
            "{answer}"
        );
    }
}

// The reads end to end, on the fake `room-cli`.
