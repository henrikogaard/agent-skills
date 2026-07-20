# Security Policy

## Supported content

Security fixes apply to the current `main` branch and the latest published release. This repository contains public skill instructions and supporting scripts; it must not contain secrets, private endpoints, personal data, or machine-specific credentials.

## Reporting

Report a suspected vulnerability through GitHub's private vulnerability reporting or security-advisory flow for this repository. Do not include working credentials, private user data, or unrelated sensitive logs in an issue or pull request.

## Public-safety boundary

The repository validator rejects vendor directories and non-first-party catalog ownership. Reviewers must also check scripts and documentation for unsafe command execution, credential exposure, hidden network behavior, private paths, and copied third-party material whose license or provenance is unclear.

Third-party skills belong in the private `agent-baseline` vendor catalog and must not be published here.
