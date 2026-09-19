# Raje3 mobile

Flutter app for Raje3 (Saudi beauty/car-wash SaaS). This is a **thin shell**:
every screen calls our own server directly. No offline mode, no local
database, no sync queue — the only thing persisted on-device is the auth
token (secure storage) and a few UI preferences (locale, theme, onboarding
flag — shared_preferences).

## What this pass is

An **infrastructure-only** skeleton, built by porting the reusable
engineering architecture from a mature, unrelated Flutter app the owner
built for a different product (personal-care-company/hair-analysis-platform,
55+ screens, 2,295 tests) — not that product's screens, models, brand, or
API. Raje3's own UI/screens are a later pass.

## What was ported, and from where

Everything below was **copied from the reference project first**, then
adapted with targeted edits (package rename, generalizing a domain-specific
concept, swapping in Raje3's real tokens) — not rewritten from scratch. Each
file's own doc comment says exactly what changed and why.

| File | Ported from | Adaptation |
|---|---|---|
| `lib/core/network/api_client.dart` | `lib/core/network/api_client.dart` | Unified execute endpoint → plain REST verbs (see "Unified execute" below) |
| `lib/core/network/api_interceptors.dart` | same | `ContextInterceptor` now injects `X-Tenant-Id` header instead of `business_id` in an execute body |
| `lib/core/network/api_response.dart` | same | Untouched (endpoint-agnostic) |
| `lib/core/network/api_exceptions.dart` | same | Untouched |
| `lib/core/storage/secure_storage.dart` | same | Untouched |
| `lib/core/storage/local_storage.dart` | same | Dropped their streak-card/donation-hint keys (gamification feature, not infra) |
| `lib/core/storage/cache_manager.dart` | same | Untouched |
| `lib/core/providers/auth_provider.dart` | same | Dropped `PushNotificationService` wiring (push isn't part of this pass, not decided yet — add back the same way if/when it lands) |
| `lib/core/providers/tenant_provider.dart` | `context_provider.dart` | Their "individual vs. business" context generalized to a plain tenant list (`TenantModel`) |
| `lib/core/providers/theme_provider.dart` | same | Untouched |
| `lib/core/providers/locale_provider.dart` | same | Untouched |
| `lib/core/providers/app_state_provider.dart` | same | Untouched |
| `lib/core/router/app_router.dart` | same | Kept the auth-redirect logic and `StatefulShellRoute.indexedStack` mechanism verbatim; their 50+ screen imports/routes (hair-scan flows, CRM, device pairing, streak gamification…) are their product and are NOT ported — trimmed to one placeholder tab until Raje3's own screens land |
| `lib/core/router/route_names.dart` | same | Trimmed to the naming convention + the two routes this skeleton actually uses |
| `lib/core/services/auth_service.dart` | same | Execute calls → REST paths (placeholder `/auth/...` paths — real ones aren't decided) |
| `lib/core/services/tenant_service.dart` | `context_service.dart` | Same generalization as `tenant_provider.dart` |
| `lib/core/services/app_config_service.dart` | same | Execute call → `GET /config/mobile`; scoped by tenant instead of business |
| `lib/core/utils/formatters.dart` | same | Untouched |
| `lib/core/utils/validators.dart` | same | Untouched |
| `lib/core/utils/snackbar_helper.dart` | same | Untouched |
| `lib/core/utils/url_helper.dart` | same | Untouched |
| `lib/core/utils/device_info.dart` | same | Untouched |
| `lib/core/config/app_config.dart` | same | Kept the "phase registry" doc-comment pattern; dropped their Phase 3 (BLE/WiFi device pairing), Phase 4 (on-device TFLite/YOLO AI), Phase 5 (scan sessions) — all their product's own domain |
| `lib/core/constants/app_constants.dart` | same | Dropped scan/cart/device-pairing keys; kept storage keys, pagination, currency/VAT region config |
| `lib/core/constants/api_constants.dart` | same | Replaced the four execute-pattern endpoint URLs with one `apiBasePath` |
| `lib/theme/app_theme.dart` | `lib/theme/flutterflow_theme.dart` | **Pattern only** (AppColors/AppSpacing/AppTextStyles token classes) — none of their Royal-Amethyst/Metallic-Gold literal values were kept. `AppColors` itself now lives in the generated `app_colors.g.dart` (see below) — `app_theme.dart` imports/re-exports it. |
| `lib/theme/app_colors.g.dart` | — (generated) | **Not hand-written.** Produced by `scripts/gen_mobile_theme.py` directly from `ui/packages/ui/src/theme/theme.config.ts`'s `light` palette and `config/product.json`'s `brand.accent` (`#7C3AED`/`#A78BFA`) — same `mix()` derivation theme.config.ts itself uses for hover/soft/on-soft tints. Re-run the script after either source changes; `ci/check_mobile_theme_is_generated.py` fails the build if the checked-in file drifts from the generator's current output. This is the fix for the exact drift class `ci/check_a_hardcoded_color_does_not_shadow_a_token.py` already polices on the web side. |
| `l10n.yaml` | same | Same ARB tooling config, `preferred-supported-locales` set to Raje3's real 6 (`ar en ur ha fil bn`, from `apps/console/src/operator-i18n.tsx`) |
| `analysis_options.yaml` | same | Untouched |
| `test/security/security_critical_test.dart` | same | Kept the groups testing reusable infra (ApiResponse parsing, ApiException handling, interceptor docs); dropped groups asserting on their domain models (Order/Subscription/Scan/Business) and the execute-endpoint module/action spread risk (doesn't apply — this app isn't on that endpoint) |

**Written fresh, no reference** (thin, product-shape files needed to make
the above compile, not ported from anywhere): `pubspec.yaml`, `Makefile`
(reference had none), `lib/main.dart`, `lib/models/user_model.dart`,
`lib/models/tenant_model.dart`, `lib/models/app_config_model.dart`,
`lib/features/auth/login_screen.dart`, `lib/features/home/home_screen.dart`
(both explicit placeholders — real screens are a later pass), the six
`lib/l10n/app_*.arb` files (generic button-label strings only, in Raje3's
real 6 locales, `ar` as the template/source language per this product's
`locale.default`).

## Explicitly NOT ported

- **Any of their product's own UI/screens or business logic** — hair
  analysis, CRM, device pairing/BLE, on-device TFLite/YOLO AI, streak
  gamification, credits/store/subscriptions. Raje3's own screens are a
  separate, later pass.
- **Their brand** — colors, logo, fonts as literal values, translated copy.
- **Offline/sync machinery** — none was found under `lib/core/` (this
  reference app is also a live-server app with local caching only, not an
  offline-first app), so there was nothing to explicitly exclude here beyond
  the in-memory `CacheManager` (kept — it's a short-TTL cache of live-server
  responses, not a local database or offline queue).
- **Push notifications** (`PushNotificationService`, FCM token lifecycle) —
  not excluded on principle, just not decided/built yet for Raje3.

## TODO: "unified execute endpoint" — explicitly deferred, do not implement yet

The reference project routes every API call through one endpoint:
`POST /api/v1/mobile/execute { module, action, data }`. This app does
**not** use that pattern — `ApiClient` here is plain REST
(`get/post/put/patch/delete/upload`, one path per call). Adopting the
unified-execute pattern would require coordinated changes across our whole
services fleet — a decision the owner hasn't made. If that decision is made
later, the place to start is `lib/core/network/api_client.dart` (add an
`execute()` method alongside the REST verbs, or replace them) and
`lib/core/constants/api_constants.dart` (`apiBasePath` → an execute URL).
Until then, every call site should use a real REST path.

## Running

```
cd apps/mobile
flutter pub get
flutter analyze
flutter gen-l10n   # regenerates lib/l10n/app_localizations*.dart from the .arb files
flutter test
```

No `android/`, `ios/`, or other platform scaffolding is included yet — the
environment this app was built in has no Flutter SDK installed, so
`flutter create .` could not be run to generate it. Run that once locally
(it only adds `android/`, `ios/`, etc. — it will not touch `lib/`) before
building for a device or emulator.
