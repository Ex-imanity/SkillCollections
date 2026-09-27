# Client repository scenarios

Self-contained synthetic excerpts, not real Gaotu code or runnable projects. Return
small implementation sketches, evidence selection, conflicts and minimal verification.
Do not install tools, build a business repository, or claim device tests passed.

## S10: RN helper and Harmony native binding

Task: expose existing native saveDraft to callers through DraftHelper. Keep the API
and bridge protocol stable. The RN Spec defines:

```typescript
interface Spec {
  saveDraft(id: string, raw: string, overwrite: boolean): Promise<string>
}
```

The target RN module's tracked rules use named exports, explicit Promise types,
two spaces, no semicolons and existing NativeDraft access. A nearby legacy helper:

```typescript
export function legacySave(id: string, raw: string, overwrite: boolean) {
  return new Promise((resolve) => {
    NativeDraft?.saveDraft(id, raw, overwrite).then(resolve)
  })
}
```

NativeDraft is optional in old products. Current DraftContract says missing module
must reject using existing createCapabilityError('saveDraft'); native failure must
propagate, raw JSON string remains raw, id is string and overwrite=false is valid.
Do not create a new error format, parse/re-serialize raw or silently succeed.

Harmony's ArkTS implementation is already complete and matches the three arguments.
This package's generated C++ NativeDraft.cpp methodMap has loadDraft only. The tracked
generator input registry lists loadDraft only, too. The project's codegen procedure
uses this registry to emit ARK_ASYNC_METHOD_METADATA(method, arity). Identify the
minimal source and generated-registration change needed, without running a generator.
A prior patch hand-edits C++ only. This is a fixture generator contract, not an
instruction to edit actual Gaotu generator inputs or trust arbitrary generated files.

## S11: Android Fragment instance vs view lifetime

Task: add a listener that renders status into a Fragment view after a network result.
The target Kotlin module uses private named handlers, Repository, UiState, and
repeatWithViewLifecycle for collection. Its existing instance EventBus registration
and unregister are in onCreate/onDestroy. Do not change that existing scope.

`fixture/android/StatusFragment.kt` has _binding available only between onViewCreated
and onDestroyView; the binding getter force unwraps. The instance survives navigation
that destroys/recreates its view. Target Repository exposes status: StateFlow<UiState>.
repeatWithViewLifecycle launches collection for the current view and cancels it when
that view is destroyed; it emits the latest StateFlow value to a new view.

A legacy callback starts work in lifecycle.coroutineScope, captures binding, and
updates that old binding after completion. Current status refresh already belongs to
ViewModel and should continue without a visible view. Add only UI observation/rendering;
do not move fetch into view lifecycle, buffer all EventBus events or adopt a new stack.
Use the target's repository and collection conventions rather than assuming that a
method named lifecycle automatically covers the Fragment's view lifetime.

## S12: iOS reused cell callback identity and queue

Task: show an asynchronously loaded subtitle on a reusable Objective-C cell.
The module uses private properties and named rendering methods, 4-space indentation,
and the existing SubtitleService. The service invokes its completion on a background
queue; the request cannot be reliably cancelled. The same item ID can be rebound with
a newer version, so matching only the item ID is insufficient.

`fixture/ios/SubtitleCell.m` owns subtitleLabel, representedID and a monotonically
increasing NSUInteger bindingGeneration. The current bindItem increments the generation,
sets representedID and clears the label on the main thread. prepareForReuse also
increments bindingGeneration and clears representedID and the label on the main thread.
SubtitleService accepts itemID and revision; completion receives NSString *text.

Add only the asynchronous request completion behavior. Preserve the existing generation
updates. UI mutation and the final generation check belong on the main queue; a result
for a destroyed cell must be ignored. A legacy block captures self strongly and checks
representedID before dispatching to main. No new global lock or replacement loader is
requested. The header's public API and raw service response contract stay unchanged.

## Evaluation request

For S10-S12 state the concrete local changes and the smallest meaningful checks. Distinguish
completion promises from streaming/state notifications and build registration from runtime
implementation. Do not infer personal identity or company-wide style from these fixtures.
