/// The store-only data shapes — mirrors apps/console/src/apps.ts (`AppRow`/`Owned`) and
/// useAppBilling.ts (`CartPreview`) exactly, field for field. `AppRow`/`kAppRows` is a STATIC
/// REGISTRY (the catalog of what we sell), never fetched — the console's own `APP_ROWS` is
/// hand-written TypeScript for the same reason (parity/app_store.md §1). `Plan`/`Subscription`/
/// `Invoice` themselves live in `auth_service.dart` — the ONE model set «الفوترة» and «متجر
/// التطبيقات» both read, never duplicated here.
library;

import 'package:flutter/material.dart';

/// One row in the sold-apps catalog. `route` is this app's real mobile route name when it has
/// one built (see AppRouter._screenFor) — absent for an app with no mobile screen yet, which
/// still shows here (locked or owned) but opens nothing when tapped, same honest
/// "_NotYetOnMobile" posture every other unbuilt nav section already takes.
class AppRow {
  const AppRow({
    required this.id,
    required this.key,
    required this.name,
    required this.what,
    this.route,
    required this.icon,
    this.vip = false,
    this.featuresPath,
  });

  final String id;
  /// The billing entitlement key (`feature.xxx`), or null for a row that is never sold
  /// separately (none exist on mobile's own subset today, kept for shape parity).
  final String? key;
  final String name;
  final String what;
  final String? route;
  /// A key into AppTileIcons — never a raw IconData literal at the call site, same "icon/tone
  /// are keys" discipline apps.ts's own AppRow.icon documents.
  final String icon;
  /// THE ONE VIP APP — matches AppTile.tsx's own fixed `app.id === 'whatsapp'` flag exactly.
  final bool vip;
  /// THE REAL FEATURE LIST'S OWN ROUTE — mirrors apps.ts's own `featuresAction` (console),
  /// resolved here straight to the real gateway path since this app has no catalog-action
  /// indirection layer for per-feature reads (services/*/app/manifest.py's own registration:
  /// campaigns→/api/v1/campaigns/features, loyalty→/api/v1/loyalty/features,
  /// insights→/api/v1/insights/features, bookings→/api/v1/bookings/features,
  /// whatsapp→/api/v1/assistant/features). Absent for every app operations itself owns
  /// (تسجيل زيارة/جهات الاتصال/التقييم/ولاء الشركاء/خدمات متنقلة/تبادل منافع) — those carry
  /// their real features INLINE on `Owned.apps[].features` instead (operations' own `apps.py`),
  /// same "never both" rule apps.ts's own `featuresAction` docstring states.
  final String? featuresPath;
}

/// One real, separately-nameable capability — mirrors apps.ts's own `AppFeature` field for
/// field (`services/*/app/core/features.py`'s wire shape). `icon`/`tone` are KEYS, never a
/// raw `IconData`/`Color` at this layer — `_appFeatureIcon`/`_appFeatureTone`
/// (apps_store_screen.dart) own the one mapping from each to a real widget, so a new backend
/// feature never needs a matching Flutter PR just to render.
class AppFeature {
  const AppFeature({
    required this.id, required this.title, required this.detail,
    required this.icon, required this.tone, required this.sharedWith, required this.ownedBy,
  });
  final String id;
  final String title;
  final String detail;
  final String icon;
  final String tone;
  final List<String> sharedWith;
  final String ownedBy;

  factory AppFeature.fromJson(Map<String, dynamic> j) => AppFeature(
        id: (j['id'] as String?) ?? '',
        title: (j['title'] as String?) ?? '',
        detail: (j['detail'] as String?) ?? '',
        icon: (j['icon'] as String?) ?? '',
        tone: (j['tone'] as String?) ?? '',
        sharedWith: ((j['shared_with'] as List?) ?? const []).whereType<String>().toList(),
        ownedBy: (j['owned_by'] as String?) ?? '',
      );
}

/// Every icon key `kAppRows` uses, resolved to a real widget — shared by the store screen's own
/// cards AND (2026-09-29) the home screen's synthetic tiles for an owned app that has no
/// `NavSectionDef` of its own (see NavProvider.extraOwnedSections's own doc comment). Was a
/// private `_appIcons` inside apps_store_screen.dart; hoisted here so a second file can read it
/// without either duplicating the map or importing a screen file for a constant.
const Map<String, IconData> kAppTileIcons = {
  'megaphone': Icons.campaign_rounded,
  'gift': Icons.card_giftcard_rounded,
  'calendar': Icons.calendar_month_rounded,
  'sparkles': Icons.auto_awesome_rounded,
  'star': Icons.star_rounded,
  'user-plus': Icons.person_add_rounded,
  'check-circle': Icons.check_circle_rounded,
  'message-circle': Icons.chat_bubble_rounded,
  'users': Icons.handshake_rounded,
  'hand-heart': Icons.volunteer_activism_rounded,
  'bot': Icons.smart_toy_rounded,
  'truck': Icons.local_shipping_rounded,
  'briefcase': Icons.work_rounded,
  'receipt': Icons.receipt_long_rounded,
  'headphones': Icons.headset_mic_rounded,
};

/// `GET /api/v1/subscription/apps/static-features`'s own real, tenant-free subkeys — mirrors the
/// console's own `launcher/launcherCatalog.ts::STATIC_FEATURES_SUBKEY` exactly. A row operations
/// owns outright carries no `featuresPath` of its own (its features ride along with
/// `Owned.apps[].features` instead), which only ever answers for an app already bought — a shop
/// still deciding WHETHER to buy one saw an empty features section otherwise.
const Map<String, String> kStaticFeaturesSubkey = {
  'feature.visit': 'visit', 'feature.contacts': 'contacts', 'feature.rating': 'rating',
  'feature.mobile_requests': 'mobile_requests', 'feature.coworking': 'coworking',
  'feature.partner_loyalty': 'coupons', 'feature.mutual_benefit': 'mutual_benefit',
  'feature.referrals': 'referrals',
};

/// apps.ts's own APP_ROWS, ported 1:1 for the subset with a real or plausible mobile surface —
/// see parity/app_store.md §1 for the full 13-row source table this is drawn from.
const List<AppRow> kAppRows = [
  AppRow(
    id: 'campaigns', key: 'feature.campaigns', name: 'الحملات',
    what: 'يعيد إليك عملاءك على وشك مغادرتك، فيكبر إيرادك من قاعدة عملائك الحالية بدل الاعتماد على زبون جديد فقط.',
    route: 'messages', icon: 'megaphone', featuresPath: '/api/v1/campaigns/features',
  ),
  AppRow(
    id: 'loyalty', key: 'feature.loyalty', name: 'برنامج النقاط',
    what: 'يبني ولاء عميلك لمحلك نفسه، لا لموظف بعينه — فيضمن رجوعه إليك دائماً أياً كان من يخدمه.',
    route: 'points', icon: 'gift', featuresPath: '/api/v1/loyalty/features',
  ),
  AppRow(
    id: 'bookings', key: 'feature.bookings', name: 'الحجوزات',
    what: 'يستثمر كل دقيقة في جدولك، فيرفع عدد العملاء الذين تخدمهم بنفس عدد موظفيك وساعاتهم.',
    icon: 'calendar', featuresPath: '/api/v1/bookings/features',
  ),
  AppRow(
    id: 'insights', key: 'feature.insights.engine', name: 'صفقات',
    what: 'يحوّل بيانات محلك اليومية إلى نصيحة واضحة بمستوى محلل مبيعات مختص، يقودك كل يوم لأعلى فرصة ترفع دخلك.',
    route: 'shop', icon: 'sparkles', featuresPath: '/api/v1/insights/features',
  ),
  AppRow(
    id: 'rating', key: 'feature.rating', name: 'التقييم',
    what: 'يحميك من خسارة عملاء دون علمك — يكشف مشكلة بموظف أو خدمة وتعالجها قبل أن تتفاقم.',
    route: 'rating', icon: 'star',
  ),
  AppRow(
    id: 'contacts', key: 'feature.contacts', name: 'جهات الاتصال',
    what: 'يبني لك قاعدة عملاء حقيقية من أول يوم لافتتاح محلك، تصبح أصلاً تسوّق عليه متى شئت.',
    route: 'customers', icon: 'user-plus',
  ),
  AppRow(
    id: 'visit', key: 'feature.visit', name: 'تسجيل زيارة',
    what: 'يجعل بيانات عملائك ملكاً لمحلك، تكبر معك مهما تغيّر فريق العمل.',
    route: 'visit', icon: 'check-circle',
  ),
  AppRow(
    id: 'whatsapp', key: 'feature.whatsapp', name: 'المساعد الذكي عبر واتساب',
    what: 'يحوّل واتساب إلى مندوب مبيعات يعرف ذوق كل عميل، ويقترح عليه باقاتك وعروضك ونقاطه في الوقت المناسب، فيرفع متوسط فاتورتك.',
    route: 'whatsapp-assistant', icon: 'message-circle', vip: true,
    featuresPath: '/api/v1/assistant/features',
  ),
  AppRow(
    id: 'partner-loyalty', key: 'feature.partner_loyalty', name: 'ولاء الشركاء',
    what: 'كوّن تحالفاً حقيقياً مع محل آخر مسجّل عندنا — امنحه امتيازاً على اشتراكه معنا يُطبَّق تلقائياً عند تجديده القادم.',
    route: 'partner-loyalty', icon: 'users',
  ),
  AppRow(
    id: 'mutual-benefit', key: 'feature.mutual_benefit', name: 'تبادل منافع',
    what: 'وسّع قاعدة عملائك دون ريال إعلان واحد — عميل محل تثق به يصير مستحقاً تلقائياً لعرضك بمجرد أن يثبت أنه عميل حقيقي.',
    route: 'mutual-benefit', icon: 'hand-heart',
  ),
  AppRow(
    id: 'mobile-ai-assistant', key: 'feature.mobile_ai_assistant', name: 'المساعد الذكي (تطبيق الجوال)',
    what: 'يجاوبك ويرشدك داخل تطبيق الجوال بصوتك أو بالكتابة، فوراً وبلا انتظار.',
    icon: 'bot',
  ),
  AppRow(
    id: 'mobile-requests', key: 'feature.mobile_requests', name: 'خدمات متنقلة',
    what: 'خدمتك تروح لعنده هو — يطلب موعداً، تراجعه وتقرر، ثم تسجّله زيارة حقيقية بعد ما تتم فعلاً.',
    route: 'mobile-requests', icon: 'truck',
  ),
  // «طلبات التوصيل عبر الواتساب» — mirrors apps/console/src/apps.ts's own row exactly (same
  // standalone-delivery-product posture, never confused with «خدمات متنقلة» above).
  AppRow(
    id: 'whatsapp-orders', key: 'feature.whatsapp_delivery_orders', name: 'طلبات التوصيل عبر الواتساب',
    what: 'عميلك يطلب من كتالوجك عبر واتساب ويدفع لحسابك مباشرة — تتابع كل طلب من لحظة الطلب إلى التسليم.',
    route: 'whatsapp-orders', icon: 'receipt',
  ),
  // «خدمات ما بعد البيع» — mirrors apps/console/src/apps.ts's own row exactly.
  AppRow(
    id: 'freelancers', key: 'feature.customer_service', name: 'خدمات ما بعد البيع',
    what: 'مستقل تثق به يتابع رضا عملائك بعد الزيارة — يسجّل ملاحظة، يمنح ترضية بسقف تحدده أنت، ويصعّد لك أي حالة غاضبة فوراً.',
    route: 'freelancers', icon: 'headphones',
  ),
  // «الاستضافة المهنية» — mirrors operations' own `core/apps.py::APPS`'s `feature.coworking` row
  // exactly (same `what` sentence). Backend-only until this pass; `route: 'coworking'` is this
  // row's real, stable mobile route now (app_router.dart's own `RouteNames.coworkingPath`).
  AppRow(
    id: 'coworking', key: 'feature.coworking', name: 'الاستضافة المهنية',
    what: 'يحوّل وقت محلك الفاضي إلى دخل إضافي — تؤجّر كرسياً أو محطة بالساعة لمستقلّين تثق بهم، بلا أي التزام مالي علينا.',
    route: 'coworking', icon: 'briefcase',
  ),
  // REAL KEY, SAME PATTERN EVERY OTHER ROW HERE USES (`feature.referrals`,
  // services/operations/app/core/apps.py) — a `listed: false` platform-tax feature, same shape
  // `feature.mutual_benefit`/`feature.coworking` already take, never `key: null` (that would skip
  // the real ownership check this row's own subscription state still has to pass). The caller's
  // own role gate (needing BOTH ownership and `referrals.list_campaigns`) lives in
  // `ReferralsScreen`'s own `CapabilityGate` and `NavProvider.ownedSections`, not here.
  AppRow(
    id: 'referrals', key: 'feature.referrals', name: 'نظام الإحالة',
    what: 'يحوّل عملاءك الحاليين إلى فريق مبيعات حقيقي — كل عميل يجلب عميلاً جديداً يكسب الاثنان مكافأة حقيقية.',
    route: 'referrals', icon: 'user-plus',
  ),
];

/// `GET /api/v1/subscription/apps` — what this shop actually owns, straight off the wire.
class OwnedApp {
  const OwnedApp({required this.key, required this.owned, required this.renewsAt, required this.features});
  final String key;
  final bool? owned;
  final int? renewsAt;
  /// ONLY FOR APPS OPERATIONS ITSELF OWNS (تسجيل زيارة/جهات الاتصال/التقييم/ولاء الشركاء/خدمات
  /// متنقلة/تبادل منافع) — mirrors apps.ts's own `Owned.apps[].features` exactly (operations'
  /// own `core/apps.py::APPS` rows carry them inline). Every other app's features are absent
  /// here and read from its own `AppRow.featuresPath` instead — never both.
  final List<AppFeature> features;

  factory OwnedApp.fromJson(Map<String, dynamic> j) => OwnedApp(
        key: (j['key'] as String?) ?? '',
        owned: j['owned'] as bool?,
        renewsAt: (j['renews_at'] as num?)?.toInt(),
        features: ((j['features'] as List?) ?? const [])
            .whereType<Map>()
            .map((m) => AppFeature.fromJson(Map<String, dynamic>.from(m)))
            .toList(),
      );
}

class Owned {
  const Owned({required this.checked, required this.keys, required this.apps});
  final bool checked;
  final List<String> keys;
  final List<OwnedApp> apps;

  static const empty = Owned(checked: false, keys: [], apps: []);

  factory Owned.fromJson(Map<String, dynamic> j) => Owned(
        checked: (j['checked'] as bool?) ?? false,
        keys: ((j['keys'] as List?) ?? const []).whereType<String>().toList(),
        apps: ((j['apps'] as List?) ?? const [])
            .whereType<Map>()
            .map((m) => OwnedApp.fromJson(Map<String, dynamic>.from(m)))
            .toList(),
      );

  /// Mirrors apps.ts::owns exactly — three answers, never two: `null` while unread.
  bool? owns(String key) {
    if (!checked) return null;
    return keys.contains(key);
  }

  int? renewsAtFor(String key) => apps.where((a) => a.key == key).map((a) => a.renewsAt).firstOrNull;

  /// The inline feature list operations already returned for this key, or `null` when this app
  /// carries none inline (it must be fetched from its own `AppRow.featuresPath` instead).
  List<AppFeature>? featuresFor(String key) {
    final row = apps.where((a) => a.key == key).firstOrNull;
    if (row == null || row.features.isEmpty) return null;
    return row.features;
  }
}

/// `POST /api/v1/subscription/checkout/preview` — useAppBilling.ts's own `CartPreview`.
class CartPreview {
  const CartPreview({
    required this.currency, required this.subtotalMinor, required this.discountMinor,
    required this.taxMinor, required this.totalMinor,
  });
  final String currency;
  final int subtotalMinor;
  final int discountMinor;
  final int taxMinor;
  final int totalMinor;

  factory CartPreview.fromJson(Map<String, dynamic> j) => CartPreview(
        currency: (j['currency'] as String?) ?? 'SAR',
        subtotalMinor: (j['subtotal_minor'] as num?)?.toInt() ?? 0,
        discountMinor: (j['discount_minor'] as num?)?.toInt() ?? 0,
        taxMinor: (j['tax_minor'] as num?)?.toInt() ?? 0,
        totalMinor: (j['total_minor'] as num?)?.toInt() ?? 0,
      );
}

extension _FirstOrNull<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}

