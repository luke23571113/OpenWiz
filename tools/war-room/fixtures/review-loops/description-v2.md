Closes #41

## Summary

`pantry export` refuses an existing destination.

## Rulings

1. Export refuses a folder destination as well as a file. Why: the ticket's "existing destination" covers both. Cost if wrong: low: a cook who meant to export into a folder picks a file name instead.
2. The refusal exits with status 2. Why: the CLI contract keeps 3 for network errors. Cost if wrong: high: a script that waits for status 3 misses the refusal and deletes its only copy.

## Facts

- **Branch:** `export-refuses`. **Head:** `4b1f0c9e2d7a5b3c8f6e1d0a9b2c4e7f5a3d1c08`.
