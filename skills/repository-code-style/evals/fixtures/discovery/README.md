# Synthetic repository fixture

This directory supplies repository files for S4-S6. It is synthetic evidence,
not Gaotu source. Evaluate by inspecting the tree, including hidden tracked files.
The evaluator can copy this tree into a disposable Git repository and stage its
files so git ls-files has real tracking information. Do not commit or touch real repos.

Source and policy files in this fixture are team files. There is no AGENTS.md.
The task prompts deliberately do not identify which file contains the rules or
which enum constant should be used.

S4: Implement TaskService.shouldHandle(String value): true for non-null values.
S5: Replace TaskService.pageType()'s business literal with the existing enum,
preserving its numeric result. This page is historically called a home-page panel.
S6: Encapsulate TaskService.response()'s statistics into a small object, preserving
the current wire output and keeping the change internal.

Return implementation sketches, sources found, conflicts resolved and meaningful
verification suggestions. Do not edit this fixture during an evaluation and do
not claim compilation or serialization execution that was not performed.
