//! The models contract (`contracts/models.v1.md`, `openwiz.models.v1`): the
//! one `## Models` table in `docs/agents/fleet.md`, the older five tables it
//! replaces, and the follow, fixer and cross-family rules. [`read`] is the
//! shared reader (`openwiz models show` and the fleet tick); [`write::set`]
//! is the writer behind `openwiz models set`. No I/O: text in, text out.

use serde::Serialize;

pub mod write;

pub const FLEET_FILE: &str = "docs/agents/fleet.md";
pub const SNAPSHOT_FILE: &str = "docs/agents/models-offered.json";

/// The five roles, in the Models table's row order.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Role {
    Orchestrator,
    Builder,
    Reviewer,
    SmallBuilder,
    Fixer,
}

impl Role {
    pub const ALL: [Role; 5] = [
        Role::Orchestrator,
        Role::Builder,
        Role::Reviewer,
        Role::SmallBuilder,
        Role::Fixer,
    ];
    /// As the table and people write it.
    pub fn row(self) -> &'static str {
        [
            "Orchestrator",
            "Builder",
            "Reviewer",
            "Small builder",
            "Fixer",
        ][self as usize]
    }
    /// As the command line spells it.
    pub fn token(self) -> &'static str {
        [
            "orchestrator",
            "builder",
            "reviewer",
            "small-builder",
            "fixer",
        ][self as usize]
    }
    pub fn from_token(word: &str) -> Option<Role> {
        Role::ALL.into_iter().find(|r| r.token() == word)
    }
    /// Only the Small builder and the Fixer may follow the Builder.
    pub fn can_follow(self) -> bool {
        matches!(self, Role::SmallBuilder | Role::Fixer)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Family {
    Claude,
    Gpt,
}

impl Family {
    pub const BOTH: [Family; 2] = [Family::Claude, Family::Gpt];
    pub fn of(provider: &str) -> Option<Family> {
        match provider {
            "claude-code" => Some(Family::Claude),
            "codex" => Some(Family::Gpt),
            _ => None,
        }
    }
    pub fn shown(self) -> &'static str {
        match self {
            Family::Claude => "Claude",
            Family::Gpt => "GPT",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Names {
    pub harness: String,
    pub model: String,
    pub effort: String,
}

/// One harness, model and effort: the ids spawn takes and the names people
/// read.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Choice {
    pub provider: String,
    pub model: String,
    pub effort: String,
    pub family: Option<Family>,
    pub names: Names,
}

impl Choice {
    fn new(ids: [&str; 3], names: [&str; 3]) -> Choice {
        Choice {
            provider: ids[0].to_owned(),
            model: ids[1].to_owned(),
            effort: ids[2].to_owned(),
            family: Family::of(ids[0]),
            names: Names {
                harness: names[0].to_owned(),
                model: names[1].to_owned(),
                effort: names[2].to_owned(),
            },
        }
    }

    /// The choice `set` writes, with the contract's names, or `None` when
    /// its ids break the ids rule.
    pub fn named(provider: &str, model: &str, effort: &str) -> Option<Choice> {
        if !(is_id(provider) && is_model_id(model) && is_id(effort)) {
            return None;
        }
        let harness = match provider {
            "claude-code" => "Claude Code",
            "codex" => "Codex",
            other => other,
        };
        let name = match model {
            "claude-opus-5-5" => "Opus 5.5",
            "claude-sonnet-5-5" => "Sonnet 5.5",
            "gpt-6.2-sol" => "Sol 6.2",
            other => other,
        };
        let mut level = effort.to_owned();
        level[..1].make_ascii_uppercase();
        Some(Choice::new(
            [provider, model, effort],
            [harness, name, &level],
        ))
    }

    /// The same provider, model and effort: what spawns.
    pub fn same_spawn(&self, other: &Choice) -> bool {
        (&self.provider, &self.model, &self.effort)
            == (&other.provider, &other.model, &other.effort)
    }

    /// `Opus 5.5 Medium on Claude Code (claude-code claude-opus-5-5 medium)`.
    pub fn shown(&self) -> String {
        format!(
            "{} {} on {} ({} {} {})",
            self.names.model,
            self.names.effort,
            self.names.harness,
            self.provider,
            self.model,
            self.effort
        )
    }

    fn flags(&self) -> String {
        format!(
            "`--provider {} --model {} --reasoning-level {}`",
            self.provider, self.model, self.effort
        )
    }
}

/// A provider or effort id: letters, digits, `.`, `_` or `-`.
pub fn is_id(word: &str) -> bool {
    !word.is_empty()
        && word
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || "._-".contains(c))
}

/// A model id: one or more ids joined by `/`.
pub fn is_model_id(word: &str) -> bool {
    word.split('/').all(is_id)
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Follows {
    Builder,
}

/// A role as read: what it follows, and its choice (the Builder's when it
/// follows).
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct RoleRead {
    pub follows: Option<Follows>,
    pub choice: Choice,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Roles {
    pub orchestrator: RoleRead,
    pub builder: RoleRead,
    pub reviewer: RoleRead,
    pub small_builder: RoleRead,
    pub fixer: RoleRead,
}

impl Roles {
    pub fn get(&self, role: Role) -> &RoleRead {
        match role {
            Role::Orchestrator => &self.orchestrator,
            Role::Builder => &self.builder,
            Role::Reviewer => &self.reviewer,
            Role::SmallBuilder => &self.small_builder,
            Role::Fixer => &self.fixer,
        }
    }
}

/// What serves a family's review or fix round.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum From {
    Reviewer,
    Builder,
    Fixer,
    Waits,
    OlderTable,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Pick {
    pub from: From,
    pub choice: Option<Choice>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct ByFamily<T> {
    pub claude: T,
    pub gpt: T,
}

impl<T> ByFamily<T> {
    pub fn get(&self, family: Family) -> &T {
        match family {
            Family::Claude => &self.claude,
            Family::Gpt => &self.gpt,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Warning {
    SameFamily {
        family: Family,
        text: String,
    },
    OlderTableKept {
        table: &'static str,
        models_table: String,
        older: String,
        text: String,
    },
}

impl Warning {
    pub fn text(&self) -> &str {
        match self {
            Warning::SameFamily { text, .. } | Warning::OlderTableKept { text, .. } => text,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Form {
    ModelsTable,
    OlderTables,
}

/// `openwiz models show`'s report (`openwiz.models-show.v1`).
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Show {
    pub schema: &'static str,
    pub file: &'static str,
    pub read: Form,
    pub older_tables_present: bool,
    pub roles: Roles,
    pub reviews: ByFamily<Pick>,
    pub fixers: ByFamily<Pick>,
    pub warnings: Vec<Warning>,
}

/// The older rows `set` keeps in step, in the contract's order.
pub const OLDER_ROWS: [&str; 6] = [
    "Builder",
    "Builder for small tickets",
    "Reviewer for Claude-built",
    "Reviewer for GPT-built",
    "Fixer, Claude",
    "Fixer, GPT",
];

impl Show {
    /// What each older row resolves to, in [`OLDER_ROWS`] order; `None`
    /// waits.
    pub fn older_rows(&self) -> [Option<Choice>; 6] {
        [
            Some(self.roles.builder.choice.clone()),
            Some(self.roles.small_builder.choice.clone()),
            self.reviews.claude.choice.clone(),
            self.reviews.gpt.choice.clone(),
            self.fixers.claude.choice.clone(),
            self.fixers.gpt.choice.clone(),
        ]
    }
}

// ---- Parsing, with line positions for the writer ------------------------

const MODELS_HEADER: [&str; 5] = [
    "Role",
    "Harness",
    "Model",
    "Effort",
    "`room-cli thread spawn` flags",
];
const OLDER: [&str; 5] = [
    "Builder",
    "Builder for small tickets",
    "Reviewer for Claude-built",
    "Reviewer for GPT-built",
    "Fixer",
];
const FOLLOWS: &str = "follows Builder";

fn cells(line: &str) -> Option<Vec<String>> {
    let inner = line.strip_prefix('|')?.strip_suffix('|')?;
    Some(inner.split('|').map(|c| c.trim().to_owned()).collect())
}

/// The heading line and the end of exactly one `## <name>` section.
fn section(lines: &[&str], name: &str) -> Result<Option<(usize, usize)>, String> {
    let heading = format!("## {name}");
    let at: Vec<usize> = (0..lines.len()).filter(|&i| lines[i] == heading).collect();
    match at[..] {
        [] => Ok(None),
        [i] => {
            let end = (i + 1..lines.len())
                .find(|&j| lines[j].starts_with("## "))
                .unwrap_or(lines.len());
            Ok(Some((i, end)))
        }
        _ => Err(format!("more than one {heading}")),
    }
}

/// `--provider P --model M --reasoning-level E`, in one code span.
fn flags(cell: &str) -> Result<[&str; 3], String> {
    let inner = cell
        .strip_prefix('`')
        .and_then(|c| c.strip_suffix('`'))
        .ok_or("flags not in one code span")?;
    match inner.split(' ').collect::<Vec<_>>()[..] {
        ["--provider", p, "--model", m, "--reasoning-level", e]
            if is_id(p) && is_model_id(m) && is_id(e) =>
        {
            Ok([p, m, e])
        }
        _ => Err(format!("bad flags {inner:?}")),
    }
}

fn choice(names: [&str; 3], ids: [&str; 3]) -> Result<Choice, String> {
    if names.iter().any(|n| n.is_empty()) {
        return Err("an empty name cell".into());
    }
    Ok(Choice::new(ids, names))
}

/// The Models table: each row present, at its line, with its choice (`None`
/// when it follows).
struct ModelsTable {
    rows: Vec<(Role, usize, Option<Choice>)>,
    /// One past the last table line.
    end: usize,
}

fn models_table(lines: &[&str], (from, to): (usize, usize)) -> Result<ModelsTable, String> {
    let start = (from + 1..to)
        .find(|&i| lines[i].starts_with('|'))
        .ok_or("no Models table")?;
    let end = (start..to)
        .find(|&i| !lines[i].starts_with('|'))
        .unwrap_or(to);
    let rows: Vec<Vec<String>> = lines[start..end]
        .iter()
        .map(|l| cells(l).ok_or("not a table row"))
        .collect::<Result<_, _>>()?;
    if rows.len() < 2 || rows[0] != MODELS_HEADER || rows[1] != ["---"; 5] {
        return Err("bad Models header".into());
    }
    let mut out = Vec::new();
    let mut next = 0;
    for (i, row) in rows.iter().enumerate().skip(2) {
        if row.len() != 5 {
            return Err("a Models row without five cells".into());
        }
        let at = Role::ALL[next..]
            .iter()
            .position(|r| r.row() == row[0])
            .ok_or_else(|| format!("row {:?} out of place", row[0]))?
            + next;
        if at > next && next < 3 {
            return Err("a required row is missing".into());
        }
        let role = Role::ALL[at];
        let choice = if row[1] == FOLLOWS && row[2..].iter().all(String::is_empty) {
            if !role.can_follow() {
                return Err(format!("{} cannot follow", row[0]));
            }
            None
        } else {
            Some(choice([&row[1], &row[2], &row[3]], flags(&row[4])?)?)
        };
        out.push((role, start + i, choice));
        next = at + 1;
    }
    if next < 3 {
        return Err("a required row is missing".into());
    }
    Ok(ModelsTable { rows: out, end })
}

/// The older five tables: the four setting tables (with their Harness,
/// Model and Effort lines) and the Fixer's Claude and GPT rows.
struct Older {
    tables: [(Choice, [usize; 3]); 4],
    fixers: [(Choice, usize); 2],
}

fn setting_table(
    lines: &[&str],
    (from, to): (usize, usize),
) -> Result<(Choice, [usize; 3]), String> {
    let rows: Vec<(usize, Vec<String>)> = (from + 1..to)
        .filter(|&i| lines[i].starts_with('|'))
        .map(|i| cells(lines[i]).map(|c| (i, c)).ok_or("not a table row"))
        .collect::<Result<_, _>>()?;
    let mut names = Vec::new();
    let mut ids = Vec::new();
    let mut at = [0; 3];
    for (i, (setting, flag)) in [
        ("Harness", "--provider"),
        ("Model", "--model"),
        ("Effort", "--reasoning-level"),
    ]
    .into_iter()
    .enumerate()
    {
        let (line, row) = rows.get(i + 2).ok_or("a short table")?;
        let value = row
            .get(2)
            .and_then(|c| c.strip_prefix(&format!("`{flag} ")))
            .and_then(|c| c.strip_suffix('`'))
            .filter(|v| {
                row.len() == 3
                    && row[0] == setting
                    && (if i == 1 { is_model_id(v) } else { is_id(v) })
            })
            .ok_or_else(|| format!("bad {setting} row"))?;
        names.push(row[1].as_str());
        ids.push(value);
        at[i] = *line;
    }
    Ok((
        choice([names[0], names[1], names[2]], [ids[0], ids[1], ids[2]])?,
        at,
    ))
}

fn older_tables(lines: &[&str]) -> Result<Older, String> {
    let mut tables = Vec::new();
    for name in &OLDER[..4] {
        let range = section(lines, name)?.ok_or_else(|| format!("no ## {name}"))?;
        tables.push(setting_table(lines, range)?);
    }
    let (from, to) = section(lines, "Fixer")?.ok_or("no ## Fixer")?;
    let mut fixers = Vec::new();
    for family in Family::BOTH {
        let (at, row) = (from + 1..to)
            .filter_map(|i| cells(lines[i]).map(|c| (i, c)))
            .find(|(_, r)| r.len() == 5 && r[0] == family.shown())
            .ok_or_else(|| format!("no Fixer row {}", family.shown()))?;
        fixers.push((choice([&row[1], &row[2], &row[3]], flags(&row[4])?)?, at));
    }
    if tables[0].0.family.is_none() {
        return Err("older Builder of no known family".into());
    }
    Ok(Older {
        tables: tables.try_into().map_err(|_| "four tables")?,
        fixers: fixers.try_into().map_err(|_| "two fixers")?,
    })
}

impl Older {
    fn rows(&self) -> [Choice; 6] {
        [
            self.tables[0].0.clone(),
            self.tables[1].0.clone(),
            self.tables[2].0.clone(),
            self.tables[3].0.clone(),
            self.fixers[0].0.clone(),
            self.fixers[1].0.clone(),
        ]
    }
}

/// A `fleet.md` as parsed: the Models table when present, else the older
/// tables, and whether any older table heading is present.
struct Parsed<'a> {
    lines: Vec<&'a str>,
    models: Option<ModelsTable>,
    older: Option<Older>,
    older_present: bool,
}

fn parse(text: &str) -> Result<Parsed<'_>, String> {
    let lines: Vec<&str> = text.lines().collect();
    let older_present = OLDER
        .iter()
        .any(|name| lines.iter().any(|l| l.strip_prefix("## ") == Some(name)));
    let (models, older) = match section(&lines, "Models")? {
        Some(range) => (
            Some(models_table(&lines, range)?),
            older_tables(&lines).ok().filter(|_| older_present),
        ),
        None if older_present => (None, Some(older_tables(&lines)?)),
        None => return Err("no model settings".into()),
    };
    Ok(Parsed {
        lines,
        models,
        older,
        older_present,
    })
}

/// Reads a `fleet.md`: the Models table, or the older five tables when it is
/// absent, then the follow, fixer and cross-family rules. A refusal says
/// why; nothing is guessed.
pub fn read(text: &str) -> Result<Show, String> {
    Ok(resolve(&parse(text)?))
}

fn resolve(p: &Parsed) -> Show {
    let role = |follows: bool, c: &Choice| RoleRead {
        follows: follows.then_some(Follows::Builder),
        choice: c.clone(),
    };
    let (roles, older_picks) = match (&p.models, &p.older) {
        (Some(table), _) => {
            let builder = table.rows[1].2.clone().unwrap_or_else(|| unreachable!());
            let get = |r: Role| match table.rows.iter().find(|row| row.0 == r) {
                Some((_, _, Some(c))) => role(false, c),
                _ => role(true, &builder),
            };
            (
                Roles {
                    orchestrator: get(Role::Orchestrator),
                    builder: get(Role::Builder),
                    reviewer: get(Role::Reviewer),
                    small_builder: get(Role::SmallBuilder),
                    fixer: get(Role::Fixer),
                },
                None,
            )
        }
        (None, Some(older)) => {
            let builder = &older.tables[0].0;
            let (reviewer, fixer) = match builder.family {
                Some(Family::Claude) => (&older.tables[2].0, &older.fixers[0].0),
                _ => (&older.tables[3].0, &older.fixers[1].0),
            };
            let pick = |c: &Choice| Pick {
                from: From::OlderTable,
                choice: Some(c.clone()),
            };
            (
                Roles {
                    orchestrator: role(true, builder),
                    builder: role(false, builder),
                    reviewer: role(false, reviewer),
                    small_builder: role(false, &older.tables[1].0),
                    fixer: role(false, fixer),
                },
                Some((
                    ByFamily {
                        claude: pick(&older.tables[2].0),
                        gpt: pick(&older.tables[3].0),
                    },
                    ByFamily {
                        claude: pick(&older.fixers[0].0),
                        gpt: pick(&older.fixers[1].0),
                    },
                )),
            )
        }
        (None, None) => unreachable!("parse refuses a file with neither form"),
    };
    let (builder, reviewer, fixer) = (
        &roles.builder.choice,
        &roles.reviewer.choice,
        &roles.fixer.choice,
    );
    let (reviews, fixers) = older_picks.unwrap_or_else(|| {
        let review = |f: Family| {
            let other = |c: &Choice| c.family.is_some_and(|x| x != f);
            if other(reviewer) {
                Pick {
                    from: From::Reviewer,
                    choice: Some(reviewer.clone()),
                }
            } else if other(builder) {
                Pick {
                    from: From::Builder,
                    choice: Some(builder.clone()),
                }
            } else {
                Pick {
                    from: From::Waits,
                    choice: None,
                }
            }
        };
        let fix = |f: Family| {
            if fixer.family == Some(f) {
                Pick {
                    from: From::Fixer,
                    choice: Some(fixer.clone()),
                }
            } else if reviewer.family == Some(f) {
                Pick {
                    from: From::Reviewer,
                    choice: Some(reviewer.clone()),
                }
            } else {
                Pick {
                    from: From::Waits,
                    choice: None,
                }
            }
        };
        (
            ByFamily {
                claude: review(Family::Claude),
                gpt: review(Family::Gpt),
            },
            ByFamily {
                claude: fix(Family::Claude),
                gpt: fix(Family::Gpt),
            },
        )
    });
    let mut warnings = Vec::new();
    if let Some(f) = reviewer.family.filter(|f| builder.family == Some(*f)) {
        let shown = f.shown();
        warnings.push(Warning::SameFamily {
            family: f,
            text: format!(
                "The Reviewer and the Builder are both {shown} models, so reviews of {shown}-built work wait (ADR 0008)."
            ),
        });
    }
    let mut show = Show {
        schema: "openwiz.models-show.v1",
        file: FLEET_FILE,
        read: if p.models.is_some() {
            Form::ModelsTable
        } else {
            Form::OlderTables
        },
        older_tables_present: p.models.is_some() && p.older_present,
        roles,
        reviews,
        fixers,
        warnings,
    };
    if let (Some(_), Some(older)) = (&p.models, &p.older) {
        let now = show.older_rows();
        for (i, was) in older.rows().iter().enumerate() {
            if now[i].as_ref() != Some(was) {
                let (new, old) = kept_values(now[i].as_ref(), was);
                show.warnings.push(Warning::OlderTableKept {
                    table: OLDER_ROWS[i],
                    text: format!(
                        "Models table: {new}; older {} table kept at {old}; fleets start {old} until launch-fleet reads the Models table (MD4)",
                        OLDER_ROWS[i]
                    ),
                    models_table: new,
                    older: old,
                });
            }
        }
    }
    show
}

/// The kept line's two values: the model ids, or `waits`; when those are
/// equal, the model and effort; when those are too, all three ids.
fn kept_values(now: Option<&Choice>, was: &Choice) -> (String, String) {
    let forms = |c: Option<&Choice>| match c {
        None => ["waits".to_owned(), "waits".to_owned(), "waits".to_owned()],
        Some(c) => [
            c.model.clone(),
            format!("{} {}", c.model, c.effort),
            format!("{} {} {}", c.provider, c.model, c.effort),
        ],
    };
    let (a, b) = (forms(now), forms(Some(was)));
    let i = (0..3).find(|&i| a[i] != b[i]).unwrap_or(2);
    (a[i].clone(), b[i].clone())
}
