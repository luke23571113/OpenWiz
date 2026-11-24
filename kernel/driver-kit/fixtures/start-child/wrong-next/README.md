# A driver whose start runs a short-lived child

Login: stays on your machine
Effort: passed as `--effort <level>`

The kit's own fixture: it refuses every effort with a `next` other than the refusal text. Its start without effort runs a child holding a credential on its command line, which exits before start answers.
