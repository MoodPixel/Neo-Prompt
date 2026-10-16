# Security Policy

Neo Prompt is a local-first, open-source AI creative language studio maintained by **MoodPixel**.

We take security, privacy, and responsible vulnerability reporting seriously. This policy explains which versions receive security updates, how to report vulnerabilities, and the security responsibilities of users and contributors.

## Supported Versions

Neo Prompt is currently in its first public release.

| Version | Security Support |
| --- | --- |
| 1.0.x | ✅ Supported |
| Development / Unreleased Builds | ⚠️ Best effort |
| Earlier Versions | ❌ Not applicable |

Security fixes are generally targeted at the latest supported release. Users are encouraged to keep their installations updated.

## Reporting a Vulnerability

**Please do not publicly disclose security vulnerabilities through GitHub Issues, Discussions, or Pull Requests before they have been reviewed.**

To report a vulnerability privately, use:

**[Report a Security Vulnerability](https://github.com/MoodPixel/Neo-Prompt/security/advisories/new)**

This reporting method requires GitHub Private Vulnerability Reporting to be enabled for the repository.

If private reporting is not yet available, please wait until a private reporting channel is provided rather than posting sensitive exploit details publicly.

### What to Include

When submitting a vulnerability report, provide:

1. A clear description of the security issue.
2. The affected Neo Prompt version.
3. Steps to reproduce the vulnerability.
4. Its potential security or privacy impact.
5. Relevant sanitized logs, screenshots, or proof-of-concept details.
6. Suggested mitigations, if known.

**Do not include passwords, API tokens, private model data, personal information, or other sensitive content.**

## What Happens After Reporting?

The maintainers will review submitted security reports and assess their potential impact.

Depending on the findings, we may:

- Request additional technical details.
- Confirm and classify the vulnerability.
- Develop and test a security fix.
- Publish a patched version.
- Coordinate public disclosure after an appropriate fix or mitigation is available.

Response and resolution times depend on the issue's severity, complexity, and maintainer availability. No fixed resolution deadline is guaranteed.

## Security Scope

Potential security issues include:

- Unauthorized access to local application data.
- Exposure of saved prompts, captions, uploaded images, or credentials.
- Path traversal and unsafe file handling.
- Authentication, session, or request-validation vulnerabilities.
- Unsafe processing of imported workflows or untrusted content.
- Unexpected command execution or privilege escalation.
- Security vulnerabilities in Neo Prompt's backend communication or local API.

## Local-First Security Model

Neo Prompt is designed primarily for local, single-user operation.

The application:

- Runs its browser interface through a local server.
- Uses loopback addresses by default.
- Connects to independently configured KoboldCPP and ComfyUI installations.
- Stores application data locally.
- Does not require Neo Studio or another Neo application.
- Does not automatically install AI models or third-party custom nodes.

**Neo Prompt is not designed to be exposed directly to the public internet or used as a multi-user service.**

Avoid forwarding its local server port, exposing its API publicly, or disabling security protections.

## Third-Party Backends and Custom Nodes

Neo Prompt supports external software, including:

- KoboldCPP
- ComfyUI
- Compatible third-party ComfyUI custom nodes
- User-installed language and vision models

These components are independently maintained and may have their own security policies.

ComfyUI custom nodes and imported workflows can execute code or perform operations with the privileges of the ComfyUI process.

Install custom nodes only from sources you trust. Review downloaded workflows and dependencies before using them.

Security vulnerabilities originating exclusively in third-party projects should also be reported to their respective maintainers.

## Protecting User Data

Users should:

- Keep `neo_prompt_data/` private.
- Never commit runtime data, credentials, personal files, or generated private content.
- Avoid sharing unredacted application logs.
- Review imported workflows before execution.
- Use trusted AI models and custom nodes.
- Back up local data before installing updates.
- Keep Python dependencies and external backends updated.

## Responsible Disclosure

We encourage responsible, coordinated vulnerability disclosure.

Please allow maintainers an opportunity to investigate and address reported vulnerabilities before publishing technical exploit details.

Good-faith security research and constructive reporting are welcome.

## License

Neo Prompt is distributed under the **GNU General Public License v3.0**.

See [LICENSE](LICENSE) for details.

## Maintainer

**MoodPixel**

GitHub: https://github.com/MoodPixel

Repository: https://github.com/MoodPixel/Neo-Prompt

Thank you for helping keep Neo Prompt secure. 💜
