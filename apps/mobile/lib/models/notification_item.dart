/// One in-app notification — mirrors notification-service's own real stored shape EXACTLY
/// (`id`/`title`/`body`/`read`/`ts`), the same one apps/console/src/api.ts's own `NotificationItem`
/// reads from `GET /api/v1/notifications`. No severity, no icon, no action link, because the
/// backend has never sent any of those — inventing fields here would silently read as blank
/// forever, same reasoning the console's own NotificationBell.tsx gives for staying this plain.
class NotificationItem {
  final String id;
  final String title;
  final String body;
  final bool read;
  final String ts;

  const NotificationItem({
    required this.id,
    required this.title,
    required this.body,
    required this.read,
    required this.ts,
  });

  factory NotificationItem.fromJson(Map<String, dynamic> json) {
    return NotificationItem(
      id: json['id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      body: json['body'] as String? ?? '',
      read: json['read'] as bool? ?? false,
      ts: json['ts'] as String? ?? '',
    );
  }
}
