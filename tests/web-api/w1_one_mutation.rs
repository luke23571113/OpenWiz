//! W1 (#9): exactly one mutation route (A4 pins the route table); every
//! other method on the send route is `405` with
//! `Allow: POST`, `POST` anywhere else is `405` with `Allow: GET`, and none
//! of them reads, claims or sends anything.
//!
//! Updated for #12 (OpenWiz 0.0.4, A2), with its reason at the change: the
//! table now holds A2's four new-thread routes, so
//! the send is one of two writes. Everything else here still holds for the
//! send: no new-thread route sends.

use crate::msg::SendFake;
use crate::send_support::{body, good_headers, messages, raw, serve_send};

#[test]
fn every_other_method_on_the_send_route_is_405_and_sends_nothing() {
    let fake = SendFake::new("web_w1_methods", "send");
    let s = serve_send(&fake);
    let payload = body("w1-op-1", "queue", "Synthetic W1 text").to_string();
    for method in [
        "GET", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "CONNECT", "TRACE", "post", "Post", "X",
    ] {
        let r = s.send(&raw(
            method,
            &messages("thr_syn_0001"),
            &good_headers(),
            payload.as_bytes(),
            true,
        ));
        assert_eq!(r.status, 405, "{method}: {}", r.status_line);
        assert_eq!(r.header("Allow"), Some("POST"), "{method}");
    }
    assert_eq!(fake.tell_count(), 0);
    assert!(fake.invocations().is_empty(), "{:?}", fake.invocations());
    assert!(!fake.record_path("w1-op-1").exists());
}

#[test]
fn post_anywhere_else_is_405_and_sends_nothing() {
    let fake = SendFake::new("web_w1_elsewhere", "send");
    let s = serve_send(&fake);
    let payload = body("w1-op-2", "queue", "Synthetic W1 text").to_string();
    for target in [
        "/api/v1/inventory",
        "/api/v1/sessions/thr_syn_0001",
        "/api/v1/sessions/thr_syn_0001/preview",
        "/api/v1/sessions/thr_syn_0001/messages/w1-op-2",
        "/api/v1/health",
        "/api/v1/sessions/thr_syn_0001/messages/",
        "/api/v1/sessions/thr_syn_0001/message",
        "/api/v1/messages",
        "/",
        "/nowhere",
    ] {
        let r = s.send(&raw(
            "POST",
            target,
            &good_headers(),
            payload.as_bytes(),
            true,
        ));
        assert_eq!(r.status, 405, "{target}: {}", r.status_line);
        assert_eq!(r.header("Allow"), Some("GET"), "{target}");
    }
    assert_eq!(fake.tell_count(), 0);
    assert!(fake.invocations().is_empty(), "{:?}", fake.invocations());
}

/// Sol #91 round 1, finding 3: without a send configuration, the send,
/// preview and lookup routes are absent for every method: `404`, no
/// `Allow`, nothing read.
#[test]
fn without_sending_the_send_routes_are_absent_for_every_method() {
    let fake = SendFake::new("web_w1_disabled", "send");
    let mut config = crate::send_support::send_config(&fake, openwiz_server::Limits::default());
    config.sending = None;
    let s = crate::send_support::serve_config(&fake, config);
    let payload = body("w1-op-9", "queue", "Synthetic W1 text").to_string();
    for target in [
        messages("thr_syn_0001"),
        "/api/v1/sessions/thr_syn_0001/preview".to_owned(),
        "/api/v1/sessions/thr_syn_0001/messages/w1-op-9".to_owned(),
    ] {
        for method in ["GET", "POST", "OPTIONS", "HEAD", "PUT", "DELETE"] {
            let r = s.send(&raw(
                method,
                &target,
                &good_headers(),
                payload.as_bytes(),
                true,
            ));
            assert_eq!(r.status, 404, "{method} {target}: {}", r.status_line);
            assert_eq!(r.header("Allow"), None, "{method} {target}");
            if method == "HEAD" {
                assert!(r.body.is_empty(), "{method} {target}");
            } else {
                assert_eq!(r.error().0, "no_route", "{method} {target}");
            }
        }
    }
    assert_eq!(fake.tell_count(), 0);
    assert!(fake.invocations().is_empty(), "{:?}", fake.invocations());
    assert!(!fake.state.exists(), "the send record was touched");
}
