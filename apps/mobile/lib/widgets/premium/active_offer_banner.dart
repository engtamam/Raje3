import 'package:flutter/material.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// «شريط العرض النشط» — the moment the operator sees a real offer this customer already holds, the
/// best of campaign/referral/mutual-benefit, already compared by real value server-side (GET
/// /api/v1/field/visits/offer/preview — a PREVIEW, never a spend; see `EntitlementGateway.choose`
/// in operations). NOTHING APPLIES AN OFFER AUTOMATICALLY (mirrors
/// `apps/console/src/screens/Visit.tsx`'s own checkbox, never copied visually): a customer who came
/// in for something else and was silently charged an offer he was saving is a customer we took
/// something from — so [applying]/[onApplyingChanged] is a deliberate checkbox the operator ticks,
/// and the actual `POST /field/visits/{id}/offer` call only fires AFTER the visit itself is safely
/// recorded (see visit_screen.dart's own `_save`), never raced against it. Deliberately the ONE
/// gold-gradient surface in this screen — the console's own VIP-card identity
/// (`AppDetailsModal.tsx`'s own `#d4af37`/`#f0d98c` pair) reused here so "this customer has
/// something special" reads instantly and consistently across both platforms.
///
/// `text` IS THE WHOLE SENTENCE NOW (2026-10-05) — each source composes its own complete Arabic
/// sentence, already stating its own amount, server-side (`core/entitlements.py`); there is no
/// separate `value` field left to append.
class ActiveOfferBanner extends StatelessWidget {
  final String text;

  const ActiveOfferBanner({super.key, required this.text});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.md),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF9C6B0F), Color(0xFFD4AF37), Color(0xFFF0D98C)],
          begin: Alignment.centerLeft,
          end: Alignment.centerRight,
        ),
        borderRadius: AppRadius.cardRadius,
        boxShadow: const [
          BoxShadow(color: Color(0x4DD4AF37), blurRadius: 16, offset: Offset(0, 6)),
        ],
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.22),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.card_giftcard_rounded, color: Colors.white, size: 22),
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'عنده عرض ساري',
                  style: AppTextStyles.caption.copyWith(
                    color: Colors.white.withValues(alpha: 0.85),
                    fontWeight: FontWeight.w600,
                    letterSpacing: 0.2,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  text,
                  style: AppTextStyles.bodyMedium.copyWith(
                    color: Colors.white, fontWeight: FontWeight.w700,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// The checkbox row itself, kept a SEPARATE tap target from the banner above (the owner's own
/// discipline: a whole gold card is loud on purpose, but the ONE thing that spends the offer must
/// stay a small, deliberate control inside it — the same "not pressed for him" reasoning
/// `ActiveOfferBanner`'s own doc comment states).
class ActiveOfferApplyToggle extends StatelessWidget {
  final bool applying;
  final ValueChanged<bool> onChanged;
  final String label;

  const ActiveOfferApplyToggle({
    super.key,
    required this.applying,
    required this.onChanged,
    required this.label,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.sm),
      child: InkWell(
        borderRadius: AppRadius.standardRadius,
        onTap: () => onChanged(!applying),
        child: Row(
          children: [
            Checkbox(
              value: applying,
              onChanged: (v) => onChanged(v ?? false),
              fillColor: WidgetStateProperty.resolveWith(
                  (states) => states.contains(WidgetState.selected) ? Colors.white : null),
              checkColor: const Color(0xFF9C6B0F),
              side: const BorderSide(color: Colors.white, width: 1.5),
            ),
            Expanded(
              child: Text(
                label,
                style: AppTextStyles.bodySmall.copyWith(color: Colors.white, fontWeight: FontWeight.w600),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
