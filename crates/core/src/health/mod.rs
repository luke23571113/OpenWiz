pub mod model;

use model::Repository;

const LOOP_PREFIX: &str = "launch-fleet ";

pub fn is_openwiz_loop(name: &str, repository: &Repository) -> bool {
    let word = repository.to_string();
    name.starts_with(LOOP_PREFIX) && name.split(' ').any(|w| w == word)
}
