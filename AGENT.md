# AGENT.md: Guidelines for Autonomous AI Agents

This repository uses [CLAUDE.md](CLAUDE.md) as its primary operating manual and instruction guide. All AI agents (Claude, Gemini, Antigravity, etc.) must read and follow [CLAUDE.md](CLAUDE.md) before performing modifications.

## Quick Summary for Entity Page Writing (Professors, Universities, Venues)

When rewriting or generating introductory text on entity pages (`/professors/<slug>/`, `/universities/<slug>/`, `/conferences/<slug>/` or `/venues/<slug>/`), follow the **Entity Page Writing Guidelines & Templates** defined in [CLAUDE.md](CLAUDE.md#entity-page-writing-guidelines--templates-professors-universities-venues):

1. **Avoid dense, robotic listing:** Never dump raw numbers in telegraphic style (avoid patterns like "80 bài trước năm 2027, 1 bài từ năm 2027" or "Tại ICLR: 5 bài nộp, 0 bài được chấp nhận..."). Weave data smoothly into complete sentences.
2. **Avoid densely packed subjects:** Keep subjects clear and light. Never nest long conditional clauses into subject phrases.
3. **No semicolons (`;`):** Use natural commas or periods.
4. **Bilingual symmetry:** Update both `frontend/i18n/vi.toml` and `frontend/i18n/en.toml` alongside layout templates (`frontend/layouts/{professors,universities,conferences}/single.html`).
5. **Quality Gate:** Run `make build` (must show zero warnings) and `make test` (all 33 unit tests must pass).
