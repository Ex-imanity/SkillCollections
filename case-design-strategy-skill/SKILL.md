---
name: case-generation-strategy
description: Generate comprehensive test cases from requirement inputs (PRD, technical design, interaction docs, acceptance criteria). Use when an agent needs to design test scenes and test points for APP (C-end), WEB (B-end), cross-end workflows, or telemetry/event-tracking validation with strong boundary, exception, and state-transition coverage.
---

# Case Generation Strategy

## Goal
Generate complete, executable test cases from requirement materials, with explicit coverage of main flow, boundary, exception, state transition, and observability.

## Mode Selection
- Use **Functional Mode** when requirements focus on feature behavior and user flows.
- Use **Telemetry/Event Mode** when docs provide event definitions (`eventid`, trigger timing, parameters).
- Use **Hybrid Mode** when both functional acceptance and telemetry acceptance are required.
- Keep outputs separated by mode; do not mix telemetry assertions into pure functional points.

## Inputs
Require at least one of:
- PRD / requirement document
- technical design / API spec
- interaction design / prototype
- acceptance criteria / business rules

If information is missing, list assumptions explicitly before generating cases.

## Generation Workflow
1. Extract requirement scope: objectives, user roles, core entities, key actions, dependencies.
2. Build a state matrix: user state, data state, object state, environment state.
3. Split test scenes by user journey and risk boundaries.
4. Generate test points per scene with "normal + boundary + exception" coverage.
5. Add cross-checks for permissions, consistency, telemetry, and recovery behavior.
6. Resolve requirement conflicts by recording assumptions explicitly.
7. Output structured cases with priority and clear assertions.

## Scene Design Rules
- Split scenes by journey first, then by risk.
- Keep granularity stable: scene = business subflow; test point = verifiable behavior.
- Force state-switch coverage: before/after login, before/after operation, before/after refresh, before/after return.
- Include at least one recovery scene for each critical flow.

## Test Point Design Rules
Each critical scene must include:
- Main-flow correctness
- Boundary behavior (limits, empty set, edge timestamps, coexistence conflicts)
- Exception behavior (timeout/failure/invalid state/degraded path)
- Data and UI consistency
- Event/telemetry observability (if applicable)

## Telemetry/Event Mode (when tracking requirements are provided)
When requirement docs include event tables (for example: page/module, eventid, trigger timing, event type, parameters), generate dedicated telemetry test scenes and points with:
- Trigger vs non-trigger conditions (what should report and what must not report).
- Parameter contract checks (required fields, enum values, dynamic fields).
- Event uniqueness/dedup checks (rapid actions, repeated exposure, re-entry).
- Context-switch checks (tab switch, refresh, background/foreground, return from subpage).
- Cross-state checks (logged-in/logged-out, feature-toggle on/off, grade/role variants).
- Verification method clarity (device/user filter, event query tool, expected query evidence).

## APP (C-end) Required Angles
- Login/session matrix and return path.
- Lifecycle: cold start, hot start, background/foreground.
- Content flow: first load, refresh, pagination, empty state, failure state.
- Interaction continuity: jump/back/position restore.
- Weak-network and retry behavior.
- Client events: exposure/click/conversion chain.

## WEB (B-end) Required Angles
- Role-permission matrix: page/button/data scopes.
- Query system: filter/search/sort/pagination/reset.
- Form and batch operations: validation/idempotency/duplicate-submit prevention.
- List-detail consistency after operations.
- Error governance: 4xx/5xx/partial success/rollback hint.
- Auditability: operation logs and exported-data consistency.

## Cross-End Required Angles
- End-to-end loop: user action -> event capture -> data aggregation -> report display.
- Metric consistency: detail-level vs aggregate-level reconciliation.
- Sync window: immediate check and delayed-final-consistency check.

## Output Format
Return in this order:
1. `Scope Summary`
2. `State Matrix`
3. `Scene List`
4. `Test Points` (grouped by scene, each with priority and expected result)
5. `Telemetry Contract Matrix` (only when telemetry requirements exist: eventid, trigger, no-trigger, required params, verification evidence)
6. `Coverage Checklist` (what is covered vs not covered)
7. `Assumptions & Risks`

## Quality Gates (before final output)
- Every P0/P1 scene has explicit normal, boundary, and exception points.
- Every test point has at least one observable assertion (UI/API/data/log/event).
- Cross-role, cross-state, and cross-end checks are present when applicable.
- Telemetry mode includes trigger + no-trigger + parameter contract + evidence path.
- Missing information is reflected in `Assumptions & Risks`, not silently guessed.

## Common Mistakes to Avoid
- Only writing happy-path points.
- Missing state-transition assertions.
- Mixing scene and test-point granularity.
- Ignoring permission differences and consistency checks.
- Writing vague expected results that cannot be asserted.

## References
- Pattern bank: `references/pattern-library.md`
- Universal checklist baseline: `references/general-test-design-strategy.md`
- Telemetry testing reference: `references/telemetry-event-testing.md`
- Skill expansion workflow (maintainers only): `references/skill-evolution.md`
