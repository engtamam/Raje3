#!/usr/bin/env python3
"""A mobile screen/widget migrated to lib/l10n must carry no raw Arabic string outside
S.of(context) — the mobile mirror of ci/check_operator_screen_localized.py's rule on the
console side, same SCREENS-allowlist shape and same reason for it.

WHY THIS EXISTS. The mobile app supports six locales through lib/l10n/*.arb — the exact same
idea apps/console/src/operator-i18n.tsx already applies. A widget that hardcodes an Arabic
literal instead of reading it through `S.of(context)!.someKey` renders Arabic to every
non-Arabic locale regardless of the user's own language setting — the drift this repo's console
gate already polices, on a door this session found unwired (main.dart never carried
S.localizationsDelegates/supportedLocales until the same pass that added this gate).

WHY STILL AN ALLOWLIST, not every *.dart file: as of 2026-09-28, SCREENS below was expanded to
every file in lib/ that was ALREADY clean (129 of them) — this gate now blocks a real build over
NEW raw-Arabic drift in any of them, per the owner's own explicit call. It still excludes the
~30 files not yet migrated (campaigns_i18n.dart, new_booking_sheet.dart, referrals_screen.dart,
app_store_model.dart, formatters.dart, api_exceptions.dart, and similar pre-l10n code) — migrating
those is its own tracked, ongoing pass, not a thing one CI gate can retroactively demand of code
nobody has touched yet. Exactly check_operator_screen_localized.py's own reasoning: "an unlisted
screen is not yet expected to be clean, so --all never flags work nobody has begun." Move a file
from dirty to SCREENS the moment ITS migration lands — a clean file left off the list is a gap
this gate can no longer see.

WHY A REGEX OVER THE ARABIC UNICODE RANGE, not a list of known strings: every hardcoded Arabic
literal in a screen's SOURCE is caught this way regardless of which runtime branch renders it,
the same reasoning check_operator_screen_localized.py's own header gives.

Usage:
    python ci/check_mobile_screen_localized.py apps/mobile/lib/features/home/home_screen.dart
    python ci/check_mobile_screen_localized.py --all   # every file in SCREENS below

Exits 1 and prints every offending line if any raw Arabic text remains; exits 0 (silent) if clean.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Files already migrated to lib/l10n — add a path here once its migration starts.
SCREENS = [
    "apps/mobile/lib/core/actions/action_executor.dart",
    "apps/mobile/lib/core/actions/action_model.dart",
    "apps/mobile/lib/core/actions/action_registry.dart",
    "apps/mobile/lib/core/actions/action_tools.dart",
    "apps/mobile/lib/core/ai/adapters/gemma_ai_model.dart",
    "apps/mobile/lib/core/ai/adapters/null_ai_model.dart",
    "apps/mobile/lib/core/ai/ai_config.dart",
    "apps/mobile/lib/core/ai/ai_container.dart",
    "apps/mobile/lib/core/ai/ai_model.dart",
    "apps/mobile/lib/core/ai/assistant_turn.dart",
    "apps/mobile/lib/core/config/app_config.dart",
    "apps/mobile/lib/core/constants/api_constants.dart",
    "apps/mobile/lib/core/knowledge/kb_model.dart",
    "apps/mobile/lib/core/network/api_interceptors.dart",
    "apps/mobile/lib/core/network/api_response.dart",
    "apps/mobile/lib/core/providers/ai_entitlement_provider.dart",
    "apps/mobile/lib/core/providers/app_state_provider.dart",
    "apps/mobile/lib/core/providers/branch_provider.dart",
    "apps/mobile/lib/core/providers/locale_provider.dart",
    "apps/mobile/lib/core/providers/nav_provider.dart",
    "apps/mobile/lib/core/providers/tenant_provider.dart",
    "apps/mobile/lib/core/providers/theme_provider.dart",
    "apps/mobile/lib/core/router/app_router.dart",
    "apps/mobile/lib/core/router/route_names.dart",
    "apps/mobile/lib/core/services/app_config_service.dart",
    "apps/mobile/lib/core/services/app_features_service.dart",
    "apps/mobile/lib/core/services/bookings_service.dart",
    "apps/mobile/lib/core/services/catalog_service.dart",
    "apps/mobile/lib/core/services/customers_service.dart",
    "apps/mobile/lib/core/services/messages_service.dart",
    "apps/mobile/lib/core/services/mobile_requests_service.dart",
    "apps/mobile/lib/core/services/mutual_benefit_service.dart",
    "apps/mobile/lib/core/services/notification_service.dart",
    "apps/mobile/lib/core/services/partner_loyalty_service.dart",
    "apps/mobile/lib/core/services/points_service.dart",
    "apps/mobile/lib/core/services/ratings_service.dart",
    "apps/mobile/lib/core/services/referrals_service.dart",
    "apps/mobile/lib/core/services/services_catalogue_service.dart",
    "apps/mobile/lib/core/services/shop_dashboard_service.dart",
    "apps/mobile/lib/core/services/tenant_service.dart",
    "apps/mobile/lib/core/services/whatsapp_assistant_service.dart",
    "apps/mobile/lib/core/storage/cache_manager.dart",
    "apps/mobile/lib/core/storage/local_storage.dart",
    "apps/mobile/lib/core/storage/secure_storage.dart",
    "apps/mobile/lib/core/tts/adapters/null_tts_model.dart",
    "apps/mobile/lib/core/tts/adapters/platform_tts_model.dart",
    "apps/mobile/lib/core/tts/tts_config.dart",
    "apps/mobile/lib/core/tts/tts_container.dart",
    "apps/mobile/lib/core/tts/tts_model.dart",
    "apps/mobile/lib/core/utils/device_info.dart",
    "apps/mobile/lib/core/utils/maps_link.dart",
    "apps/mobile/lib/core/utils/snackbar_helper.dart",
    "apps/mobile/lib/core/utils/url_helper.dart",
    "apps/mobile/lib/core/voice/adapters/null_speech_input_model.dart",
    "apps/mobile/lib/core/voice/adapters/platform_speech_input_model.dart",
    "apps/mobile/lib/core/voice/speech_input_config.dart",
    "apps/mobile/lib/core/voice/speech_input_container.dart",
    "apps/mobile/lib/core/voice/speech_input_model.dart",
    "apps/mobile/lib/core/wakeword/adapters/null_wake_word_model.dart",
    "apps/mobile/lib/core/wakeword/adapters/platform_wake_word_model.dart",
    "apps/mobile/lib/core/wakeword/micro_frontend.dart",
    "apps/mobile/lib/core/wakeword/wake_word_config.dart",
    "apps/mobile/lib/core/wakeword/wake_word_container.dart",
    "apps/mobile/lib/core/wakeword/wake_word_model.dart",
    "apps/mobile/lib/features/account/account_screen.dart",
    "apps/mobile/lib/features/account/billing_screen.dart",
    "apps/mobile/lib/features/account/branch_detail_screen.dart",
    "apps/mobile/lib/features/account/branches_screen.dart",
    "apps/mobile/lib/features/account/shop_identity_screen.dart",
    "apps/mobile/lib/features/apps/payment_webview_screen.dart",
    "apps/mobile/lib/features/auth/login_screen.dart",
    "apps/mobile/lib/features/auth/signup_screen.dart",
    "apps/mobile/lib/features/auth/verify_phone_screen.dart",
    "apps/mobile/lib/features/campaigns/campaigns_style.dart",
    "apps/mobile/lib/features/campaigns/message_preview_sheet.dart",
    "apps/mobile/lib/features/campaigns/messages_screen.dart",
    "apps/mobile/lib/features/campaigns/text_editor_sheet.dart",
    "apps/mobile/lib/features/campaigns/wa_flow_screens.dart",
    "apps/mobile/lib/features/campaigns/whatsapp_bubble.dart",
    "apps/mobile/lib/features/customers/customer_detail_screen.dart",
    "apps/mobile/lib/features/customers/customers_screen.dart",
    "apps/mobile/lib/features/home/app_tone.dart",
    "apps/mobile/lib/features/home/home_screen.dart",
    "apps/mobile/lib/features/mobile_requests/mobile_requests_screen.dart",
    "apps/mobile/lib/features/mutual_benefit/mutual_benefit_screen.dart",
    "apps/mobile/lib/features/points/points_screen.dart",
    "apps/mobile/lib/features/rating/rating_screen.dart",
    "apps/mobile/lib/features/rating/staff_quadrant.dart",
    "apps/mobile/lib/features/services/bulk_import_sheet.dart",
    "apps/mobile/lib/features/services/packages_tab.dart",
    "apps/mobile/lib/features/services/procedures_tab.dart",
    "apps/mobile/lib/features/services/services_screen.dart",
    "apps/mobile/lib/features/shell/main_shell.dart",
    "apps/mobile/lib/features/shop/shop_screen.dart",
    "apps/mobile/lib/features/visit/visit_screen.dart",
    "apps/mobile/lib/features/whatsapp_assistant/whatsapp_assistant_screen.dart",
    "apps/mobile/lib/main.dart",
    "apps/mobile/lib/models/booking_model.dart",
    "apps/mobile/lib/models/catalog_model.dart",
    "apps/mobile/lib/models/coworking_model.dart",
    "apps/mobile/lib/models/customer_model.dart",
    "apps/mobile/lib/models/mobile_request_model.dart",
    "apps/mobile/lib/models/mutual_benefit_model.dart",
    "apps/mobile/lib/models/notification_item.dart",
    "apps/mobile/lib/models/partner_loyalty_model.dart",
    "apps/mobile/lib/models/points_model.dart",
    "apps/mobile/lib/models/rating_model.dart",
    "apps/mobile/lib/models/referral_model.dart",
    "apps/mobile/lib/models/service_model.dart",
    "apps/mobile/lib/models/shop_dashboard_model.dart",
    "apps/mobile/lib/models/tenant_model.dart",
    "apps/mobile/lib/models/user_model.dart",
    "apps/mobile/lib/theme/app_colors.g.dart",
    "apps/mobile/lib/theme/app_theme.dart",
    "apps/mobile/lib/widgets/app_back_button.dart",
    "apps/mobile/lib/widgets/app_widgets.dart",
    "apps/mobile/lib/widgets/assistant_chat_sheet.dart",
    "apps/mobile/lib/widgets/assistant_reply_mode_sheet.dart",
    "apps/mobile/lib/widgets/branch_switcher.dart",
    "apps/mobile/lib/widgets/brand_loading_indicator.dart",
    "apps/mobile/lib/widgets/capability_gate.dart",
    "apps/mobile/lib/widgets/date_time_picker_sheet.dart",
    "apps/mobile/lib/widgets/effects/confetti_burst.dart",
    "apps/mobile/lib/widgets/effects/game_effects.dart",
    "apps/mobile/lib/widgets/effects/points_fly_text.dart",
    "apps/mobile/lib/widgets/floating_mic_button.dart",
    "apps/mobile/lib/widgets/kb_anchor.dart",
    "apps/mobile/lib/widgets/notification_bell.dart",
    "apps/mobile/lib/widgets/rj_sheen.dart",
]

ARABIC = re.compile(r"[؀-ۿ]")


def _is_exempt(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
        return True
    # A CALL ALREADY ROUTED THROUGH THE DICTIONARY LOOKUP is not a bypass of it — same reasoning
    # check_operator_screen_localized.py gives for t('...') call arguments.
    if "S.of(context)" in stripped:
        return True
    # THE BRAND'S OWN NAME IS NOT UI COPY TO TRANSLATE — same category as console's NAME_AR
    # exemption. AppConfig.appInfoNameAr is the product's Arabic wordmark itself, and stays Arabic
    # in every locale the same way a brand name does in any product translated around it.
    if "appInfoNameAr" in stripped:
        return True
    return False


def scan(path: Path) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    in_block_comment = False
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        if stripped.startswith("/*") and "*/" not in stripped:
            in_block_comment = True
            continue
        if ARABIC.search(line) and not _is_exempt(line):
            hits.append((i, line.strip()))
    return hits


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    targets = [ROOT / s for s in SCREENS] if argv[0] == "--all" else [ROOT / argv[0]]
    failed = False
    for path in targets:
        hits = scan(path)
        if hits:
            failed = True
            print(f"✗ {path.relative_to(ROOT)}: {len(hits)} raw Arabic string(s) outside S.of(context)")
            for lineno, text in hits:
                print(f"    {lineno}: {text}")
        else:
            print(f"✓ {path.relative_to(ROOT)}: clean")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
