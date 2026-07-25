# Snapshot: 2026-07-25 11:32

## Context
The Codex→ClaudeCode 403 is resolved in the installed skill through a strict, user-approved truthful CLI identity fallback. Gateway allowlisting of the official `sdk-cli` identity remains the preferred long-term governance fix.

## Recent Progress
- Completed a real adapter gate with `claude-cli/2.1.216`: `APPROVE WITH NITS`, `$0.64111725`, one attempt/one success.
- Implemented strict opt-in validation and child identity isolation through TDD; 12/12 tests pass.
- Updated skill/protocol/README with the governance and usage boundaries.
- Synchronized and independently verified `/Users/gaotu/.cc-switch/skills/cross-agent-review`.

## Current Focus
Task complete. Use the installed compatibility option only for the diagnosed gateway policy and only after explicit user approval.

## Blockers
_(none)_

## Next Session Should Know
- Preferred long-term fix: configure the gateway to allow the official `sdk-cli` User-Agent.
- Current installed fallback: `--claude-user-agent claude-cli/<installed-semantic-version>`; never use `claude-vscode` or arbitrary headers.
- Use a fresh artifact key only for a materially revised artifact; never rotate keys to bypass the fixed attempt cap.
