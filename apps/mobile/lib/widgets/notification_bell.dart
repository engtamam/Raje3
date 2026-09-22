import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/services/notification_service.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/models/notification_item.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

/// The bell — this app's own mirror of the console's `NotificationBell.tsx`, reading the exact
/// same real backend feed (`NotificationService`'s own doc comment). FETCHED ON MOUNT (for the
/// badge count) AND AGAIN EVERY TIME THE PANEL OPENS — no polling while closed, same reasoning
/// the console's own component gives: an operator does not need his badge to update mid-shift to
/// the second, he needs it accurate the moment he looks.
class NotificationBell extends StatefulWidget {
  const NotificationBell({super.key});

  @override
  State<NotificationBell> createState() => _NotificationBellState();
}

class _NotificationBellState extends State<NotificationBell> {
  late final NotificationService _service;
  List<NotificationItem> _items = const [];
  bool _loaded = false;

  @override
  void initState() {
    super.initState();
    _service = context.read<NotificationService>();
    _refresh();
  }

  Future<void> _refresh() async {
    final items = await _service.list();
    if (!mounted) return;
    setState(() {
      _items = items;
      _loaded = true;
    });
  }

  int get _unreadCount => _items.where((i) => !i.read).length;

  Future<void> _open() async {
    await _refresh();
    if (!mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _NotificationSheet(
        items: _items,
        onMarkRead: (item) async {
          await _service.markRead(item.id);
          if (!mounted) return;
          setState(() {
            _items = _items
                .map((i) => i.id == item.id
                    ? NotificationItem(id: i.id, title: i.title, body: i.body, read: true, ts: i.ts)
                    : i)
                .toList(growable: false);
          });
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final unread = _unreadCount;
    return KbAnchor(
      id: 'home.notifications',
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          SizedBox(
            width: 44,
            height: 44,
            child: Material(
              color: Colors.white.withValues(alpha: 0.16),
              shape: const CircleBorder(),
              child: InkWell(
                customBorder: const CircleBorder(),
                onTap: _open,
                child: Center(
                  child: Icon(
                    unread > 0 ? Icons.notifications_rounded : Icons.notifications_outlined,
                    color: AppColors.accentContrast,
                    size: 22,
                  ),
                ),
              ),
            ),
          ),
          if (_loaded && unread > 0)
            Positioned(
              top: 2,
              right: 2,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                constraints: const BoxConstraints(minWidth: 18),
                decoration: BoxDecoration(
                  color: AppColors.warning,
                  borderRadius: BorderRadius.circular(9),
                  border: Border.all(color: AppColors.accent, width: 1.5),
                ),
                child: Text(
                  unread > 9 ? '9+' : '$unread',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: Colors.black,
                    fontSize: 10,
                    fontWeight: FontWeight.w800,
                    height: 1.2,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _NotificationSheet extends StatelessWidget {
  final List<NotificationItem> items;
  final Future<void> Function(NotificationItem) onMarkRead;
  const _NotificationSheet({required this.items, required this.onMarkRead});

  String _ago(BuildContext context, String ts) {
    final s = S.of(context)!;
    final then = DateTime.tryParse(ts);
    if (then == null) return '';
    final minutes = DateTime.now().difference(then).inMinutes;
    if (minutes < 1) return s.notificationsAgoJustNow;
    if (minutes < 60) return s.notificationsAgoMinutes(minutes);
    final hours = minutes ~/ 60;
    if (hours < 24) return s.notificationsAgoHours(hours);
    final days = hours ~/ 24;
    if (days == 1) return s.notificationsAgoYesterday;
    return s.notificationsAgoDays(days);
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;
    return DraggableScrollableSheet(
      initialChildSize: 0.6,
      minChildSize: 0.35,
      maxChildSize: 0.92,
      expand: false,
      builder: (context, scrollController) => Container(
        decoration: BoxDecoration(
          color: dark ? AppDarkColors.surface0 : AppColors.surface0,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
          boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
        ),
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.md, AppSpacing.lg, AppSpacing.sm),
              child: Row(
                children: [
                  Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      gradient: appPrimaryGradient,
                      borderRadius: BorderRadius.circular(AppRadius.md),
                    ),
                    child: const Icon(Icons.notifications_rounded, color: AppColors.accentContrast, size: 20),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Text(s.notificationsTitle, style: AppTextStyles.headlineSmall),
                ],
              ),
            ),
            Expanded(
              child: items.isEmpty
                  ? Center(
                      child: Padding(
                        padding: const EdgeInsets.all(AppSpacing.xl),
                        child: Text(
                          s.notificationsEmptyState,
                          style: AppTextStyles.bodyMedium.copyWith(color: AppColors.textSecondary),
                        ),
                      ),
                    )
                  : ListView.separated(
                      controller: scrollController,
                      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.xs),
                      itemCount: items.length,
                      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.xs),
                      itemBuilder: (context, i) {
                        final item = items[i];
                        return Material(
                          color: item.read
                              ? Colors.transparent
                              : (dark ? AppDarkColors.accentSoft : AppColors.accentSoft),
                          borderRadius: AppRadius.standardRadius,
                          child: InkWell(
                            borderRadius: AppRadius.standardRadius,
                            onTap: item.read ? null : () => onMarkRead(item),
                            child: Padding(
                              padding: const EdgeInsets.all(AppSpacing.md),
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  if (!item.read)
                                    Padding(
                                      padding: const EdgeInsets.only(top: 6, left: 8),
                                      child: Container(
                                        width: 8,
                                        height: 8,
                                        decoration: const BoxDecoration(
                                          color: AppColors.accent,
                                          shape: BoxShape.circle,
                                        ),
                                      ),
                                    ),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(item.title,
                                            style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700)),
                                        const SizedBox(height: 2),
                                        Text(item.body, style: AppTextStyles.bodySmall),
                                        const SizedBox(height: 4),
                                        Text(_ago(context, item.ts),
                                            style: AppTextStyles.caption.copyWith(color: AppColors.textMuted)),
                                      ],
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }
}
