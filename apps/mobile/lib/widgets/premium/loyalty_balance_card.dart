import 'package:flutter/material.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// One affordable reward — «غسلة مجانية», its cost in points. [FieldReward] on the console side
/// (apps/console/src/api.ts) — this file keeps the same loose `Map<String, dynamic>` shape every
/// other lookup in visit_screen.dart already reads, no new model type for a screen that reads
/// everything else this way.

/// «بطاقة العضوية» — the customer's points balance, shown the moment he is identified (phone or
/// plate), never after saving. Grounded in real 2026 loyalty-UX research: a glass-on-gradient
/// membership card, the balance as the one unmissable number, a slim progress bar toward the next
/// real reward (never a bare percentage — "كم يبقى" is the sentence that makes a customer act),
/// and up to two affordable rewards named directly rather than a flat list greying out the rest
/// (mindinventory.com's own "meaningful progress, not volume" — reused here, first stated for
/// GameEffects's own doc comment).
///
/// GLASS FOR CHROME, SOLID FOR NUMBERS — the same split real 2026 glassmorphism guidance draws
/// (a higher-opacity layer under anything carrying digits, frosted glass only for decoration):
/// the points figure itself sits on a solid dark chip, never blurred text a workshop's own
/// fluorescent glare would wash out.
class LoyaltyBalanceCard extends StatelessWidget {
  final int points;
  final int toNextReward;
  final List<Map<String, dynamic>> rewards;

  const LoyaltyBalanceCard({
    super.key,
    required this.points,
    required this.toNextReward,
    this.rewards = const [],
  });

  @override
  Widget build(BuildContext context) {
    final dark = context.isDark;
    final gradient = primaryGradient(dark: dark);
    // A REAL PROGRESS FRACTION, NEVER A GUESSED ONE — `toNextReward` is what is missing, not what
    // is needed in total, so the total is reconstructed as `points + toNextReward` (the exact
    // relationship the server's own EarnSettings/Balance shape implies); 0 when there is nothing
    // useful to show (every reward already affordable, or none exist), matching that field's own
    // "0 means nothing to say" contract.
    final total = points + toNextReward;
    final fraction = toNextReward > 0 && total > 0 ? points / total : 1.0;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        gradient: gradient,
        borderRadius: AppRadius.cardRadius,
        boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
      ),
      child: Stack(
        children: [
          // ── decorative glass chrome only — never anything a reader must resolve ──────────
          Positioned.directional(
            textDirection: Directionality.of(context),
            top: -30,
            end: -20,
            child: Container(
              width: 120,
              height: 120,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.white.withValues(alpha: 0.08),
              ),
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(AppSpacing.xs),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.18),
                      borderRadius: BorderRadius.circular(AppRadius.sm),
                    ),
                    child: const Icon(Icons.stars_rounded, color: Colors.white, size: 18),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Text(
                    'رصيد النقاط',
                    style: AppTextStyles.labelMedium.copyWith(
                      color: Colors.white.withValues(alpha: 0.85),
                      letterSpacing: 0.2,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.sm),
              _CountUpNumber(value: points, style: AppTextStyles.displaySmall.copyWith(
                color: Colors.white,
                fontWeight: FontWeight.w800,
                fontSize: 40,
                fontFeatures: const [FontFeature.tabularFigures()],
              )),
              if (toNextReward > 0) ...[
                const SizedBox(height: AppSpacing.md),
                ClipRRect(
                  borderRadius: BorderRadius.circular(AppRadius.pill),
                  child: LinearProgressIndicator(
                    value: fraction.clamp(0.0, 1.0),
                    minHeight: 8,
                    backgroundColor: Colors.white.withValues(alpha: 0.22),
                    valueColor: const AlwaysStoppedAnimation(Colors.white),
                  ),
                ),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  'يبقى $toNextReward نقطة لمكافأة جديدة',
                  style: AppTextStyles.bodySmall.copyWith(color: Colors.white.withValues(alpha: 0.9)),
                ),
              ],
              if (rewards.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.md),
                Wrap(
                  spacing: AppSpacing.xs,
                  runSpacing: AppSpacing.xs,
                  children: [
                    for (final r in rewards.take(2))
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: AppSpacing.sm, vertical: AppSpacing.xs / 2,
                        ),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.16),
                          borderRadius: BorderRadius.circular(AppRadius.pill),
                          border: Border.all(color: Colors.white.withValues(alpha: 0.28)),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(Icons.redeem_rounded, size: 13, color: Colors.white),
                            const SizedBox(width: 4),
                            Text(
                              '${r['name']}',
                              style: AppTextStyles.bodySmall.copyWith(
                                color: Colors.white, fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                      ),
                  ],
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }
}

/// A balance that COUNTS UP to its real value rather than snapping — the exact "instantaneous
/// feedback" gamification research (this session's own GameEffects doc comment) asks for, reused
/// here for a number that changes as the operator moves to the next customer, not just for a
/// one-shot celebration.
class _CountUpNumber extends StatelessWidget {
  final int value;
  final TextStyle style;
  const _CountUpNumber({required this.value, required this.style});

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: value.toDouble()),
      duration: const Duration(milliseconds: 700),
      curve: Curves.easeOutCubic,
      builder: (context, animated, _) => Text(animated.round().toString(), style: style),
    );
  }
}
