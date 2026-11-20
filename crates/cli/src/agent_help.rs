pub fn render() -> String {
    let catalogue: serde_json::Value = serde_json::from_str(include_str!("agent-catalogue.json"))
        .expect("the embedded CLI catalogue is valid JSON");
    let mut text = serde_json::to_string(&catalogue).expect("the catalogue serializes");
    text.push('\n');
    text
}
