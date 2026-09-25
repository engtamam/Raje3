import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/nav/nav_sections.g.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/features/home/app_tone.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/branch_switcher.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';
import 'package:raje3_mobile/widgets/notification_bell.dart';

/// «الرئيسية» — the launcher, not a dashboard. MainShell's own doc comment settled this: every
/// super-app case study behind the fixed 5-slot bar (WeChat, Grab, Careem) surfaces its actual
/// services from a home-screen grid rather than the bar itself, so this screen's one job is that
/// grid — nothing here duplicates «تطبيقاتي»'s own full app-store browsing (search, categories,
/// buying) or «التحليلات»'s own dashboard.
///
/// LAID OUT AS A BENTO GRID, not a flat uniform grid — real 2026 home-screen research (bento
/// layouts: mockuuups.studio, saasframe.io, mydesigner.gg) is unanimous that a modular grid with
/// deliberately varied card sizes reads as organized-but-alive, where a flat grid of identical
/// tiles reads as a plain app drawer. Size here still encodes something true rather than
/// decorating: the ONE featured card is [NavProvider.customSlotSection] — the operator's own
/// real pinned choice (the exact same value the bottom bar's customizable slot already shows),
/// never a guessed "most used" app this build has no usage data to support. Every other visible
/// section then falls into a repeating wide/half/half rhythm purely for visual variety — no
/// invented ranking claimed for THIS tier, just presented at human scale instead of a spreadsheet
/// of equal boxes.
///
/// PERMISSIONS-FIRST BY CONSTRUCTION, not by a role check bolted on after: every tile below comes
/// straight from [NavProvider.visibleSections], the SAME server-filtered list the bottom bar's
/// own customizable slot and «تطبيقاتي» both trust — a capability-limited account (an employee
/// hired with one role, see services/operations/app/core/signup.py's own `hire()`) simply never
/// has a tile for anything it cannot open, with no separate logic here deciding that twice.
///
/// EACH TILE WEARS ITS APP'S REAL BRAND TONE ([toneForSection]) — the same identity
/// `apps/console/src/apps.ts` already gives it on the web console, not a single repeated accent
/// color for every app regardless of what it is.
///
/// NO INVENTED DATA. A "today" summary card was considered and dropped for this pass: nothing in
/// this app yet fetches real reminders/insights data (the 'shop' section itself is still
/// `_NotYetOnMobile`), and a card showing numbers nobody computed would be exactly the kind of
/// placeholder drift this project's own standing rule forbids. The greeting below is real (the
/// device's own clock plus the account holder's own name, when set), never invented.
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final nav = context.watch<NavProvider>();
    final sections = nav.visibleSections;
    final featured = nav.customSlotSection;
    final rest = featured == null
        ? sections
        : sections.where((sec) => sec.id != featured.id).toList(growable: false);

    return KbAnchor(
      id: 'home',
      child: Scaffold(
        backgroundColor: AppColors.surface0,
        body: RefreshIndicator(
          onRefresh: nav.load,
          child: CustomScrollView(
            slivers: [
              SliverToBoxAdapter(child: _HeroHeader(s: s)),
              if (sections.isEmpty)
                SliverFillRemaining(hasScrollBody: false, child: _EmptyState(s: s))
              else ...[
                if (featured != null)
                  SliverToBoxAdapter(
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(
                          AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, 0),
                      child: _FeaturedTile(section: featured, index: 0),
                    ),
                  ),
                SliverToBoxAdapter(
                  child: Padding(
                    padding:
                        const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.sm),
                    child: Text(s.homeAppsSectionTitle, style: AppTextStyles.headlineSmall),
                  ),
                ),
                SliverPadding(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                  sliver: SliverToBoxAdapter(child: _BentoBody(sections: rest, indexOffset: 1)),
                ),
                const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.xxl)),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// A real top bar, not bare text floating on the background — a gradient banner (the same brand
/// gradient every primary action in this app already uses) that carries the greeting, curves into
/// the content below with a rounded bottom edge, and clears the status bar itself via its own
/// SafeArea(bottom: false) rather than the whole screen's. A soft glass circle in the corner is
/// pure decorative chrome (never carries anything a reader must resolve) — the same
/// "glass for chrome, solid for numbers" split [LoyaltyBalanceCard] already established.
class _HeroHeader extends StatelessWidget {
  final S s;
  const _HeroHeader({required this.s});

  /// A real greeting (the device's own clock) — by name when the account holder set one
  /// (optionally at signup, or from «حسابي» on the console; see UserModel.ownerName's own doc
  /// comment for where that value actually lives), otherwise the same generic greeting as
  /// before. Never an invented name — this is exactly what the account holder typed, or nothing.
  String _greeting(String? ownerName) {
    final hour = DateTime.now().hour;
    if (ownerName != null && ownerName.isNotEmpty) {
      return hour < 12
          ? s.homeGreetingMorningNamed(ownerName)
          : s.homeGreetingEveningNamed(ownerName);
    }
    return hour < 12 ? s.homeGreetingMorning : s.homeGreetingEvening;
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().user;
    final phone = user?.phone;
    final ownerName = user?.ownerName;
    final dark = context.isDark;
    return Container(
      decoration: BoxDecoration(
        gradient: primaryGradient(dark: dark),
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(AppRadius.card)),
        boxShadow: dark ? AppShadows.darkButton : AppShadows.button,
      ),
      child: ClipRRect(
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(AppRadius.card)),
        child: Stack(
          children: [
            Positioned.directional(
              textDirection: Directionality.of(context),
              top: -36,
              end: -28,
              child: Container(
                width: 140,
                height: 140,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: Colors.white.withValues(alpha: 0.08),
                ),
              ),
            ),
            Positioned.directional(
              textDirection: Directionality.of(context),
              bottom: -50,
              start: -20,
              child: Container(
                width: 100,
                height: 100,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: Colors.white.withValues(alpha: 0.06),
                ),
              ),
            ),
            SafeArea(
              bottom: false,
              child: Padding(
                padding:
                    const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xl),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(_greeting(ownerName),
                              style:
                                  AppTextStyles.displaySmall.copyWith(color: AppColors.accentContrast)),
                          if (phone != null && phone.isNotEmpty) ...[
                            const SizedBox(height: AppSpacing.xs),
                            Text(phone,
                                style: AppTextStyles.bodyMedium.copyWith(
                                  color: AppColors.accentContrast.withValues(alpha: 0.85),
                                  fontFamily: AppTextStyles.englishFont,
                                )),
                          ],
                          const SizedBox(height: AppSpacing.sm),
                          const BranchChip(),
                        ],
                      ),
                    ),
                    const NotificationBell(),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// One large "start here" card for the operator's own pinned action — the same real
/// [NavSectionDef] the bottom bar's customizable slot already carries, presented at hero scale
/// instead of a same-size grid tile, with its tone as a full gradient wash rather than a soft
/// chip (the one tile on this screen that earns full-bleed color, per bento's own "size follows
/// value" rule).
class _FeaturedTile extends StatelessWidget {
  final NavSectionDef section;
  final int index;
  const _FeaturedTile({required this.section, required this.index});

  @override
  Widget build(BuildContext context) {
    final tone = ToneColors.of(context, toneForSection(section.id));
    final dark = context.isDark;
    return _Reveal(
      index: index,
      child: KbAnchor(
        id: section.id,
        child: Material(
          color: Colors.transparent,
          borderRadius: AppRadius.cardRadius,
          child: InkWell(
            borderRadius: AppRadius.cardRadius,
            onTap: () => context.goNamed(section.id),
            child: Ink(
              decoration: BoxDecoration(
                borderRadius: AppRadius.cardRadius,
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [tone.solid, tone.solid.withValues(alpha: 0.78)],
                ),
                boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
              ),
              child: Padding(
                padding: const EdgeInsets.all(AppSpacing.lg),
                child: Row(
                  children: [
                    Container(
                      width: 56,
                      height: 56,
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(AppRadius.md),
                      ),
                      child: Icon(section.icon, color: Colors.white, size: 28),
                    ),
                    const SizedBox(width: AppSpacing.md),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(section.label,
                              style: AppTextStyles.headlineSmall.copyWith(color: Colors.white)),
                          const SizedBox(height: 2),
                          Text(S.of(context)!.homeFeaturedStartNow,
                              style: AppTextStyles.bodySmall
                                  .copyWith(color: Colors.white.withValues(alpha: 0.85))),
                        ],
                      ),
                    ),
                    Icon(
                      Directionality.of(context) == TextDirection.rtl
                          ? Icons.chevron_left_rounded
                          : Icons.chevron_right_rounded,
                      color: Colors.white.withValues(alpha: 0.85),
                      size: 22,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// The bento body for every non-featured section: a repeating wide/half/half rhythm (one full-
/// width row, then a row of two half-width tiles), looping for as many sections as the account's
/// catalogue actually has. Built as plain Rows/Columns (no external grid package) so the pattern
/// stays exact regardless of list length, including the last, possibly-incomplete row.
class _BentoBody extends StatelessWidget {
  final List<NavSectionDef> sections;
  final int indexOffset;
  const _BentoBody({required this.sections, required this.indexOffset});

  @override
  Widget build(BuildContext context) {
    final rows = <Widget>[];
    var i = 0;
    var revealIndex = indexOffset;
    while (i < sections.length) {
      final isWideRow = i % 3 == 0;
      if (isWideRow) {
        rows.add(_BentoTile(
            section: sections[i], index: revealIndex, aspectRatio: 2.6, iconSize: 26));
        i += 1;
        revealIndex += 1;
      } else {
        final left = sections[i];
        final right = i + 1 < sections.length ? sections[i + 1] : null;
        rows.add(
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: _BentoTile(section: left, index: revealIndex, aspectRatio: 1.05),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: right != null
                    ? _BentoTile(section: right, index: revealIndex + 1, aspectRatio: 1.05)
                    : const SizedBox.shrink(),
              ),
            ],
          ),
        );
        i += right != null ? 2 : 1;
        revealIndex += right != null ? 2 : 1;
      }
      rows.add(const SizedBox(height: AppSpacing.md));
    }
    return Column(children: rows);
  }
}

class _BentoTile extends StatelessWidget {
  final NavSectionDef section;
  final int index;
  final double aspectRatio;
  final double iconSize;
  const _BentoTile({
    required this.section,
    required this.index,
    required this.aspectRatio,
    this.iconSize = 22,
  });

  @override
  Widget build(BuildContext context) {
    final tone = ToneColors.of(context, toneForSection(section.id));
    final dark = context.isDark;
    final wide = aspectRatio > 2;
    return _Reveal(
      index: index,
      child: KbAnchor(
        id: section.id,
        child: AspectRatio(
          aspectRatio: aspectRatio,
          child: Material(
            color: dark ? AppDarkColors.surface1 : AppColors.surface1,
            borderRadius: AppRadius.cardRadius,
            child: InkWell(
              borderRadius: AppRadius.cardRadius,
              onTap: () => context.goNamed(section.id),
              child: Ink(
                decoration: BoxDecoration(
                  borderRadius: AppRadius.cardRadius,
                  border: Border.all(color: dark ? AppDarkColors.borderSubtle : AppColors.borderSubtle),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  child: wide
                      ? Row(
                          children: [
                            _ToneIcon(tone: tone, icon: section.icon, size: iconSize),
                            const SizedBox(width: AppSpacing.sm),
                            Expanded(
                              child: Text(
                                section.label,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700),
                              ),
                            ),
                          ],
                        )
                      : Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            _ToneIcon(tone: tone, icon: section.icon, size: iconSize),
                            Text(
                              section.label,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w700),
                            ),
                          ],
                        ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _ToneIcon extends StatelessWidget {
  final ToneColors tone;
  final IconData icon;
  final double size;
  const _ToneIcon({required this.tone, required this.icon, required this.size});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size + 20,
      height: size + 20,
      decoration: BoxDecoration(color: tone.soft, borderRadius: BorderRadius.circular(AppRadius.sm)),
      child: Icon(icon, color: tone.onSoft, size: size),
    );
  }
}

/// A gentle staggered entrance — fade + rise, each tile a beat behind the last (capped so a long
/// catalogue never makes the bottom of the list wait seconds to appear). Pure polish: the grid is
/// fully interactive and correct even if this animation were removed entirely.
class _Reveal extends StatelessWidget {
  final int index;
  final Widget child;
  const _Reveal({required this.index, required this.child});

  @override
  Widget build(BuildContext context) {
    final delay = (index.clamp(0, 8)) * 45;
    return TweenAnimationBuilder<double>(
      key: ValueKey('reveal-$index'),
      tween: Tween(begin: 0, end: 1),
      duration: Duration(milliseconds: 320 + delay),
      curve: Curves.easeOutCubic,
      builder: (context, t, _) => Opacity(
        opacity: t,
        child: Transform.translate(offset: Offset(0, (1 - t) * 14), child: child),
      ),
      child: child,
    );
  }
}

class _EmptyState extends StatelessWidget {
  final S s;
  const _EmptyState({required this.s});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.apps_outlined, size: 48, color: AppColors.textMuted),
            const SizedBox(height: AppSpacing.md),
            Text(s.homeEmptyStateTitle, style: AppTextStyles.headlineSmall, textAlign: TextAlign.center),
            const SizedBox(height: AppSpacing.sm),
            Text(s.homeEmptyStateBody,
                style: AppTextStyles.bodyMedium.copyWith(color: AppColors.textSecondary),
                textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }
}
