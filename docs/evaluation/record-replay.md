# Evaluation Record/Replay

Default evaluation is replay-only and uses synthetic fixtures under
`eval/cases/synthetic` plus matching records under `eval/replay/synthetic`.
It must not call Crossref, OpenAlex, PubMed, MinerU, text LLMs, image semantic
LLMs, or imagedetector.

Record mode is explicit. A caller provides a recorder function, adapter name,
and model name to `veritas.evaluation.run_record_suite(...)`. Each record stores
the adapter, model, prompt version, schema version, risk rule version, input
hash, timestamp, and response.

When prompt, schema, or risk rules change, run the synthetic replay suite first.
If real public-paper calibration is needed, place those cases under
`eval/cases/public`, run explicit record mode, and review the newly recorded
fixtures before promoting them to replay data.
