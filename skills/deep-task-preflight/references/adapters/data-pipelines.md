# Data and Multi-Output Pipelines Adapter

Use for extraction, normalization, batch processing, reports, model evaluation, and LLM
Judge or replay pipelines.

- Define the logical unit before extracting: record, page, user turn, attempt, stream,
  grouped output, or session. Define how continuous grouped output differs from a retry or
  regenerated attempt, and how incomplete boundaries are represented.
- Preserve all relevant items until the final projection. Never use the first item or first
  text field as a completeness shortcut without a proven contract.
- At every boundary verify source date/revision, query/filter conditions, sample scope,
  cardinality, ordering, structured fields, references, and media/file availability.
- For a downstream evaluator or report, verify the evidence contract before changing its
  prompt or scoring logic: the intended data set, scope, full payload, references, and
  structured details must actually enter the request. A downstream prompt cannot restore
  evidence dropped by an upstream extractor.
- If a run reuses an existing data set, label it as re-evaluation and state what changed;
  do not present a prompt-only rerun as newly queried data.
- Retain enough provenance to compare source input, normalized input, request payload,
  stored result, and displayed result. Missing evidence should fail closed or be marked
  uncertain rather than guessed away.
