# CLAUDE.md

This repo hosts Tampermonkey userscripts for tweaking the ELK/OpenSearch stack.

## Git workflow

Never run `git push` without explicit approval from the user.

Never run `git commit` without explicit approval from the user. Make code changes, then show what you've done and ask before committing.

## Adding a new script

1. Add the `.js` file to the repo root.
2. Update `README.md` with a section for the new script under `## Scripts`, including:
   - The filename
   - A short description of what it does
   - The `@match` URLs it targets
