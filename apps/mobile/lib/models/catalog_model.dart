/// The action catalogue, mirroring apps/console/src/catalog.ts's `Catalog`/`Action` shape
/// exactly (same field names, same meaning) — see that file's own doc comment for why this
/// exists at all: the gateway has already filtered by capability before this app sees it, so
/// "should this section exist" is answered by what is present here, never by a role check.
///
/// Fetched from `GET /api/v1/app/catalog` (see catalog_service.dart).
class CatalogAction {
  final String id;
  final String label;
  final String method;
  final String path;
  final String capability;

  const CatalogAction({
    required this.id,
    required this.label,
    required this.method,
    required this.path,
    required this.capability,
  });

  factory CatalogAction.fromJson(Map<String, dynamic> json) {
    return CatalogAction(
      id: json['id'] as String? ?? '',
      label: json['label'] as String? ?? '',
      method: json['method'] as String? ?? 'GET',
      path: json['path'] as String? ?? '',
      capability: json['capability'] as String? ?? '',
    );
  }
}

class CatalogServiceEntry {
  final String service;
  final List<CatalogAction> actions;

  const CatalogServiceEntry({required this.service, required this.actions});

  factory CatalogServiceEntry.fromJson(Map<String, dynamic> json) {
    final rawActions = json['actions'] as List<dynamic>? ?? const [];
    return CatalogServiceEntry(
      service: json['service'] as String? ?? '',
      actions: rawActions
          .whereType<Map<String, dynamic>>()
          .map(CatalogAction.fromJson)
          .toList(growable: false),
    );
  }
}

class Catalog {
  final List<CatalogServiceEntry> services;
  final List<String> unreachable;

  const Catalog({required this.services, required this.unreachable});

  factory Catalog.fromJson(Map<String, dynamic> json) {
    final rawServices = json['services'] as List<dynamic>? ?? const [];
    final rawUnreachable = json['unreachable'] as List<dynamic>? ?? const [];
    return Catalog(
      services: rawServices
          .whereType<Map<String, dynamic>>()
          .map(CatalogServiceEntry.fromJson)
          .toList(growable: false),
      unreachable: rawUnreachable.map((e) => e.toString()).toList(growable: false),
    );
  }

  /// An empty catalogue — used before the first fetch resolves, or after a failed one, so
  /// callers never need to null-check the catalogue itself (mirrors nav_provider.dart's own
  /// "fail into nothing visible, not into a crash" rule).
  static const empty = Catalog(services: [], unreachable: []);

  /// Every action, flattened — mirrors catalog.ts's `allActions`.
  List<CatalogAction> get allActions => services.expand((s) => s.actions).toList(growable: false);

  /// Does this session hold every one of [ids]? Mirrors catalog.ts's `hasAll` EXACTLY —
  /// same "ids are unique enough for this check" assumption, same all-or-nothing result.
  bool hasAll(List<String> ids) {
    final have = allActions.map((a) => a.id).toSet();
    return ids.every(have.contains);
  }
}
