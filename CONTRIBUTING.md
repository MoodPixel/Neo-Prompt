# Contributing to Neo Prompt

Thank you for your interest in contributing to **Neo Prompt**! 🚀

Neo Prompt is an open-source, local-first creative language studio developed by **MoodPixel**. We welcome bug reports, feature suggestions, documentation improvements, and code contributions.

## Ways to Contribute

You can help improve Neo Prompt by:

- 🐛 **Reporting bugs:** Help identify issues with the application, interface, or backend integrations.
- 💡 **Suggesting features:** Share ideas that improve prompting, captioning, datasets, or creative workflows.
- 📝 **Improving documentation:** Make setup instructions, tutorials, and troubleshooting guides clearer.
- 🛠️ **Contributing code:** Fix bugs, improve existing functionality, or propose new features.
- 🧪 **Testing compatibility:** Share results from different hardware, operating systems, local models, and supported backends.

## Reporting Bugs

Before submitting an issue, please check whether it has already been reported.

When opening a bug report, include:

1. A clear description of the problem.
2. Steps to reproduce it.
3. What you expected to happen and what actually happened.
4. Your operating system and Neo Prompt version.
5. The backend used (KoboldCPP or ComfyUI), including relevant model and custom-node information.
6. Screenshots or sanitized error logs, if available.

**Never include passwords, API tokens, private files, personal data, or sensitive information in public issues.**

## Suggesting Features

Open a GitHub Issue describing your idea.

Explain what problem it solves, how users would benefit, and how it fits Neo Prompt's purpose.

For substantial changes, please discuss the proposal before investing time in implementation.

## Submitting Code Contributions

1. Fork the Neo Prompt repository.
2. Create a descriptive feature or bug-fix branch.
3. Make focused changes while preserving existing functionality.
4. Test your changes locally.
5. Update relevant user documentation when functionality changes.
6. Submit a Pull Request explaining your changes and testing results.

Keep Pull Requests focused. Large architectural changes should be discussed with the maintainers first.

## Development Principles

Neo Prompt follows several core principles:

- **Local-first:** User data and inference workflows should remain locally controlled.
- **Standalone:** Neo Prompt must operate without requiring Neo Studio, Neo Spaces, or another Neo application.
- **Backend independence:** KoboldCPP and ComfyUI remain independently configured external runtimes.
- **User control:** Never silently install models, custom nodes, or external dependencies.
- **Privacy and security:** Protect local data, credentials, uploaded images, and generated content.
- **Honest functionality:** Do not present simulated or unavailable capabilities as working features.
- **Consistent design:** Preserve the Neo family's dark navy, violet, and cyan visual identity and accessible interface patterns.

## Testing

Before submitting changes, verify the relevant functionality.

For interface changes, check layout, navigation, keyboard access, and responsive behavior.

For backend changes, test against a compatible backend where possible. Clearly state when testing was limited to mocks or static checks.

Do not commit runtime data, Python virtual environments, downloaded model weights, private development records, credentials, or generated user content.

## Documentation

Public guides are located in the [`guides/`](guides/) directory.

Documentation should explain supported functionality clearly, including prerequisites, limitations, and troubleshooting steps.

Avoid internal development milestones and phase identifiers in public-facing instructions.

## Code of Conduct

All contributors are expected to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

Respectful and constructive collaboration is required.

## License

Neo Prompt is distributed under the **GNU General Public License v3.0**.

By contributing, you agree that your submitted contributions may be distributed under the project's GPLv3 license, and you confirm that you have the rights necessary to submit them.

See [LICENSE](LICENSE) for the complete license.

## Project Maintainer

**MoodPixel**

GitHub: https://github.com/MoodPixel

Project: https://github.com/MoodPixel/Neo-Prompt

Thank you for helping make Neo Prompt better for creators and the open-source community! 💜
