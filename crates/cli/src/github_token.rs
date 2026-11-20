use std::ffi::OsString;
use std::io::Write;
use std::sync::Arc;
use std::time::{Duration, Instant};

use openwiz_adapter_github::app::{self, CurlExchange, Exchange, Mode, Refusal, SecretApp};

use crate::{EXIT_NOT_FOUND, EXIT_OK, EXIT_READ_FAILED, EXIT_USAGE, UsageError};

pub const SECRET: &str = "OPENWIZ_GITHUB_APP_KEY";
pub const APP_ID: &str = "OPENWIZ_GITHUB_APP_ID";
pub const MODE: &str = "OPENWIZ_GITHUB_APP_MODE";
pub const EXIT_REFUSED: i32 = 5;
const BUDGET: Duration = Duration::from_secs(30);

pub const USAGE: &str = "  openwiz github token --repository OWNER/NAME [--read]\n";
pub const HELP: &str = "github token --repository OWNER/NAME [--read]
  Mints one GitHub App installation token (about an hour) for the installation
  that covers OWNER/NAME, from the App key in the OPENWIZ_GITHUB_APP_KEY secret
  and the App id in OPENWIZ_GITHUB_APP_ID. A user's own App (the default) mints
  only on its owner's account; OPENWIZ_GITHUB_APP_MODE=factory is the explicit
  setting for the factory's App and its named installations. Prints only the
  token on stdout and `expires_at <unix seconds>` on stderr; stores nothing.
  --read asks for the read-only profile. Exits 0 printed, 1 key, App id, mode
  or GitHub unavailable, 2 usage, 3 repository not installed, 5 refused.
";

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TokenArgs {
    pub repository: String,
    pub read: bool,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Parsed {
    Help,
    Token(TokenArgs),
}

pub fn parse(args: &[String]) -> Result<Parsed, UsageError> {
    let usage = |why: &str| Err(UsageError(format!("github token: {why}")));
    if args.iter().any(|a| a == "--help" || a == "-h") {
        return Ok(Parsed::Help);
    }
    let Some(rest) = args.strip_prefix(&["token".to_owned()]) else {
        return usage("the only github command is token");
    };
    let (mut repository, mut read) = (None, false);
    let mut args = rest.iter();
    while let Some(arg) = args.next() {
        let (flag, inline) = match arg.split_once('=') {
            Some((flag, value)) if flag.starts_with("--") => (flag, Some(value.to_owned())),
            _ => (arg.as_str(), None),
        };
        match flag {
            "--read" if inline.is_none() => read = true,
            "--repository" if repository.is_none() => {
                let Some(value) = inline.or_else(|| args.next().cloned()) else {
                    return usage("--repository needs OWNER/NAME");
                };
                repository = Some(value);
            }
            "--repository" => return usage("--repository is given once"),
            _ => return usage("unknown option or argument"),
        }
    }
    let Some(repository) = repository else {
        return usage("--repository OWNER/NAME is required");
    };
    let Ok(parsed) = openwiz_core::fleet::starts::Repository::parse(&repository) else {
        return usage("--repository is OWNER/NAME, as GitHub names them");
    };
    Ok(Parsed::Token(TokenArgs {
        repository: parsed.as_str().to_owned(),
        read,
    }))
}

pub struct Context {
    pub secret: Option<OsString>,
    pub app_id: Option<OsString>,
    pub mode: Option<OsString>,
    pub exchange: Arc<dyn Exchange>,
    pub clock: Arc<dyn app::Clock>,
}

impl Context {
    pub fn system() -> Self {
        Self {
            secret: std::env::var_os(SECRET),
            app_id: std::env::var_os(APP_ID),
            mode: std::env::var_os(MODE),
            exchange: Arc::new(CurlExchange),
            clock: Arc::new(app::SystemClock),
        }
    }
}

pub fn run(
    args: &[String],
    context: Context,
    stdout: &mut dyn Write,
    stderr: &mut dyn Write,
) -> i32 {
    let say = |stderr: &mut dyn Write, code: i32, line: &str| {
        let _ = writeln!(stderr, "openwiz: github token: {line}");
        code
    };
    let token = match parse(args) {
        Ok(Parsed::Help) => {
            return match stdout
                .write_all(HELP.as_bytes())
                .and_then(|()| stdout.flush())
            {
                Ok(()) => EXIT_OK,
                Err(_) => say(stderr, EXIT_READ_FAILED, "could not write output"),
            };
        }
        Ok(Parsed::Token(token)) => token,
        Err(UsageError(message)) => {
            let _ = writeln!(
                stderr,
                "openwiz: {message} (see openwiz github token --help)"
            );
            return EXIT_USAGE;
        }
    };
    let deadline = Instant::now() + BUDGET;
    let Some(app) = secret_app(context) else {
        return say(
            stderr,
            EXIT_READ_FAILED,
            "the App key, App id or App mode is missing or unreadable; no token was minted",
        );
    };
    let minted = match app.mint(&token.repository, token.read, deadline) {
        Ok(minted) => minted,
        Err(Refusal::Unavailable) => {
            return say(
                stderr,
                EXIT_READ_FAILED,
                "GitHub gave no complete answer; no token was minted",
            );
        }
        Err(Refusal::NotInstalled) => {
            return say(
                stderr,
                EXIT_NOT_FOUND,
                "the repository is not covered by an installation of this App",
            );
        }
        Err(Refusal::Refused) => {
            return say(
                stderr,
                EXIT_REFUSED,
                "GitHub refused the token (details withheld); no token was printed",
            );
        }
    };
    let mut line = minted.token;
    line.push('\n');
    if stdout
        .write_all(line.as_bytes())
        .and_then(|()| stdout.flush())
        .is_err()
    {
        return say(stderr, EXIT_READ_FAILED, "could not write output");
    }
    let _ = writeln!(stderr, "expires_at {}", minted.expires_at);
    EXIT_OK
}

fn secret_app(context: Context) -> Option<SecretApp> {
    let app_id = context.app_id?.into_string().ok()?;
    if app_id.starts_with('0') || !app_id.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    let app_id = app_id.parse::<u64>().ok()?;
    let mode = match context.mode.as_deref().map(|m| m.to_str()) {
        None | Some(Some("user")) => Mode::User,
        Some(Some("factory")) => Mode::Factory,
        Some(_) => return None,
    };
    let secret = context.secret?.into_string().ok()?;
    SecretApp::from_secret(&secret, app_id, mode, context.exchange, context.clock).ok()
}
