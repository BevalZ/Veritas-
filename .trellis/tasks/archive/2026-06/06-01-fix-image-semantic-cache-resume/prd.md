# fix-image-semantic-cache-resume

## Goal

Fix image semantic analysis resume/cache behavior so interrupted paper audits can continue reliably, while avoiding reuse of stale semantic results after provider/model/API/cache-version changes.

## What I Already Know

* The user observed that image semantic analysis did not resume and did not appear to save a local file.
* Current code writes a visible `image_semantic_cache.json`, but cache lookup is keyed only by image fingerprint.
* Current load behavior chooses hidden resume cache or visible local cache, so entries can be lost when both files exist.
* User-facing wording must remain `图像语义分析`, not `GLM`.

## Requirements

* Cache keys for image semantic analysis must include image identity and semantic-service context so provider/model/API/cache-version changes do not reuse stale results.
* Hidden resume cache and visible `image_semantic_cache.json` must be merged on load.
* Completed image semantic results must be persisted to the visible cache during interrupted runs.
* Existing legacy config compatibility can remain internal, but user-facing docs/messages should continue using `图像语义分析`.

## Acceptance Criteria

* [x] Same image with a different semantic model/API/cache version triggers a fresh semantic call.
* [x] Hidden resume cache and visible cache entries are both available after load.
* [x] Interrupted runs retain completed semantic results in visible `image_semantic_cache.json`.
* [x] Focused tests pass, then full `tests/test_core.py` passes.
* [x] `veritas/legacy.py` and `paper_audit.py` compile.

## Out of Scope

* PubPeer/Letter article identity editor changes.
* Replacing the third-party semantic service implementation.
* Broad CLI/report redesign.

## Technical Notes

* Likely code locations: `veritas/legacy.py` image audit loop and stage-4 cache load/save.
* Follow existing JSON cache helpers and test style.
