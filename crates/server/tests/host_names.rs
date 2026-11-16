//! The server's two host-name rules, through its public API: the name an
//! owner may configure for the tunnel (A3, `valid_host_name`), and the send
//! host, which can never be a loopback name or an IP address (W3, WS-6,
//! `SendHost`). Moved here from `tests/web-api/` (#807): they exercise only
//! this crate and run no program.

use openwiz_server::{SendHost, valid_host_name};

#[test]
fn only_dns_names_can_be_configured() {
    for good in ["openwiz.example.invalid", "a", "x-1.example.invalid", "A.B"] {
        assert!(valid_host_name(good), "{good}");
    }
    let long = format!("{}.example.invalid", "a".repeat(64));
    let too_long = ["a"; 128].join(".");
    for bad in [
        "",
        " ",
        "openwiz.example.invalid:443",
        "openwiz.example.invalid/",
        "http://openwiz.example.invalid",
        "-a.example.invalid",
        "a-.example.invalid",
        "a..example.invalid",
        ".example.invalid",
        "example.invalid.",
        "a_b.example.invalid",
        "*.example.invalid",
        "127.0.0.1:80",
        "[::1]",
        "ex\u{e4}mple.invalid",
        &long,
        &too_long,
    ] {
        assert!(!valid_host_name(bad), "{bad:?}");
    }
}

/// Sol #91 round 1, finding 2: WS-6 holds by type, not by convention. A
/// send host can never be a loopback name or an IP literal, so no
/// configuration can serve a send to a loopback `Host`.
#[test]
fn a_send_host_can_never_be_loopback_or_an_ip_address() {
    for bad in [
        "localhost",
        "LOCALHOST",
        "LocalHost",
        "a.localhost",
        "openwiz.localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
        "127.0.0.1",
        "127.1",
        "127.0.0.1.",
        "2130706433",
        "0.0.0.0",
        "10.0.0.1",
        "203.0.113.7",
        "1.2.3.4",
        "0x7f.0.0.1",
        "::1",
        "[::1]",
        "",
        "openwiz.example:443",
    ] {
        assert!(
            SendHost::new(bad).is_err(),
            "{bad:?} was accepted as a send host"
        );
    }
    for good in [
        "openwiz.example",
        "my.openwiz.example",
        "a",
        "x-1.example.invalid",
    ] {
        assert_eq!(SendHost::new(good).expect(good).as_str(), good);
    }
}
