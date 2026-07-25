# Native Feishu Drive Markdown for case-lite

## Chosen approach

Add a single read-only MCP tool, `get_markdown_file_sections`. It accepts a native file token, `/file/` URL, or `/wiki/` URL that resolves to a `file` node. It returns either a compact section index or the exact original Markdown for selected section IDs.

This is preferred over parsing in case-lite because token handling and Feishu API calls belong to the MCP. It is preferred over converting Markdown to Docx because conversion would change content and lose the native file semantics.

## Tool contract

Input:

- exactly one of `url` or `file_token`
- `max_level` from 1 through 6, default 4
- `section_ids` optional; absent means index-only, present means return selected original sections
- `preview_chars`, default 300, only affects index output

Index fields:

- `id`, `title`, `level`, `section_path`
- `range.start_line` and `range.end_line`, both 1-based and inclusive
- `preview`, a direct truncated excerpt, not a summary

Selected-content rule: a section runs from its own heading through the line immediately before the next heading of equal or lower level. A selected parent therefore includes nested subsections exactly once. The caller deduplicates ancestor/descendant selections before writing the corpus.

Parser scope: UTF-8 Markdown using ATX headings (`#` through `######`) outside backtick or tilde fenced code blocks. Unsupported non-UTF-8 files and files without headings produce explicit, non-destructive results.

## TDD execution order

1. Add failing unit tests for direct file URL, wiki-file resolution, rejecting wiki Docx targets, and a client raw download response.
2. Add failing parser tests covering hierarchy, fence suppression, line ranges, and selected parent content.
3. Implement the client download method, resolver, parser, tool registration, and JSON response.
4. Add case-lite contract tests first, then update its skill and Feishu tool guide with a distinct native Markdown branch.
5. Run targeted automated suites plus a read-only invocation against the supplied real file.
6. Build `feishu-docx-blocks` 3.4.0, inspect with Twine, run a budget-approved ClaudeCode read-only review, and publish only after the gate passes.

## Non-goals

- No automatic selection of sections.
- No modification or upload of the Feishu Drive file.
- No alteration of existing Docx parsing, media downloading, or wiki child discovery semantics.
