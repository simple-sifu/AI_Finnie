# CLAUDE.md

Project rules for Finnie (AI Finance Assistant). The product requirements are in [`docs/prd.md`](docs/prd.md).

## Git workflow

Every approved story or document is committed on its own new branch, pushed, and merged into `main` through a pull request. Never commit directly to `main`.

1. Start from an up-to-date `main`: `git checkout main && git pull`.
2. Create a new branch for the approved work:
   - Stories: `story/<epic>.<story>-<short-slug>` (for example, `story/1.4-project-setup`)
   - Documents: `docs/<short-slug>` (for example, `docs/architecture`)
3. Commit the work on that branch and push it: `git push -u origin <branch>`.
4. Open a pull request into `main`: `gh pr create --base main`.
5. Merge the pull request: `gh pr merge --merge`.
6. Sync locally: `git checkout main && git pull`.

Only work the PM has approved is merged into `main`. Work still awaiting approval stays marked as draft in the document itself.

When an **approved story** from `docs/prd.md` is **fully implemented**, the agent should **commit, push, open a PR, and merge to `main`** in the same session (see `.cursor/rules/approved-story-git.mdc`), unless the user asks to hold off.

Never commit secrets: `.env` is in `.gitignore`; commit `.env.example` instead.
