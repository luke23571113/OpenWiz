# 0.0.16 first-merge kit fixtures (#637)

Synthetic documents for the offline proofs of the 0.0.16 extension of the
[first-hour live kit](../../../../tools/install/first-hour-live-kit.md), read by
`tools/install/tests/first-hour/test_first_merge.py`. Every value is invented:
each private-record pointer is a `POINTER-<n>` placeholder that the tests
turn into the synthetic pointer form (as `test_kit.py` builds its own), digests are
repeated hex, and the repository, times and ids are made up.

**Shape only.** Their `live` proof class is a label on invented values, so the
validator's positive path can be exercised. It is never an observation, a
measured time, a real account, an approved authority or an upstream capability.
No file here may be offered as a live result: a real receipt comes only from
T9 #639's run under T8 #638's exact authorization.

The documents are the one JSON block below, keyed by name (the fixture scan reads
README files as documentation, as for `../README.md`'s examples).

| Name | What |
| --- | --- |
| `result` | A first-hour.v1 `result`: #2200's synthetic `recording-complete` example (`../README.md`) with its times scaled so the merge lands at 29 min 59 s, relabelled `live` with a pointer and every gate settled |
| `receipt` | A setup-onboard.v1 `first_merge_receipt` bound to the SHA-256 of `result` as the tests serialize it, the same candidate, repository, merge, waits and help, and five owner actions: the App's Create and Install, the spec confirmation, the plan approval and the launch's spending approval, on the `agent_save` route |
| `fleet` | An `openwiz.first-merge-kit-fleet.v1` fleet start: one launch-fleet fleet thread, its 10-minute per-spec loop, no engine activation or tick start |
| `binding` | An `openwiz.first-merge-kit-binding.v1` binding for that run, with its test-owned cleanup |
| `eligibility` | An `openwiz.first-merge-kit-eligibility.v1` record: graph, the seven producers' synthetic verified merges, one pointer per authority scope and an observed upstream save |

The tests change copies of these and rebind the receipt's SHA-256 as a real run
would; expected codes and refusals are written by hand from the contracts and
the kit.

```json
{
 "result": {
  "schema": "openwiz.first-hour.v1",
  "kind": "result",
  "verdict": "unverified",
  "proof_class": "live",
  "synthetic_assumptions": [],
  "private_record": "POINTER-30",
  "candidate": {
   "known": {
    "version": "0.0.99",
    "source": "1111111111111111111111111111111111111111",
    "target": "x86_64-unknown-linux-gnu",
    "manifest_sha256": "2222222222222222222222222222222222222222222222222222222222222222"
   }
  },
  "repository": {
   "known": {
    "full_name": "syn-owner/syn-first-hour",
    "selected_by_owner": true
   }
  },
  "clock": {
   "started_at_ms": {
    "known": 1700000000000
   },
   "ended_at_ms": {
    "known": 1700001799000
   },
   "limit_ms": 3600000
  },
  "stages": [
   {
    "id": "public_instruction",
    "state": "verified",
    "reason": "Synthetic: the public install instruction was opened.",
    "evidence": [
     {
      "basis": "instruction_opened",
      "at_ms": 1700000000000,
      "detail": "Synthetic instruction page opened."
     }
    ]
   },
   {
    "id": "install",
    "state": "verified",
    "reason": "Synthetic: the candidate installed.",
    "evidence": [
     {
      "basis": "install_result",
      "at_ms": 1700000191382,
      "detail": "Synthetic install result for the candidate."
     }
    ]
   },
   {
    "id": "connections",
    "state": "verified",
    "reason": "Synthetic: every prerequisite of the selected engine verified.",
    "evidence": [
     {
      "basis": "setup_component_verified",
      "at_ms": 1700000574148,
      "detail": "Synthetic setup read with every component verified."
     }
    ]
   },
   {
    "id": "idea",
    "state": "verified",
    "reason": "Synthetic: a fresh small idea was saved.",
    "evidence": [
     {
      "basis": "idea_saved",
      "at_ms": 1700000765531,
      "detail": "Synthetic idea saved for the selected repository."
     }
    ]
   },
   {
    "id": "spec_confirmation",
    "state": "verified",
    "reason": "Synthetic: the spec confirmation was saved.",
    "evidence": [
     {
      "basis": "decision_saved",
      "at_ms": 1700000956914,
      "detail": "Synthetic resolved confirmation record."
     }
    ]
   },
   {
    "id": "plan_approval",
    "state": "verified",
    "reason": "Synthetic: the exact plan approval was saved.",
    "evidence": [
     {
      "basis": "decision_saved",
      "at_ms": 1700001071744,
      "detail": "Synthetic resolved approval of the current revision."
     }
    ]
   },
   {
    "id": "fleet",
    "state": "verified",
    "reason": "Synthetic: the approved builders started.",
    "evidence": [
     {
      "basis": "agents_running",
      "at_ms": 1700001148297,
      "detail": "Synthetic builder started."
     }
    ]
   },
   {
    "id": "review",
    "state": "verified",
    "reason": "Synthetic: the independent reviewer approved the head.",
    "evidence": [
     {
      "basis": "review_approve_exact_head",
      "at_ms": 1700001722446,
      "detail": "Synthetic APPROVE naming the head."
     }
    ]
   },
   {
    "id": "ci",
    "state": "verified",
    "reason": "Synthetic: every required check was green on the head.",
    "evidence": [
     {
      "basis": "ci_green_exact_head",
      "at_ms": 1700001645893,
      "detail": "Synthetic green required checks."
     }
    ]
   },
   {
    "id": "merge",
    "state": "verified",
    "reason": "Synthetic: the merge was read back at the approved head.",
    "evidence": [
     {
      "basis": "merge_read_back",
      "at_ms": 1700001799000,
      "detail": "Synthetic merged state at the approved head."
     }
    ]
   }
  ],
  "builder": {
   "harness": "claude_code",
   "model": "Synthetic builder model",
   "effort": "high",
   "location": "cloud",
   "usable": "verified",
   "extra_prerequisites": [],
   "evidence": [
    {
     "basis": "harness_run_observed",
     "at_ms": 1700001148297,
     "detail": "Synthetic builder run observed."
    }
   ]
  },
  "reviewer": {
   "harness": "codex",
   "model": "Synthetic reviewer model",
   "effort": "high",
   "location": "cloud",
   "usable": "verified",
   "extra_prerequisites": [
    "Synthetic separate sign-in for the reviewer harness."
   ],
   "evidence": [
    {
     "basis": "harness_run_observed",
     "at_ms": 1700001594858,
     "detail": "Synthetic reviewer run observed."
    }
   ]
  },
  "waits": [
   {
    "stage": "install",
    "kind": "install",
    "started_at_ms": 1700000038276,
    "ended_at_ms": 1700000153106,
    "detail": "Synthetic download and verification."
   },
   {
    "stage": "fleet",
    "kind": "queue",
    "started_at_ms": 1700001084503,
    "ended_at_ms": 1700001148297,
    "detail": "Synthetic builder queue."
   },
   {
    "stage": "ci",
    "kind": "ci",
    "started_at_ms": 1700001531063,
    "ended_at_ms": 1700001645893,
    "detail": "Synthetic CI run."
   }
  ],
  "help": [
   {
    "stage": "connections",
    "at_ms": 1700000382765,
    "source": "public_docs",
    "detail": "Synthetic public setup page read."
   }
  ],
  "retained_work": [
   {
    "kind": "setup_state",
    "id": "syn-setup-state",
    "content": "a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7",
    "basis": "owner_state_read_back"
   },
   {
    "kind": "branch",
    "id": "room/syn-first-hour-1",
    "content": "b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8",
    "basis": "repository_read_back"
   },
   {
    "kind": "commit",
    "id": "dadadadadadadadadadadadadadadadadadadada",
    "content": "c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9",
    "basis": "repository_read_back"
   }
  ],
  "operations": [
   {
    "operation_id": "b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2",
    "kind": "connect_app",
    "phase": "applied",
    "effect_count": 1,
    "attempts": 1,
    "reconciliation": "none"
   },
   {
    "operation_id": "a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1",
    "kind": "send",
    "phase": "applied",
    "effect_count": 1,
    "attempts": 1,
    "reconciliation": "provider_read_back"
   },
   {
    "operation_id": "c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3",
    "kind": "start_agent",
    "phase": "applied",
    "effect_count": 1,
    "attempts": 1,
    "reconciliation": "none"
   },
   {
    "operation_id": "d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4d4",
    "kind": "merge",
    "phase": "applied",
    "effect_count": 1,
    "attempts": 1,
    "reconciliation": "none"
   }
  ],
  "interruptions": [
   {
    "interruption": "lost_reply",
    "before": [
     {
      "kind": "pending_operation",
      "id": "a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1",
      "content": "e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5",
      "basis": "owner_state_read_back"
     },
     {
      "kind": "draft",
      "id": "syn-draft-confirmation",
      "content": "f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6",
      "basis": "tab_session_storage"
     }
    ],
    "after": [
     {
      "kind": "pending_operation",
      "id": "a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1",
      "content": "e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5",
      "basis": "owner_state_read_back"
     },
     {
      "kind": "draft",
      "id": "syn-draft-confirmation",
      "content": "f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6",
      "basis": "tab_session_storage"
     }
    ],
    "operations": [
     {
      "operation_id": "a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1",
      "kind": "send",
      "phase_before": "uncertain",
      "phase_after": "applied",
      "effect_count": 1,
      "attempts": 1,
      "reconciliation": "provider_read_back"
     }
    ],
    "explanation": {
     "what_happened": "Synthetic: the confirmation's reply was lost; its send record showed it was sent once.",
     "took_effect": "yes",
     "next_action": "Synthetic: nothing to resend; wait for the saved confirmation."
    }
   },
   {
    "interruption": "browser_restart",
    "before": [
     {
      "kind": "setup_state",
      "id": "syn-setup-state",
      "content": "a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7",
      "basis": "owner_state_read_back"
     }
    ],
    "after": [
     {
      "kind": "setup_state",
      "id": "syn-setup-state",
      "content": "a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7",
      "basis": "owner_state_read_back"
     }
    ],
    "operations": [],
    "explanation": {
     "what_happened": "Synthetic: the browser restarted during setup; the saved setup state was read back unchanged.",
     "took_effect": "no",
     "next_action": "Synthetic: continue setup from the saved state."
    }
   },
   {
    "interruption": "update_rejected",
    "before": [
     {
      "kind": "branch",
      "id": "room/syn-first-hour-1",
      "content": "b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8",
      "basis": "repository_read_back"
     },
     {
      "kind": "commit",
      "id": "dadadadadadadadadadadadadadadadadadadada",
      "content": "c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9",
      "basis": "repository_read_back"
     }
    ],
    "after": [
     {
      "kind": "branch",
      "id": "room/syn-first-hour-1",
      "content": "b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8",
      "basis": "repository_read_back"
     },
     {
      "kind": "commit",
      "id": "dadadadadadadadadadadadadadadadadadadada",
      "content": "c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9c9",
      "basis": "repository_read_back"
     }
    ],
    "operations": [],
    "explanation": {
     "what_happened": "Synthetic: an update was refused before activation; the last good build stayed selected.",
     "took_effect": "no",
     "next_action": "Synthetic: keep working on the current build."
    }
   }
  ],
  "findings": [
   {
    "id": "F1",
    "severity": "low",
    "work_loss": false,
    "summary": "Synthetic low finding.",
    "owner": 9001,
    "disposition": "open"
   }
  ],
  "gaps": [
   {
    "claim": "PR2",
    "reason": "Synthetic: no usable-login observation in a recording."
   },
   {
    "claim": "PR3",
    "reason": "Synthetic: no independent security review."
   },
   {
    "claim": "PR5",
    "reason": "Synthetic: no reviewed page captures."
   }
  ],
  "gates": {
   "cloudroom_setup": {
    "decision_ticket": 2201,
    "state": "settled",
    "producers": [
     9001
    ]
   },
   "paid_offer": {
    "decision_ticket": 2202,
    "state": "settled",
    "producers": [
     2293
    ]
   },
   "feedback": {
    "decision_ticket": 2203,
    "state": "settled",
    "producers": [
     2292
    ]
   }
  },
  "ten_minute_fleet": {
   "owner": 1110,
   "state": "unmeasured",
   "elapsed_ms": null
  }
 },
 "receipt": {
  "schema": "openwiz.setup-onboard.v1",
  "kind": "first_merge_receipt",
  "proof_class": "live",
  "synthetic_assumptions": [],
  "private_record": "POINTER-31",
  "verdict": "pass",
  "binding": {
   "first_hour_result_sha256": "8bd524d734bb633f7415fb9a40d34010f20504c9f3a884d09c9a2ca2904c1f0e",
   "candidate": {
    "known": {
     "version": "0.0.99",
     "source": "1111111111111111111111111111111111111111",
     "target": "x86_64-unknown-linux-gnu",
     "manifest_sha256": "2222222222222222222222222222222222222222222222222222222222222222"
    }
   },
   "repository": {
    "known": "syn-owner/syn-first-hour"
   },
   "merge": {
    "pull_request": 9101,
    "head": "dadadadadadadadadadadadadadadadadadadada",
    "merge_commit": "4e4e4e4e4e4e4e4e4e4e4e4e4e4e4e4e4e4e4e4e",
    "merged_at_ms": 1700001799000,
    "basis": "merge_read_back",
    "change": "implementation",
    "reviewed_head": "dadadadadadadadadadadadadadadadadadadada",
    "ci_green_head": "dadadadadadadadadadadadadadadadadadadada"
   }
  },
  "instruction": "Install OpenWiz from github.com/openwizdev/OpenWiz",
  "idea": "Synthetic fresh idea: a docs link checker for this repository.",
  "clock": {
   "started_at_ms": {
    "known": 1700000000000
   },
   "ended_at_ms": {
    "known": 1700001799000
   },
   "limit_ms": 1800000,
   "rule": "strictly_less_than"
  },
  "actions": {
   "count": {
    "known": 5
   },
   "limit": 5,
   "log": [
    {
     "at_ms": 1700000446560,
     "kind": "app_manifest",
     "actor": "owner",
     "stage": "create_app",
     "detail": "Synthetic: Create on the App manifest page."
    },
    {
     "at_ms": 1700000484836,
     "kind": "app_manifest",
     "actor": "owner",
     "stage": "install_app",
     "detail": "Synthetic: Install on the selected repository only."
    },
    {
     "at_ms": 1700000956914,
     "kind": "confirmation",
     "actor": "owner",
     "stage": "spec_confirmation",
     "detail": "Synthetic: the spec confirmation."
    },
    {
     "at_ms": 1700001071744,
     "kind": "approval",
     "actor": "owner",
     "stage": "plan_approval",
     "detail": "Synthetic: the exact-plan approval."
    },
    {
     "at_ms": 1700001084503,
     "kind": "spending_approval",
     "actor": "owner",
     "stage": "launch",
     "detail": "Synthetic: yes to the fleet start and its Cloud Credits."
    }
   ]
  },
  "identity": "app",
  "app_registration": "created",
  "secret_route": "agent_save",
  "secret_route_observed": true,
  "decisions": {
   "spec_confirmation": true,
   "plan_approval": true
  },
  "waits": [
   {
    "kind": "install",
    "started_at_ms": 1700000038276,
    "ended_at_ms": 1700000153106,
    "detail": "Synthetic download and verification."
   },
   {
    "kind": "queue",
    "started_at_ms": 1700001084503,
    "ended_at_ms": 1700001148297,
    "detail": "Synthetic builder queue."
   },
   {
    "kind": "ci",
    "started_at_ms": 1700001531063,
    "ended_at_ms": 1700001645893,
    "detail": "Synthetic CI run."
   }
  ],
  "help": [
   {
    "at_ms": 1700000382765,
    "source": "public_docs",
    "detail": "Synthetic public setup page read."
   }
  ],
  "freshness": {
   "machine": "fresh",
   "repository": "fresh",
   "seeded_openwiz_state": false,
   "initial_record": "recorded"
  }
 },
 "fleet": {
  "schema": "openwiz.first-merge-kit-fleet.v1",
  "proof_class": "live",
  "private_record": "POINTER-32",
  "route": "launch_fleet",
  "fleet_threads": 1,
  "loop": {
   "spec": 9100,
   "every_minutes": 10
  },
  "engine_activations": 0,
  "tick_starts": 0,
  "builders": 1,
  "reviewers": 0
 },
 "binding": {
  "schema": "openwiz.first-merge-kit-binding.v1",
  "candidate": {
   "version": "0.0.99",
   "source": "1111111111111111111111111111111111111111",
   "target": "x86_64-unknown-linux-gnu",
   "manifest_sha256": "2222222222222222222222222222222222222222222222222222222222222222"
  },
  "host": {
   "target": "x86_64-unknown-linux-gnu",
   "fresh_machine": true,
   "seeded_openwiz_state": false
  },
  "scope": {
   "repository": "syn-owner/syn-first-hour",
   "app_repositories": [
    "syn-owner/syn-first-hour"
   ],
   "companion_repository": null
  },
  "route": {
   "identity": "app",
   "app_registration": "created",
   "secret_route": "agent_save"
  },
  "counts": {
   "fleet_threads": 1,
   "loops": 1,
   "builders": 3,
   "reviewers": 3,
   "merges": 1,
   "app_registrations": 1,
   "companions": 0
  },
  "credit_bound": 50,
  "recorded": {
   "actions": 5,
   "waits": 3,
   "help": 1
  },
  "cleanup": [
   {
    "resource": "test_threads",
    "action": "archive"
   },
   {
    "resource": "test_loops",
    "action": "stop"
   },
   {
    "resource": "test_app",
    "action": "delete"
   },
   {
    "resource": "test_secret",
    "action": "delete"
   },
   {
    "resource": "throwaway_repository",
    "action": "delete"
   }
  ],
  "graph": {
   "spec": 625,
   "revision": 1,
   "fingerprint": "3333333333333333333333333333333333333333333333333333333333333333"
  }
 },
 "eligibility": {
  "schema": "openwiz.first-merge-kit-eligibility.v1",
  "graph": {
   "spec": 625,
   "revision": 1,
   "fingerprint": "3333333333333333333333333333333333333333333333333333333333333333",
   "approval": "POINTER-10"
  },
  "producers": [
   {
    "ticket": 632,
    "pr": 10632,
    "merge_commit": "5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a",
    "approved_head": "6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b",
    "merged_at_head": true
   },
   {
    "ticket": 633,
    "pr": 10633,
    "merge_commit": "5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a",
    "approved_head": "6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b",
    "merged_at_head": true
   },
   {
    "ticket": 606,
    "pr": 10606,
    "merge_commit": "5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a",
    "approved_head": "6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b",
    "merged_at_head": true
   },
   {
    "ticket": 634,
    "pr": 10634,
    "merge_commit": "5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a",
    "approved_head": "6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b",
    "merged_at_head": true
   },
   {
    "ticket": 635,
    "pr": 10635,
    "merge_commit": "5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a",
    "approved_head": "6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b",
    "merged_at_head": true
   },
   {
    "ticket": 636,
    "pr": 10636,
    "merge_commit": "5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a",
    "approved_head": "6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b",
    "merged_at_head": true
   },
   {
    "ticket": 637,
    "pr": 10637,
    "merge_commit": "5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a",
    "approved_head": "6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b",
    "merged_at_head": true
   }
  ],
  "authority": {
   "live": "POINTER-40",
   "machine": "POINTER-41",
   "accounts": "POINTER-42",
   "repository": "POINTER-43",
   "app": "POINTER-44",
   "companion": "POINTER-45",
   "secret": "POINTER-46",
   "agents": "POINTER-47",
   "merges": "POINTER-48",
   "spending": "POINTER-49",
   "cleanup": "POINTER-50"
  },
  "upstream": {
   "state": "observed_supported",
   "evidence": "POINTER-60"
  }
 }
}
```
