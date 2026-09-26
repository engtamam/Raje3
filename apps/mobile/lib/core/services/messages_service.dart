import 'package:dio/dio.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/models/messages_model.dart';

/// «الحملات» — every real route Messages.tsx/MessagePreview.tsx/Launch.tsx call, ported 1:1.
/// See parity/messages.md for the full feature catalogue and the action-id table this mirrors.
class MessagesService {
  final ApiClient apiClient;

  MessagesService({required this.apiClient});

  Future<TodayStatus?> today() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/reminders/today');
      final body = response.data;
      if (body is! Map) return null;
      return TodayStatus.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  Future<List<ReasonRow>?> reasons() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/reminders/reasons');
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['reasons'] as List?) ?? const [];
      return rows.whereType<Map>().map((m) => ReasonRow.fromJson(Map<String, dynamic>.from(m))).toList();
    } on DioException {
      return null;
    }
  }

  Future<List<GoalRow>?> goals() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/campaigns/goals');
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['goals'] as List?) ?? const [];
      return rows.whereType<Map>().map((m) => GoalRow.fromJson(Map<String, dynamic>.from(m))).toList();
    } on DioException {
      return null;
    }
  }

  /// `PUT /api/v1/reminders/reasons/{id}` — turns one automatic reason on/off, optionally
  /// pointing it at a custom text (`template`, empty means "use ours"). Returns the server's own
  /// refusal sentence on failure, `null` on success.
  Future<String?> setReason(String reasonId, bool on, {String template = ''}) async {
    try {
      final response = await apiClient.dio.put<dynamic>(
        '/api/v1/reminders/reasons/$reasonId',
        data: {'on': on, if (template.isNotEmpty) 'template': template},
      );
      final status = response.statusCode ?? 0;
      if (status >= 200 && status < 300) return null;
      return _refusal(response.data);
    } on DioException catch (e) {
      return _refusal(e.response?.data);
    }
  }

  /// `GET /api/v1/reminders/reasons/{id}/preview` — the real wordings for an automatic reason,
  /// AND which one is sending now (`chosen`/`tone`) AND why the list is empty when it is
  /// (`empty_because`) — the whole answer, not just the options list.
  Future<PreviewAnswer?> previewReason(String reasonId) async {
    try {
      final response =
          await apiClient.dio.get<dynamic>('/api/v1/reminders/reasons/$reasonId/preview');
      final body = response.data;
      if (body is! Map) return null;
      return PreviewAnswer.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  /// `GET /api/v1/reminders/templates/by-type/{type}/preview` — same engine, no reason id: the
  /// goals with no automatic counterpart yet (announce/service_offer/package_offer).
  Future<PreviewAnswer?> previewByType(String templateType) async {
    try {
      final response = await apiClient.dio
          .get<dynamic>('/api/v1/reminders/templates/by-type/$templateType/preview');
      final body = response.data;
      if (body is! Map) return null;
      return PreviewAnswer.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  /// «اجعل هذا الصوت صوتك» (#326) — the tenant's own branding record carries the tone, merged
  /// never replaced (same reasoning `AuthService.setBranding` already documents for logo/accent:
  /// a bare `{tone: ...}` body would drop the shop's own logo). Reads the current record first so
  /// this is safe to call without the caller having read it itself.
  Future<bool> chooseTone(String tone) async {
    try {
      final read = await apiClient.dio.get<dynamic>('/api/v1/tenant');
      final data = read.data;
      final current = data is Map && data['branding'] is Map
          ? Map<String, dynamic>.from(data['branding'] as Map)
          : <String, dynamic>{};
      await apiClient.dio.put<dynamic>('/api/v1/tenant/branding', data: {
        'branding': {...current, 'tone': tone},
      });
      return true;
    } on DioException {
      return false;
    }
  }

  /// `POST /api/v1/reminders/templates` — a draft, and nothing reaches Meta until submitted.
  /// `fills` is the slot id in the order its chip sits in the body (`{{1}}` is `fills[0]`, …) —
  /// generated from position, never typed by the shop, so a gap or a wrong number is impossible.
  Future<String?> writeTemplate({
    required String reasonId,
    required String body,
    required List<String> fills,
    String replaces = '',
  }) async {
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/reminders/templates', data: {
        'reason_id': reasonId, 'body': body, 'fills': fills, 'replaces': replaces,
      });
      final status = response.statusCode ?? 0;
      if (status >= 200 && status < 300) {
        final data = response.data;
        if (data is Map && data['error'] != null) return data['error'].toString();
        return null;
      }
      return _refusal(response.data);
    } on DioException catch (e) {
      return _refusal(e.response?.data);
    }
  }

  /// `POST /api/v1/reminders/templates/{name}/submit` — sends his draft to WhatsApp for review.
  Future<String?> submitTemplate(String name) async {
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/reminders/templates/$name/submit');
      final status = response.statusCode ?? 0;
      if (status >= 200 && status < 300) return null;
      return _refusal(response.data);
    } on DioException catch (e) {
      return _refusal(e.response?.data);
    }
  }

  /// `POST /api/v1/reminders/templates/{name}/help` — «ساعدوني»: attaches Meta's own refusal
  /// sentence and his text to a queue a human answers.
  Future<String?> templateHelp(String name) async {
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/reminders/templates/$name/help');
      final status = response.statusCode ?? 0;
      if (status >= 200 && status < 300) return null;
      return _refusal(response.data);
    } on DioException catch (e) {
      return _refusal(e.response?.data);
    }
  }

  /// `GET /api/v1/reminders/templates` — the shop's own texts that are not sending yet, and why.
  Future<List<MyTemplate>?> myTemplates(String reasonId) async {
    try {
      final response = await apiClient.dio
          .get<dynamic>('/api/v1/reminders/templates', queryParameters: {'reason_id': reasonId});
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['templates'] as List?) ?? const [];
      return rows.whereType<Map>().map((m) => MyTemplate.fromJson(Map<String, dynamic>.from(m))).toList();
    } on DioException {
      return null;
    }
  }

  /// `GET /api/v1/reminders/templates/help` — every «ساعدوني» request and our reply.
  Future<List<TemplateHelpRequest>?> myTemplateHelp() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/reminders/templates/help');
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['requests'] as List?) ?? const [];
      return rows.whereType<Map>().map((m) => TemplateHelpRequest.fromJson(Map<String, dynamic>.from(m))).toList();
    } on DioException {
      return null;
    }
  }

  Future<List<ScheduleRow>?> schedule() async {
    try {
      final response = await apiClient.dio
          .get<dynamic>('/api/v1/reminders/schedule', queryParameters: {'state': 'pending', 'limit': 200});
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['schedule'] as List?) ?? const [];
      return rows.whereType<Map>().map((m) => ScheduleRow.fromJson(Map<String, dynamic>.from(m))).toList();
    } on DioException {
      return null;
    }
  }

  /// `DELETE /api/v1/reminders/schedule/{id}` — cancels ONE queued message, never the rule
  /// behind it: the next visit still schedules a new one.
  Future<bool> cancelSchedule(String id) async {
    try {
      final response = await apiClient.dio.delete<dynamic>('/api/v1/reminders/schedule/$id');
      final status = response.statusCode ?? 0;
      return status >= 200 && status < 300;
    } on DioException {
      return false;
    }
  }

  /// `(rows, denied)` — DENIED IS ITS OWN ANSWER, never folded into "failed". A role that cannot
  /// read the log and a peer that is down look identical over the wire (both throw) but must
  /// read as two different sentences: "you don't have permission" is never "try again later".
  Future<(List<MessageLogRow>?, bool)> log({String outcome = '', String branchId = ''}) async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/reminders/log', queryParameters: {
        'limit': 100,
        if (outcome.isNotEmpty) 'outcome': outcome,
        if (branchId.isNotEmpty) 'branch_id': branchId,
      });
      final body = response.data;
      if (body is! Map) return (null, false);
      final rows = (body['log'] as List?) ?? const [];
      return (
        rows.whereType<Map>().map((m) => MessageLogRow.fromJson(Map<String, dynamic>.from(m))).toList(),
        false,
      );
    } on DioException catch (e) {
      return (null, e.response?.statusCode == 403);
    }
  }

  Future<List<Campaign>?> campaigns() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/campaigns');
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['campaigns'] as List?) ?? const [];
      return rows.whereType<Map>().map((m) => Campaign.fromJson(Map<String, dynamic>.from(m))).toList();
    } on DioException {
      return null;
    }
  }

  /// `POST /api/v1/campaigns/preview` — the message and the real reach count, computed but
  /// never saved. This is the step that must never be skipped before a real send.
  Future<CampaignPreview?> previewCampaign(Map<String, dynamic> body) async {
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/campaigns/preview', data: body);
      final data = response.data;
      if (data is! Map) return null;
      return CampaignPreview.fromJson(Map<String, dynamic>.from(data));
    } on DioException catch (e) {
      // THE SERVER'S OWN REFUSAL SENTENCE ("لا يوجد قالب مفعّل لهذا الهدف" etc.) rides the error
      // body, same shape a success would carry — a refusal is still an answer worth showing.
      final data = e.response?.data;
      if (data is Map) return CampaignPreview.fromJson(Map<String, dynamic>.from(data));
      return null;
    }
  }

  /// `POST /api/v1/campaigns` — creates AND fires (or schedules), one press. Returns the
  /// server's own refusal sentence on failure, `null` on success.
  Future<String?> createCampaign(Map<String, dynamic> body) async {
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/campaigns', data: body);
      final status = response.statusCode ?? 0;
      if (status >= 200 && status < 300) return null;
      return _refusal(response.data);
    } on DioException catch (e) {
      return _refusal(e.response?.data);
    }
  }

  Future<String?> pauseCampaign(String id) async {
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/campaigns/$id/pause');
      final status = response.statusCode ?? 0;
      if (status >= 200 && status < 300) return null;
      return _refusal(response.data);
    } on DioException catch (e) {
      return _refusal(e.response?.data);
    }
  }

  Future<(List<CampaignRun>, Map<String, int>)?> runs(String campaignId) async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/campaigns/$campaignId/runs');
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['runs'] as List?) ?? const [];
      final totals = (body['totals'] as Map?) ?? const {};
      return (
        rows.whereType<Map>().map((m) => CampaignRun.fromJson(Map<String, dynamic>.from(m))).toList(),
        totals.map((k, v) => MapEntry(k.toString(), (v as num?)?.toInt() ?? 0)),
      );
    } on DioException {
      return null;
    }
  }

  String _refusal(dynamic data) {
    if (data is! Map) return '';
    final message = data['message'] as String?;
    final reason = data['reason'] as String?;
    return (message?.isNotEmpty == true ? message : reason) ?? '';
  }
}
