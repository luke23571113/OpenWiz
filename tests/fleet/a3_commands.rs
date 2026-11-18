//! A3 (ClosedWiz#111): `openwiz --help` carries `openwiz fleets` and
//! `openwiz fleet <spec>`'s own usage line, section and exit codes in their
//! places. The program's dispatch to each command is proven by running the
//! release `openwiz` (`a4_fleets.rs`, `a5_agents_cli.rs`).
//!
//! What the stubs do (say not yet, read nothing) is each command's own,
//! proven in `a4_fleets.rs` and `a5_fleet.rs`, which A4 and A5 replace (Sol
//! on #247, R1).

use openwiz_cli::{fleet, fleets};

#[test]
fn the_help_carries_each_commands_own_lines_in_their_places() {
    let help = openwiz_cli::help();
    let find = |part: &str| {
        help.find(part)
            .unwrap_or_else(|| panic!("{part:?} is not in --help:\n{help}"))
    };
    let usage = find("\nUsage:\n");
    let usage_end = usage
        + help[usage..]
            .find("  openwiz --help\n")
            .expect("--help's line");
    let exit_codes = help.rfind("\nExit codes:\n").expect("the exit codes");
    // Up to and with the newline that ends the last exit code's line.
    let on_error = exit_codes
        + help[exit_codes..]
            .find("\nOn an error, stdout is empty")
            .expect("the error note")
        + 1;
    for (name, usage_line, section, exits) in [
        ("fleets", fleets::USAGE, fleets::HELP, fleets::EXIT_CODES),
        ("fleet", fleet::USAGE, fleet::HELP, fleet::EXIT_CODES),
    ] {
        assert!(
            help[usage..usage_end].contains(usage_line),
            "{name}'s USAGE is in the usage list, before --help's line:\n{help}"
        );
        assert!(
            help[usage_end..exit_codes].contains(section),
            "{name}'s HELP is a section before the exit codes:\n{help}"
        );
        assert!(
            help[exit_codes..on_error].contains(exits),
            "{name}'s EXIT_CODES are in the exit codes:\n{help}"
        );
    }
}
