# Technical report v1.0

Karl von Poncet's *A Conformance Harness for Agent Retry Decisions Under Commit
Ambiguity* presents an inspectable synthetic conformance harness and a qualified
historical model pilot. It is a technical report, not a peer-reviewed publication.

The report distinguishes duplicate effects, exact-state correctness, observed
completion within a trial budget, and recovery cost. The pilot found no safety
or completion improvement across three prompts. Historical model-process
isolation was not established, guidance content differs across treatments, and
execution provenance is incomplete; stronger empirical claims require a new
isolated, replicated study.

Evidence: 11,520 deterministic rows; 432 historical model configurations,
including 288 model-exercised trajectories and 400 decisions. No fresh model
inference was run for this release. Offline action replay reproduced every
historical model row. All 50 tests, lint, headline-claim checks, and archived
artifact checksums passed. The PDF was rendered and visually inspected.

Assets:

- `agent-retry-safety-report.pdf`: sole-author publication copy, with hyperlinks,
  page numbers, and an AI-assistance disclosure.
- `agent-retry-safety-paper-v1.0-source-evidence.zip`: frozen repository snapshot,
  including raw evidence, analysis, source, licenses, and reproduction commands.
- `zenodo-metadata.json`: prepared metadata for a Publication / Report deposit.
- `SHA256SUMS`: checksums of the attached files.

Licenses: CC BY 4.0 for the report and research artifacts; MIT for code. Third-party
works cited in the bibliography retain their own terms.

Zenodo publication awaits the author's account access. No DOI has been assigned.
Citation metadata and upload instructions are included in the source snapshot.
