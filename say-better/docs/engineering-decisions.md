# Engineering Decisions

These decisions are inferred from the current implementation. Unless a repository document explicitly states intent, the rationale describes what the structure appears designed to achieve rather than attributing undocumented intent to an individual.

## Decision: Pair a React Native Companion App with a Native Keyboard Extension

### Context

Account, onboarding, subscription, settings, and support workflows benefit from a conventional application UI. Cross-application text rewriting must run inside Apple's keyboard-extension model and interact directly with iOS text-document APIs.

### Decision

Use React Native for the companion experience and Swift with UIKit/SwiftUI for the custom keyboard.

### Rationale

Based on the current implementation, this structure appears designed to keep product screens in a shared TypeScript/React environment while using native APIs where extension lifecycle, host text access, secure storage, and keyboard rendering require them.

### Trade-offs

- Two UI/runtime stacks require explicit bridges and duplicated platform-aware contracts.
- Native extension behavior can be tested close to iOS APIs, while app product work remains in React Native.
- The boundary increases release complexity but avoids forcing keyboard-specific work through a general mobile abstraction.

### Evidence in the Repository

- `apps/mobile/App.tsx`
- `apps/mobile/src/screens/`
- `apps/mobile/ios/SayBetterKeyboard/`
- `apps/mobile/ios/SayBetterKeyboardUI/`
- `apps/mobile/ios/SayBetterMobileSettingsModule.swift`

## Decision: Give the Keyboard a Separate Scoped Credential

### Context

The companion app and keyboard act for the same account but run in different processes. Sharing the full application session would grant the extension more capability than it needs.

### Decision

Issue a dedicated, expiring and revocable keyboard credential after app authentication and disclosure acceptance. Store its secret in shared Keychain access, store only a server-side hash, and authorize keyboard requests through a narrower endpoint set.

### Rationale

Based on the current implementation, this structure appears designed to apply least privilege across the app/extension boundary while still allowing the app to rotate or revoke keyboard access.

### Trade-offs

- Credential provisioning and refresh add setup states and recovery paths.
- Server authorization has to distinguish app and keyboard modes.
- A compromised keyboard credential has a narrower use, and revocation does not require exposing the full app session to the extension.

### Evidence in the Repository

- `apps/api/src/auth/keyboard-tokens.ts`
- `apps/api/src/auth/session.ts`
- `apps/api/src/routes/auth-routes.ts`
- `apps/mobile/src/auth/keyboardTokenStore.ts`
- `apps/mobile/ios/Shared/SayBetterNativeConfig.swift`

## Decision: Route AI Generation Through the API

### Context

Rewrite generation needs provider credentials, shared prompt rules, request validation, disclosure checks, quotas, privacy-safe logging, and consistent error translation.

### Decision

Keep the LLM API integration server-side behind a provider interface. The iOS clients exchange validated product contracts with the API rather than calling the model provider directly.

### Rationale

Based on the current implementation, this structure appears designed to keep provider credentials off devices and centralize product policy, prompt construction, timeout handling, response validation, and provider substitution boundaries.

### Trade-offs

- Every rewrite requires network access and adds an API hop.
- The API becomes responsible for remote-provider latency and availability.
- Centralization enables one privacy/logging policy and consistent behavior across the companion app and keyboard.

### Evidence in the Repository

- `packages/ai-core/src/provider.ts`
- `packages/ai-core/src/prompt.ts`
- `apps/api/src/routes/rewrite-routes.ts`
- `packages/contracts/src/index.ts`
- `packages/privacy/src/index.ts`

## Decision: Reserve Usage Before Calling the AI Provider

### Context

Plan limits must remain consistent when rewrite requests overlap, are retried, time out, or fail after remote work begins.

### Decision

Use a request key and content fingerprint as an idempotency gate, reserve the expected word charge in a database transaction, and then commit or release it when generation reaches a terminal state. A worker recovers expired reservations.

### Rationale

Based on the current implementation, this structure appears designed to prevent concurrent oversubscription without permanently charging failed or abandoned work.

### Trade-offs

- The request lifecycle and SQL transaction logic are more involved than incrementing a counter after success.
- Recovery depends on the worker running regularly.
- Duplicate and retry behavior becomes explicit and testable, including completed and in-flight outcomes.

### Evidence in the Repository

- `apps/api/src/rewrite/usage-reservation.ts`
- `apps/api/src/rewrite/fingerprint.ts`
- `apps/api/src/routes/rewrite-routes.ts`
- `apps/api/src/workers/reservation-sweep.ts`
- `apps/api/prisma/schema.prisma`

## Decision: Review and Verify Context Before Replacing Host Text

### Context

iOS keyboard extensions receive incomplete, host-controlled text context. The document may change while a remote rewrite is in progress, and replacement behavior varies between host applications.

### Decision

Capture typed-session or focused-input context, show generated text in a review state, compare the current document with the captured context before applying, and use copy as a safe fallback when replacement cannot be established.

### Rationale

Based on the current implementation, this structure appears designed to avoid destructive edits while preserving a usable outcome in restrictive host applications.

### Trade-offs

- Users take an extra review/apply step.
- Some host applications cannot support automatic replacement even after successful generation.
- The failure mode protects user text and still offers copy rather than guessing at deletion ranges.

### Evidence in the Repository

- `apps/mobile/ios/SayBetterKeyboard/TypedSessionBuffer.swift`
- `apps/mobile/ios/SayBetterKeyboard/TypedSessionReplacement.swift`
- `apps/mobile/ios/SayBetterKeyboard/CaptureAdapter.swift`
- `apps/mobile/ios/SayBetterKeyboard/KeyboardRewriteController.swift`
- `apps/mobile/ios/SayBetterKeyboardTests/`

## Decision: Treat the Server as the Authority for Apple Entitlements

### Context

Subscription access can change through purchases, restores, renewals, expiration, grace periods, refunds, and revocations. Client-reported state is not enough to maintain an account entitlement.

### Decision

Submit signed purchase evidence from the app, verify it with Apple's server library, bind it to the authenticated account, persist normalized entitlement state, and consume signed App Store lifecycle notifications.

### Rationale

Based on the current implementation, this structure appears designed to reconcile access from both user-initiated and server-initiated events instead of trusting a local flag.

### Trade-offs

- Billing requires Apple credentials, notification setup, environment handling, and more failure states.
- Entitlement availability depends on Apple verification and API reachability.
- Purchase restore and lifecycle updates converge on one server-owned plan decision.

### Evidence in the Repository

- `apps/mobile/src/iap/client.ts`
- `apps/mobile/src/api/billing.ts`
- `apps/api/src/iap/apple-client.ts`
- `apps/api/src/routes/billing-routes.ts`
- `apps/api/prisma/schema.prisma`
