# Technical report publication

Author: Karl von Poncet (sole author; no affiliation or ORCID supplied).

Title: A Conformance Harness for Agent Retry Decisions Under Commit Ambiguity

Version: 1.0

Release: https://github.com/KarlvonPoncet/agent-retry-safety/releases/tag/paper-v1.0

The report and research artifacts are CC BY 4.0; code is MIT. The AI-assistance
statement is included in the report. No DOI has been minted or reserved.

## Zenodo handoff

1. Create an account at https://zenodo.org/signup/ and complete any verification.
   GitHub or ORCID sign-in is also available. Account creation and acceptance of
   service terms must be completed by the author.
2. Create a new upload. Use resource type **Publication / Report**, the sole
   creator **Karl von Poncet**, and public access. Copy the title, abstract,
   keywords, version, and license from `zenodo-metadata.json`. Set the publication
   date to the actual first-publication date rather than the evidence snapshot.
3. Upload `agent-retry-safety-report.pdf` and the source/evidence ZIP attached
   to the GitHub release. The separate SHA256SUMS file verifies their integrity.
   Code in the ZIP retains MIT terms as explained in its LICENSE file.
4. Answer **No** to the existing-DOI question. Zenodo can reserve a DOI before
   publication. If a DOI is reserved, provide it before freezing an updated PDF;
   do not represent a reserved DOI as registered until publication succeeds.
5. Preview the record, check authors, files, licensing, abstract, and version,
   then publish. Share the resulting record URL and DOI so the repository's
   citation metadata and README can be linked to the deposit.

Prepared `zenodo-metadata.json` uses Zenodo's deposit API metadata shape. It is
also a copyable reference for the web form; uploading the JSON alone does not
populate or publish a Zenodo record.

No Zenodo account or API credential was available during release preparation.
No Zenodo record or arXiv submission has been created. This GitHub technical
report release is not peer-reviewed acceptance.

## Verified reproduction

Install `.[dev,paper]`, run the tests and offline claim validator as documented
in README.md, then build HTML with `make -C paper` and the PDF with
`make -C paper pdf`. Raw historical model actions are archived; reproducing
fresh model inference is a separate, optional process that needs credentials
and does not establish historical process isolation.

## Optional arXiv submission

The PDF, sole-author metadata, and disclosure are ready for an author-led
submission, subject to arXiv's moderation and endorsement requirements. No
arXiv endorsement or author account was supplied. arXiv posting is not required
for the Zenodo/GitHub technical report release and is not peer review.

Official instructions:

- https://help.zenodo.org/docs/deposit/create-new-upload/
- https://help.zenodo.org/docs/deposit/describe-records/reserve-doi/
- https://info.arxiv.org/help/submit/index.html
