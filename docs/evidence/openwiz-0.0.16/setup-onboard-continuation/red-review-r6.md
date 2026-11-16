# Red run: review R6, an interrupted Decisions settings write (#636) at 78e39a4

The real helper's `decisions --yes` was killed (SIGKILL) just before its final replace, in an isolated recording folder; then the approved preview and yes were run again.

```text
FAIL: test_a_decisions_write_cut_short_before_its_replace_can_be_confirmed_again [no settings file]
AssertionError: 10 != 0 : Effect: set Decisions' repository pair in the private settings: public synthetic-owner/synthetic-sheep, private synthetic-owner/synthetic-sheep-brain. Restart the OpenWiz server afterwards.
FAIL: test_a_decisions_write_cut_short_before_its_replace_can_be_confirmed_again [an existing settings file]
AssertionError: 10 != 0 : Effect: set Decisions' repository pair in the private settings: public synthetic-owner/synthetic-sheep, private synthetic-owner/synthetic-sheep-brain. Restart the OpenWiz server afterwards.
Ran 1 test in 0.187s
FAILED (failures=2)
```

The fixed staging name `config.json.new` survives the interruption, and every later confirmation fails its exclusive open (exit 10), so the companion can never be connected.
