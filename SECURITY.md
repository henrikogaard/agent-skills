# Security Policy

## Supported content

Security fixes apply to the current `main` branch and the latest published release. This repository contains public skill instructions and supporting scripts; it must not contain secrets, private endpoints, personal data, or machine-specific credentials.

## Reporting

Report a suspected vulnerability through GitHub's private vulnerability reporting or security-advisory flow for this repository. Do not include working credentials, private user data, or unrelated sensitive logs in an issue or pull request.

## Public-safety boundary

The repository validator rejects vendor directories, internal hosting metadata,
machine-specific absolute paths, private hosting endpoints, and non-first-party
catalog ownership. Reviewers must also check scripts and documentation for
unsafe command execution, credential exposure, hidden network behavior, and
copied third-party material whose license or provenance is unclear.

GitHub secret scanning and push protection are enabled. CI also runs a pinned
Gitleaks action against full fetched history with comments, summaries, and
artifact uploads disabled. This keeps detections from being republished while
still blocking the change.

Public dashboard exports must use the default public schema. Detailed
`--privacy private` exports are operational data and must never be committed.

Third-party skills belong in the private `agent-baseline` vendor catalog and must not be published here.
