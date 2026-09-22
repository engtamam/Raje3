import 'package:dio/dio.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/models/notification_item.dart';

/// The account's own in-app notification feed — a platform-wide, capability-free door
/// (`GET /api/v1/notifications`, `POST /api/v1/notifications/{id}/read`), the exact same real
/// backend apps/console/src/api.ts's own `listNotifications`/`markNotificationRead` already call.
/// Answers a plain JSON body directly, no `{success, data}` envelope — same reasoning
/// AuthService's own doc comment gives for talking to `apiClient.dio` directly rather than through
/// the wrapped `get<T>()` helper: any of our services can have written an item here via
/// notification-service's own `POST /internal/notify` (channel=inapp); this class neither knows
/// nor cares which one did.
class NotificationService {
  final ApiClient apiClient;

  NotificationService({required this.apiClient});

  /// Never throws — a failed read (offline, a transient 500) resolves to an empty list so a
  /// caller degrades to "nothing new" rather than crashing the whole screen over a bell icon.
  Future<List<NotificationItem>> list() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/notifications');
      final data = response.data;
      if (data is! Map) return const [];
      final items = data['items'];
      if (items is! List) return const [];
      return items
          .whereType<Map<String, dynamic>>()
          .map(NotificationItem.fromJson)
          .toList(growable: false);
    } on DioException {
      return const [];
    }
  }

  /// Best-effort — a failed mark-read is not worth surfacing to the operator; the item just
  /// shows as unread again next time the list is fetched.
  Future<void> markRead(String id) async {
    try {
      await apiClient.dio.post<dynamic>('/api/v1/notifications/${Uri.encodeComponent(id)}/read');
    } on DioException {
      // swallowed — see this method's own doc comment
    }
  }
}
