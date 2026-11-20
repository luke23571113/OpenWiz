use std::io::Write;

use openwiz_core::limits::READ_TIMEOUT;
use openwiz_core::new_thread::operation::NewThreadClient;
use openwiz_core::new_thread::options::{CloudOptions, OptionsState, cloud_options};
use openwiz_core::ops::Clock;

use crate::{EXIT_OK, EXIT_USAGE, clean, help, utc};

pub const EXIT_NO_OPTIONS: i32 = 13;

pub fn run_models(
    args: &[String],
    client: &dyn NewThreadClient,
    clock: &dyn Clock,
    stdout: &mut dyn Write,
    stderr: &mut dyn Write,
) -> i32 {
    let mut json = false;
    for arg in args {
        match arg.as_str() {
            "--help" | "-h" => {
                let _ = stdout.write_all(
                    crate::response::help(
                        crate::response::Request::for_command("models", args).json,
                        help(),
                    )
                    .as_bytes(),
                );
                return EXIT_OK;
            }
            "--json" => json = true,
            other => {
                let _ = writeln!(
                    stderr,
                    "openwiz: models takes only --json, not {}; nothing was read (see openwiz \
                     --help)",
                    clean(other)
                );
                return EXIT_USAGE;
            }
        }
    }
    let deadline = clock.monotonic() + READ_TIMEOUT;
    let options = cloud_options(client.catalogue(deadline), client.cli_levels(), clock.now());
    let printed = if json {
        let mut out = serde_json::to_string_pretty(&options)
            .unwrap_or_else(|e| format!("{{\"error\": \"{e}\"}}"));
        out.push('\n');
        out
    } else {
        render_options(&options)
    };
    let _ = stdout.write_all(printed.as_bytes());
    let _ = stdout.flush();
    match options.state {
        OptionsState::Offered => EXIT_OK,
        OptionsState::NoOptions { .. } => EXIT_NO_OPTIONS,
    }
}

pub fn render_options(options: &CloudOptions) -> String {
    let mut out = format!(
        "openwiz models · read {} · {}\n",
        utc(options.read_at),
        clean(&options.label)
    );
    if let OptionsState::NoOptions { text, .. } = &options.state {
        out.push_str(&format!("no options: {}\n", clean(text)));
    }
    for harness in &options.harnesses {
        out.push_str(&format!(
            "{} (spawn provider {})\n",
            clean(&harness.harness),
            clean(&harness.provider)
        ));
        for model in &harness.models {
            out.push_str(&format!(
                "  {}: {}\n",
                clean(&model.model),
                clean(&model.efforts.join(", "))
            ));
        }
    }
    for harness in &options.unavailable {
        out.push_str(&format!(
            "{}: {}\n",
            clean(&harness.harness),
            clean(&harness.text)
        ));
    }
    out
}
