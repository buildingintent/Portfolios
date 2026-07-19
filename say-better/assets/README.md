# Screenshot Guide

No screenshots are included in this showcase yet. Capture new, public-safe images from a dedicated demo account; do not copy production user screens.

## Recommended Captures

| Suggested filename | UI state | Suggested caption | Suggested alt text |
| ------------------ | -------- | ----------------- | ------------------ |
| `onboarding-keyboard-setup.png` | Companion app showing the keyboard enablement dialog or setup steps | Guided setup connects the companion app with the iOS keyboard. | Say Better keyboard setup instructions on iPhone |
| `home-dashboard.png` | Home tab with a fictional usage summary and sanitized recent activity | The companion app summarizes plan usage and recent rewrites. | Say Better home dashboard with usage and activity cards |
| `keyboard-compose.png` | Custom keyboard with tone/language controls and non-personal sample text | Tone and language controls stay available where the user is typing. | Say Better custom keyboard beneath generic sample text |
| `keyboard-review.png` | Generated result sheet before apply, using fictional content | Every rewrite is reviewable before it changes the host application. | Rewrite result with retry, copy, and apply controls |
| `activity-detail.png` | Before/after activity detail with synthetic text | Optional history makes past rewrites inspectable and removable. | Activity detail comparing fictional before and after text |
| `subscription.png` | Purchase or restore screen without transaction/account details | Subscription and restore controls live in the companion app. | Say Better subscription screen with purchase and restore actions |
| `privacy-support.png` | More tab or support screen with empty/synthetic fields | Account, history, legal, and support controls are grouped in the app. | Say Better privacy and support controls |

Use only the smallest set that tells the story. Four images—setup, dashboard, keyboard compose, and keyboard review—are enough for the main README; add the others only when they explain a distinct capability.

## Dimensions and Export

- Prefer a consistent portrait iPhone canvas. Existing release assets use **1290 × 2796 px** for the larger phone format and **1242 × 2688 px** for the alternate format.
- Export PNG for crisp text and interface details.
- Keep the original aspect ratio; do not stretch screenshots to fit a template.
- For GitHub presentation, retain the full-resolution source and display it at a readable width in Markdown or a simple table.
- If a composite image is created, keep individual screenshots large enough for labels to remain legible and provide alt text for the composite.

## Public-Safety Review

Before adding an image:

- Use a dedicated demo account with a fictional name and non-routable example email.
- Replace all message, rewrite, activity, and support content with neutral synthetic text.
- Remove account identifiers, purchase details, usage values copied from production, internal plan/cost information, and debug state.
- Hide notifications, status-bar personal details, keyboard suggestions, clipboard previews, device names, internal URLs, and development menus.
- Do not show real support attachments, identity-provider screens, password-reset links, tokens, or QR codes.
- Check that legal/support links are intended for public release.
- Strip EXIF and other image metadata, then inspect the final pixels at 100% zoom.
- Have a second person review every image before publication.

After review, add the files to this directory and replace the placeholder comments in the main README with real Markdown image links and the alt text above.
