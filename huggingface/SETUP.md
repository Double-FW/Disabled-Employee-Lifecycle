# Weekly employee lifecycle dataset sync

Destination: [GarethFW/Disabled_Employee_Customer_Lifecycle](https://huggingface.co/datasets/GarethFW/Disabled_Employee_Customer_Lifecycle). The supplied destination name is preserved. Current source content concerns employees, candidates and optional alumni contact; it does not supply a general customer-lifecycle framework.

1. The workflow already names `GarethFW/Disabled_Employee_Customer_Lifecycle` as its destination. No repository variable is required. If `HF_DATASET_ID` already exists, it must have that exact value; review [Actions variables](https://github.com/Double-FW/Disabled-Employee-Lifecycle/settings/variables/actions). A wrong override stops publication.
2. Open [Hugging Face tokens](https://huggingface.co/settings/tokens). Create a Fine-grained/Custom token scoped only to this dataset, with repository read/write access. Copy the generated `hf_` value privately.
3. Open [Actions secrets](https://github.com/Double-FW/Disabled-Employee-Lifecycle/settings/secrets/actions). Add or update `HF_TOKEN` using an underscore, with that token value. Do not share it in chat or paste the dataset name into its value.
4. Open [the sync workflow](https://github.com/Double-FW/Disabled-Employee-Lifecycle/actions/workflows/huggingface-sync.yml), choose Run workflow on main, then inspect the publishing result and destination Files tab before declaring the sync complete.

Schedule: Monday 10:55 UTC (10:55 UK winter, 11:55 UK summer). GitHub may delay scheduled jobs or disable schedules after inactivity. Manual Run workflow remains available.

## Export coverage and source status

Seven complete guidance documents appear in documents.jsonl. Six phase records in lifecycle_phases.jsonl are an alternative view of the same complete main guide: shared prefix/suffix retain status, overview, transition guidance, manager capability and source qualifications. Do not treat overlapping views as independent evidence.

The full opinion article and edited AI conversation appear only in historical_material.jsonl, with original publication date, content-type metadata and explicit opinion/transcript/evidence limitations. They are not empirical model results, factual HR answers or an instruction-tuning conversation. All nine original guidance/historical/licence files are explicitly covered, with hashes and export roles in provenance; related GitHub links are retained. External linked bodies are not fetched or copied.

New committed content outside the reserved .github/, scripts/, tests/ and huggingface/ implementation directories stops publication until reviewed and classified. A source allowlist entry alone cannot silently omit a source body. Those directories are reserved for implementation/setup, not substantive guidance. Source metadata, main-guide and agent versions, unassigned adoption/approval, source bytes and the approved licence are checked before publication. This does not detect all sensitive information or establish legal clearance; review changes before a public commit.

Eight output files are managed: README.md, LICENSE, NOTICE.md, documents.jsonl, lifecycle_phases.jsonl, historical_material.jsonl, provenance.json and record_schema.json. Updates are atomic against the destination revision, preserving unrelated files, .gitattributes and visibility. No-change runs create no extra dataset commit. Source GitHub public status is checked with the automatically supplied read-only GITHUB_TOKEN; no extra GitHub token is needed. HF_TOKEN is supplied only to the publishing step. No test/audit report is published in source or dataset; diagnostics stay in workflow logs.

## Local checks

Install huggingface/requirements.txt, then run `python scripts/export_huggingface.py --check-only` and `python -m unittest discover -s tests -v`. Build outside the checkout using `python scripts/export_huggingface.py --output /tmp/lifecycle-preview --dataset-id GarethFW/Disabled_Employee_Customer_Lifecycle`. Regression tests use a simulated destination without real credentials. They test source extraction and publishing safeguards, not employees, models, law, privacy compliance or deployed control systems.
