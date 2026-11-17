# Red run: the unchanged launch calls the engine's tick (#636, J87 Q1)

The unchanged helper's launch preview, given the installed openwiz it asks for, on the recorded journey's state. The assertion is the claim: the launch calls no engine or tick.

```text
F
======================================================================
FAIL: test_old_launch_calls_the_engine_tick (__main__.Red.test_old_launch_calls_the_engine_tick)
----------------------------------------------------------------------
Traceback (most recent call last):
AssertionError: Lists differ: [['fleet', 'tick', '--dry-run', '--json']] != []

First list contains 1 additional elements.
First extra element 0:
['fleet', 'tick', '--dry-run', '--json']

- [['fleet', 'tick', '--dry-run', '--json']]
+ [] : the launch must call no engine or tick

----------------------------------------------------------------------
Ran 1 test in 5.007s

FAILED (failures=1)
Could not read the engine's dry run; nothing started.

```
