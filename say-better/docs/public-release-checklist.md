# Public Release Checklist

Use this checklist on the copied `portfolio-showcase` directory immediately before making a public repository. It is not a review of the private production repository as a whole.

## Content and Security

- [ ] Run an automated secret scan across every tracked file and the full Git history.
- [ ] Confirm there are no API keys, tokens, passwords, certificates, private keys, cookies, or environment values.
- [ ] Confirm environment files, build artifacts, provisioning profiles, signing material, and production configuration were not copied.
- [ ] Search for private URLs, internal hostnames, IP addresses, database connection strings, webhook endpoints, and non-public email addresses.
- [ ] Remove bundle identifiers, team/account/project/database IDs, organization identifiers, transaction references, and other internal identifiers.
- [ ] Check analytics or service configuration for keys even when a vendor describes them as client-safe.
- [ ] Confirm database descriptions remain conceptual and do not reveal sensitive fields, indexes, access rules, or operational data.
- [ ] Confirm no proprietary source, production payload, fixture, migration SQL, prompt text, or large code snippet was copied.
- [ ] Confirm repository evidence paths reveal only generic structure and no confidential naming.
- [ ] Remove unreleased roadmap details, review correspondence, confidential pricing, internal cost estimates, and unsupported launch claims.

## Personal Data and Screenshots

- [ ] Confirm names, email addresses, avatars, support messages, rewrite text, and account details are fictional and non-identifying.
- [ ] Confirm screenshots contain no notifications, status-bar location clues, test accounts, device names, purchase identifiers, debug overlays, or internal URLs.
- [ ] Inspect attachment previews, keyboard suggestions, clipboard content, and recent activity for personal text.
- [ ] Strip image metadata and verify every image at full resolution after redaction.
- [ ] Confirm image filenames, captions, and alt text do not contain private information.

## Accuracy and Scope

- [ ] Re-check every technology and feature claim against the current private repository revision.
- [ ] Confirm implemented, active-development, planned, and not-verifiable statements remain clearly separated.
- [ ] Confirm no user counts, performance results, revenue, production scale, coverage percentage, certification, or launch date is implied without public evidence.
- [ ] Confirm third-party product names and trademarks are used descriptively.
- [ ] Verify the repository still contains documentation only.

## Repository Quality

- [ ] Select and add a license appropriate for public documentation and any image assets.
- [ ] Add a concise repository description that says this is a public product/architecture showcase for a private-source project.
- [ ] Add a reviewed social preview image with no private content.
- [ ] Choose relevant GitHub topics, for example `ios`, `react-native`, `swift`, `fastify`, `postgresql`, `prisma`, `ai`, and `portfolio`.
- [ ] Render every Mermaid diagram on GitHub and fix syntax or layout problems.
- [ ] Run a Markdown link checker and open every relative link manually.
- [ ] Check heading hierarchy, table rendering, spelling, image alt text, and mobile readability.
- [ ] Confirm the README screenshot comments match files that actually exist before uncommenting them.
- [ ] Review the final Git diff and commit history for accidentally copied or deleted private material.

## Recommended GitHub Repository Settings

- [ ] Set repository visibility to **Public** only after all checks above pass.
- [ ] Disable Issues unless public feedback or bug reports are desired.
- [ ] Enable Discussions only if there is a plan to moderate and respond.
- [ ] Disable the Wiki unless it will be maintained separately from these docs.
- [ ] Do not configure production deployment secrets, environments, webhooks, Actions variables, or private package credentials.
- [ ] Use a clear description such as: “Public product and architecture showcase for Say Better; production source is private.”
- [ ] Add only relevant, accurate GitHub topics.
- [ ] Protect the default branch if more than one contributor will publish updates.
