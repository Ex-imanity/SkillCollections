---
name: case-generation-strategy
description: Generate comprehensive, executable test cases from PRD, technical design, interaction docs, acceptance criteria, APIs, or telemetry specs. Use when the user asks for 测试用例, 测试点, 场景设计, case generation, APP/C-end, WEB/B-end, cross-end validation, or event/telemetry tracking coverage with boundary, exception, state-transition, consistency, and evidence assertions.
---

# Case Generation Strategy

## Goal
Turn requirement materials into complete, executable test cases. Optimize for coverage depth, stable granularity, observable assertions, and clear risk disclosure rather than simply listing happy-path checks.

## Trigger Fit
Use this skill when the user needs any of the following:
- Generate or review test cases from requirement documents, PRD, technical design, prototypes, APIs, or acceptance criteria.
- Design scenes/test points for APP (C-end), WEB (B-end), backend-admin flows, cross-end loops, or data-reporting flows.
- Validate telemetry/event tracking requirements such as `eventid`, trigger timing, event type, parameters, exposure/click/conversion chains.
- Strengthen existing cases for boundary, exception, role, state-transition, recovery, consistency, or observability coverage.

Do not use this skill for pure code-unit-test implementation unless the user asks for product-level test design.

## Input Triage
Require at least one concrete source:
- PRD / requirement document / user story
- technical design / API spec / data schema
- interaction design / prototype / page screenshots
- acceptance criteria / business rules / risk notes
- telemetry table containing event definitions, trigger timing, or parameters

Before generating cases, classify inputs:
1. **Functional Mode**: feature behavior, page flow, API behavior, permissions, or data consistency.
2. **Telemetry/Event Mode**: `eventid`, trigger timing, event type, parameter contract, reporting evidence.
3. **Hybrid Mode**: both functional acceptance and telemetry acceptance are required.

If the source is incomplete, continue with explicit assumptions unless one missing item blocks case design entirely. Put unresolved blockers in `Assumptions & Risks`.

## Reference Loading
- Read `references/general-test-design-strategy.md` when the request is broad or the scenario type is unclear.
- Read `references/pattern-library.md` for complex flows involving state matrices, strategy/fallback logic, cross-end metrics, time windows, frequency limits, or deduplication.
- Read `references/telemetry-event-testing.md` whenever event tables, `eventid`, exposure/click/conversion tracking, or parameter validation appears.
- Read `references/skill-evolution.md` only when improving this skill from new historical case samples.

## Generation Workflow
1. **Extract Scope**: summarize objective, roles, endpoints/pages, core entities, actions, dependencies, and explicit out-of-scope items.
2. **Select Mode**: choose Functional, Telemetry/Event, or Hybrid; keep functional and telemetry cases separated in Hybrid Mode.
3. **Build State Matrix**: cover user state, data state, object state, permission state, environment/lifecycle state, and feature-toggle state when applicable.
4. **Split Scenes**: split by user journey first, then by risk boundary; keep `scene = business subflow` and `test point = verifiable behavior`.
5. **Generate Points**: for every P0/P1 scene, include normal, boundary, exception, consistency, and recovery points.
6. **Attach Assertions**: every point must contain at least one observable signal: UI, API response, database/data view, log, metric, or event query evidence.
7. **Review Coverage**: mark covered/not covered, call out conflicts, assumptions, and residual risks before final output.

## Scene Design Rules
- Split by journey stages such as enter, browse, operate, submit, jump, return, refresh, and recover.
- Force state-switch checks: before/after login, before/after operation, before/after refresh, before/after return, before/after permission or feature-toggle change.
- Add at least one recovery scene for each critical flow: retry, rollback, degraded display, resume, or manual correction.
- Avoid flat document-chapter mapping; merge duplicated scenes and separate mixed-risk scenes.
- For list/detail/reporting flows, always include list-detail-export or detail-aggregate reconciliation where applicable.

## Test Point Template
Each test point should use this structure:

| Field | Requirement |
|---|---|
| ID | Stable scene-point ID, e.g. `S01-T03` |
| Priority | `P0` critical acceptance, `P1` common/risky path, `P2` extended compatibility |
| Type | normal / boundary / exception / permission / state / consistency / telemetry / recovery |
| Preconditions | user role, data setup, object state, environment, feature toggle |
| Steps & Data | concrete operation and key test data |
| Expected Result | user-visible or system-visible result |
| Assertions/Evidence | UI/API/data/log/event evidence path |

Do not write vague expected results such as “works normally” or “meets requirements”.

## Priority Rules
- `P0`: core business flow, money/data correctness, permission isolation, blocking failure, required telemetry acceptance.
- `P1`: common alternatives, key boundaries, recoverable exceptions, cross-state consistency, duplicate-submit/idempotency.
- `P2`: low-frequency compatibility, long-tail UI display, optional analytics, non-blocking edge cases.

## Required Coverage Angles

| Domain | Required Angles |
|---|---|
| APP / C-end | login/session matrix, cold/hot start, background/foreground, first load, refresh, pagination, empty/failure state, jump/back/position restore, weak network, retry, exposure-click-conversion chain |
| WEB / B-end | role-page-button-data permission matrix, filter/search/sort/pagination/reset, form validation, batch operation, idempotency, duplicate-submit prevention, list-detail consistency, export consistency, 4xx/5xx/partial success, audit logs |
| Cross-End | user action → capture/storage → aggregation → report display, detail vs aggregate reconciliation, immediate check plus delayed-final-consistency check |
| Backend/API | parameter validation, auth/authz, idempotency, concurrency, timeout/retry, partial failure, backward compatibility, data persistence and rollback evidence |

## Telemetry/Event Mode
When tracking requirements exist, generate dedicated telemetry scenes. Keep telemetry assertions separate from functional assertions unless Hybrid Mode explicitly requires a linked chain.

For each event, cover:
- **Trigger**: exact action, page state, exposure threshold, click area, conversion timing.
- **No-trigger**: UI changes without trigger, invalid state, repeated action inside dedup window, documented non-reporting paths.
- **Parameter Contract**: required fields, fixed values, enum coverage, dynamic value source, non-empty constraints.
- **Uniqueness/Dedup**: rapid click, repeated exposure, refresh, re-entry, tab switch, back/forward, background/foreground.
- **Cross-State**: login/logout, role/grade variants, feature-toggle on/off, empty/non-empty data.
- **Evidence**: device/user filter, event query tool, eventid, time window, expected count, key parameter assertions.

## Output Format
Return in this order:
1. `Scope Summary`
2. `Mode & Assumptions`
3. `State Matrix`
4. `Scene List`
5. `Test Points` grouped by scene, using the test point template
6. `Telemetry Contract Matrix` only when telemetry requirements exist: eventid, trigger, no-trigger, required params, dynamic params, dedup rule, evidence path
7. `Coverage Checklist`: covered vs not covered
8. `Assumptions & Risks`

If the user asks for a lightweight result, keep the same order but reduce each scene to the highest-value P0/P1 points.

## Quality Gates
Before final output, verify:
- Every P0/P1 scene has normal, boundary, exception, and recovery coverage unless explicitly not applicable.
- Every test point has an observable assertion through UI, API, data, log, metric, or event evidence.
- Cross-role, cross-state, cross-page, and cross-end checks are present when the requirement implies them.
- Telemetry/Event Mode includes trigger, no-trigger, parameter contract, dedup/uniqueness, and evidence path.
- Missing information is listed in `Assumptions & Risks`; do not silently invent product rules.
- Functional and telemetry granularity remains separated enough for execution ownership.

## Common Mistakes to Avoid
- Only writing happy-path points or copying requirement headings as scenes.
- Mixing scene and test-point granularity.
- Hiding assumptions inside expected results.
- Missing state-transition assertions after refresh, return, retry, permission change, or feature-toggle change.
- Ignoring permission differences, data consistency, export/report reconciliation, or telemetry no-trigger conditions.
- Writing cases that lack setup data, steps, or evidence path.

## References
- Pattern bank: `references/pattern-library.md`
- Universal checklist baseline: `references/general-test-design-strategy.md`
- Telemetry testing reference: `references/telemetry-event-testing.md`
- Skill expansion workflow (maintainers only): `references/skill-evolution.md`
