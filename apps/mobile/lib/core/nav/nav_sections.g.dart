// GENERATED FILE — DO NOT EDIT BY HAND.
//
// Produced by scripts/gen_mobile_nav.py from:
//   - apps/console/src/nav.ts (the `SECTIONS` array)
//
// Re-run `python scripts/gen_mobile_nav.py` after nav.ts changes.
// ci/check_mobile_nav_is_generated.py fails the build if this file drifts
// from what the generator would currently produce.
//
// THE ORDER IS THE PRODUCT'S ARGUMENT, exactly as nav.ts's own header says —
// this list is in the SAME order as SECTIONS in nav.ts, and that order is what
// both the default landing screen and the default pin priority read.

import 'package:flutter/material.dart';

/// One navigable section, as nav.ts's own `Section` interface declares it —
/// see that file for the full reasoning (capability-derived nav, no role checks).
class NavSectionDef {
  final String id;
  final String path;
  final String label;
  final IconData icon;
  /// Every id must be present in the fetched catalogue for this section to show.
  /// Empty = always available (mirrors nav.ts's own `requires: []` rule).
  final List<String> requires;
  /// Which service provides its actions — a down service hides nothing (mirrors
  /// nav.ts's own `unreachable` handling), this is carried for parity/telemetry only.
  final String? service;

  const NavSectionDef({
    required this.id,
    required this.path,
    required this.label,
    required this.icon,
    required this.requires,
    this.service,
  });
}

/// SAME ORDER, SAME IDS AND `requires` AS nav.ts's `SECTIONS` — do not reorder
/// or hand-edit; re-run the generator instead.
const List<NavSectionDef> kNavSections = [
  NavSectionDef(
    id: 'visit',
    path: '/visit',
    label: 'تسجيل زيارة',
    icon: Icons.assignment_turned_in_outlined,
    requires: ['operations.record_visit'],
    service: 'operations',
  ),
  NavSectionDef(
    id: 'shop',
    path: '/shop',
    label: 'محلّي',
    icon: Icons.trending_up,
    requires: ['reminders.today', 'insights.dashboard'],
    service: 'insights',
  ),
  NavSectionDef(
    id: 'bookings',
    path: '/bookings',
    label: 'الحجوزات',
    icon: Icons.calendar_month_outlined,
    requires: ['bookings.list'],
    service: 'bookings',
  ),
  NavSectionDef(
    id: 'customers',
    path: '/customers',
    label: 'جهات الاتصال',
    icon: Icons.people_outline,
    requires: ['operations.recent'],
    service: 'operations',
  ),
  NavSectionDef(
    id: 'rating',
    path: '/rating',
    label: 'التقييم',
    icon: Icons.star_outline,
    requires: ['operations.ratings'],
    service: 'operations',
  ),
  NavSectionDef(
    id: 'partner-loyalty',
    path: '/partner-loyalty',
    label: 'ولاء الشركاء',
    icon: Icons.handshake_outlined,
    requires: ['operations.coupons_page'],
    service: 'operations',
  ),
  NavSectionDef(
    id: 'mutual-benefit',
    path: '/mutual-benefit',
    label: 'تبادل منافع',
    icon: Icons.volunteer_activism_outlined,
    requires: ['operations.mutual_benefit_list'],
    service: 'operations',
  ),
  NavSectionDef(
    id: 'mobile-requests',
    path: '/mobile-requests',
    label: 'خدمات متنقلة',
    icon: Icons.local_shipping_outlined,
    requires: ['operations.mobile_requests_list'],
    service: 'operations',
  ),
  NavSectionDef(
    id: 'services',
    path: '/services',
    label: 'خدماتي ومنتجاتي',
    icon: Icons.build_outlined,
    requires: ['operations.update_service'],
    service: 'operations',
  ),
  NavSectionDef(
    id: 'messages',
    path: '/messages',
    label: 'الحملات',
    icon: Icons.campaign_outlined,
    requires: ['reminders.get_settings'],
    service: 'reminders',
  ),
  NavSectionDef(
    id: 'points',
    path: '/points',
    label: 'نقاط الولاء',
    icon: Icons.card_giftcard_outlined,
    requires: ['loyalty.rewards.update'],
    service: 'loyalty',
  ),
  NavSectionDef(
    id: 'support',
    path: '/support',
    label: 'الدعم الفني',
    icon: Icons.support_outlined,
    requires: ['tickets.open'],
    service: 'ticket-service',
  ),
];
