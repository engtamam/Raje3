/// The store-only data shapes — mirrors apps/console/src/apps.ts (`AppRow`/`Owned`) and
/// useAppBilling.ts (`CartPreview`) exactly, field for field. `AppRow`/`kAppRows` is a STATIC
/// REGISTRY (the catalog of what we sell), never fetched — the console's own `APP_ROWS` is
/// hand-written TypeScript for the same reason (parity/app_store.md §1). `Plan`/`Subscription`/
/// `Invoice` themselves live in `auth_service.dart` — the ONE model set «الفوترة» and «متجر
/// التطبيقات» both read, never duplicated here.
library;

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
}

/// apps.ts's own APP_ROWS, ported 1:1 for the subset with a real or plausible mobile surface —
/// see parity/app_store.md §1 for the full 13-row source table this is drawn from.
const List<AppRow> kAppRows = [
  AppRow(
    id: 'campaigns', key: 'feature.campaigns', name: 'الحملات',
    what: 'يعيد إليك عملاءك على وشك مغادرتك، فيكبر إيرادك من قاعدة عملائك الحالية بدل الاعتماد على زبون جديد فقط.',
    icon: 'megaphone',
  ),
  AppRow(
    id: 'loyalty', key: 'feature.loyalty', name: 'برنامج النقاط',
    what: 'يبني ولاء عميلك لمحلك نفسه، لا لموظف بعينه — فيضمن رجوعه إليك دائماً أياً كان من يخدمه.',
    route: 'points', icon: 'gift',
  ),
  AppRow(
    id: 'bookings', key: 'feature.bookings', name: 'الحجوزات',
    what: 'يستثمر كل دقيقة في جدولك، فيرفع عدد العملاء الذين تخدمهم بنفس عدد موظفيك وساعاتهم.',
    icon: 'calendar',
  ),
  AppRow(
    id: 'insights', key: 'feature.insights.engine', name: 'صفقات',
    what: 'يحوّل بيانات محلك اليومية إلى نصيحة واضحة بمستوى محلل مبيعات مختص، يقودك كل يوم لأعلى فرصة ترفع دخلك.',
    route: 'shop', icon: 'sparkles',
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
  ),
  AppRow(
    id: 'partner-loyalty', key: 'feature.partner_loyalty', name: 'ولاء الشركاء',
    what: 'كوّن تحالفاً حقيقياً مع محل آخر مسجّل عندنا — امنحه امتيازاً على اشتراكه معنا يُطبَّق تلقائياً عند تجديده القادم.',
    route: 'partner-loyalty', icon: 'users',
  ),
  AppRow(
    id: 'referral-partnership', key: 'feature.referral_partnership', name: 'شراكة استراتيجية',
    what: 'وسّع قاعدة عملائك دون ريال إعلان واحد — عميل محل تثق به يصير مستحقاً تلقائياً لعرضك بمجرد أن يثبت أنه عميل حقيقي.',
    route: 'referral-partnership', icon: 'hand-heart',
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
];

/// `GET /api/v1/subscription/apps` — what this shop actually owns, straight off the wire.
class OwnedApp {
  const OwnedApp({required this.key, required this.owned, required this.renewsAt});
  final String key;
  final bool? owned;
  final int? renewsAt;

  factory OwnedApp.fromJson(Map<String, dynamic> j) => OwnedApp(
        key: (j['key'] as String?) ?? '',
        owned: j['owned'] as bool?,
        renewsAt: (j['renews_at'] as num?)?.toInt(),
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
