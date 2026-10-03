# Working with this Diversion repository

This repository uses Diversion for version control. Use the `dv` CLI to manage it.
Repository metadata lives in `.diversion/`; do not edit it manually.

## Basic workflow

Run commands from the repository directory:

```sh
dv status                         # Check the branch, local changes, and sync status
dv diff                           # Inspect uncommitted changes
dv branch                         # List branches
dv branch -c feature-name         # Create and switch to a feature branch
dv branch-name                    # Confirm the current branch before committing
dv commit -a -m "Describe the change"  # Commit all pending changes
dv log                            # View commit history
dv checkout main --take-changes   # Switch branches; keep uncommitted changes with you
dv merge feature-name --into main # Merge the feature branch into the target branch
dv review "Describe the change" --into main # Open a review for the current branch
```

Use the repository's actual target branch name in place of `main`. Open a review
from your feature branch before merging, and follow the team's review process.
Inspect `dv diff` before `commit -a`: it includes all pending changes, including
changes made by other people or agents in this workspace.

## Sync and safe changes

- Diversion automatically syncs files and commits with the cloud; no manual
  push or pull is needed. File sync does not replace committing your work.
- `dv checkout` without a flag asks a question when the workspace has uncommitted
  changes, which blocks a non-interactive run. Always pass `--take-changes`,
  `--shelve-changes`, or `--discard-changes`; see `dv help checkout`.
- Use `.dvignore` for files that should not be tracked.
- Do not discard changes, delete branches, or merge work without authorization.

## More information

Run `dv help` to discover commands and `dv help <command>` for exact syntax and
options, especially before a command you have not used before.

Read https://docs.diversion.dev/llms.txt for the full documentation index, then
follow the relevant links for detailed guidance.
