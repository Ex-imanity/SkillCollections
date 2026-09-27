# Skill Evolution Guide (Maintainers)

Use this document only when improving the skill itself from new historical cases.

## Purpose
Extract reusable patterns from new case samples and update the skill/reference set without overfitting to one business domain.

## Workflow
1. Collect new case sample and parse structure.
2. Identify reusable strengths and LLM-missed boundaries.
3. Rewrite findings into domain-agnostic rules.
4. Update `pattern-library.md` with concise incremental patterns.
5. Update `SKILL.md` only when a rule is stable across multiple cases.

## Abstraction Rules
- Convert business nouns to generic terms (role, entity, detail page, event type, fallback path).
- Prefer capability statements over feature names.
- Keep one case insight = one generic rule.

## Update Threshold
Promote a rule into `SKILL.md` only if it is:
- high-impact,
- repeatable across cases,
- not already covered by existing baseline rules.
- concise enough to justify token cost in always-loaded skill body.

## Keep Out of SKILL.md
- case-by-case learning logs,
- raw API payload details,
- one-off business-specific terminology.
- auxiliary docs like README/CHANGELOG/installation notes.

Store raw case JSON and analysis notes outside this skill folder (e.g. project `tmp` work directories).
