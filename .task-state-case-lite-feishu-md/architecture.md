# Architecture: Native Feishu Drive Markdown

## Ownership

- `feishu-docx-blocks`: resolve native Drive file URLs, download Markdown bytes through Feishu Drive, parse headings, return exact selected content.
- `case-lite`: identify document kind, show the returned section tree, record the user's choice, and append returned original Markdown to the corpus.
- Existing Docx path: remains `parse_document_id` -> `extract_document_structure` -> `get_document_blocks` and optional media tools.

## Data Flow

1. A user supplies a `/file/<token>` URL or a `/wiki/<node>` whose resolved object type is `file`.
2. `get_markdown_file_sections` resolves the token, downloads the bytes read-only, decodes UTF-8, and derives ATX headings outside fenced code blocks.
3. Without `section_ids`, the tool returns a compact section index. With `section_ids`, it returns the original heading-to-boundary slices.
4. case-lite writes the index to `chapters/` and selected content to `corpus/selected-corpus.md` without summarizing or rewriting it.

## Compatibility Rules

- The new tool rejects non-file wiki targets with an actionable message rather than falling through into Docx APIs.
- It has no write endpoint or file mutation behavior.
- Markdown image and attachment references remain source text. The current Docx image/board download sequence applies only to Docx blocks.
