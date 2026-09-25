import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/models/service_model.dart';

/// «خدماتي ومنتجاتي» — the owner's own service catalogue CRUD (`operations.manage_services`,
/// `operations.create_service`, `operations.update_service`), same contract
/// apps/console/src/screens/Services.tsx already calls. RAW `apiClient.dio` calls, same
/// convention every other mobile service in this app already holds to.
///
/// NO DELETE ROUTE EXISTS, ON PURPOSE — the real server never refuses a delete for referential
/// reasons because there is no delete endpoint at all; `active: false` (retire) is the only
/// removal action, full stop. This class does not pretend otherwise.
class ServicesCatalogueService {
  final ApiClient apiClient;

  ServicesCatalogueService({required this.apiClient});

  /// `GET /api/v1/staff/services?include_retired=` — the owner's own full list (no pagination —
  /// the real server returns everything in one response).
  Future<List<ServiceItem>?> list({bool includeRetired = true}) async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/staff/services',
          queryParameters: {'include_retired': includeRetired});
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['services'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => ServiceItem.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `POST /api/v1/staff/services` — `priceMinor`/`durationMinutes`/`cycleDays` omitted (`null`)
  /// mean "not set", never sent as a literal `0` standing in for "unset"/"free".
  Future<ServiceItem?> create({
    required String name,
    int? priceMinor,
    int? durationMinutes,
    int? cycleDays,
    String description = '',
  }) async {
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/staff/services', data: {
        'name': name,
        if (priceMinor != null) 'price_minor': priceMinor,
        if (durationMinutes != null) 'duration_minutes': durationMinutes,
        if (cycleDays != null) 'cycle_days': cycleDays,
        if (description.isNotEmpty) 'description': description,
      });
      final body = response.data;
      if (body is! Map) return null;
      return ServiceItem.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  /// `PATCH /api/v1/staff/services/{id}` — every field here is "leave unchanged" when omitted;
  /// the caller only passes what it actually wants to change. `eligibleStaffIds: []` is a real,
  /// meaningful value (falls back to "every active field operator") — distinct from omitting it
  /// entirely — so it is passed via a sentinel wrapper, not `int?`-style null-means-omit.
  Future<ServiceItem?> update(
    String id, {
    String? name,
    int? priceMinor,
    int? durationMinutes,
    int? cycleDays,
    String? description,
    bool? active,
    List<String>? eligibleStaffIds,
    String? assignmentMode,
    List<String>? procedureStepIds,
  }) async {
    try {
      final response = await apiClient.dio.patch<dynamic>('/api/v1/staff/services/$id', data: {
        if (name != null) 'name': name,
        if (priceMinor != null) 'price_minor': priceMinor,
        if (durationMinutes != null) 'duration_minutes': durationMinutes,
        if (cycleDays != null) 'cycle_days': cycleDays,
        if (description != null) 'description': description,
        if (active != null) 'active': active,
        if (eligibleStaffIds != null) 'eligible_staff_ids': eligibleStaffIds,
        if (assignmentMode != null) 'assignment_mode': assignmentMode,
        if (procedureStepIds != null) 'procedure_step_ids': procedureStepIds,
      });
      final body = response.data;
      if (body is! Map) return null;
      return ServiceItem.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  /// `POST /api/v1/staff/services/{id}/image` — raw bytes base64-encoded in the JSON body, same
  /// convention WhatsApp media upload already uses in this app. Returns the updated row (its
  /// `hasImage` flips true) or `null` on a real failure — the route's own `{ok:false}` refusal
  /// shape never throws, so a non-2xx here is a genuine transport/validation error.
  Future<ServiceItem?> uploadImage(String id, {required Uint8List bytes, required String contentType}) async {
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/staff/services/$id/image', data: {
        'content_type': contentType,
        'data_base64': base64Encode(bytes),
      });
      final body = response.data;
      if (body is! Map) return null;
      return ServiceItem.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  /// `GET /api/v1/staff/services/{id}/image` — raw image bytes, 404 when the service carries no
  /// image at all (never called unless the caller already saw `hasImage == true`).
  Future<Uint8List?> fetchImage(String id) async {
    try {
      final response = await apiClient.dio.get<List<int>>(
        '/api/v1/staff/services/$id/image',
        options: Options(responseType: ResponseType.bytes),
      );
      final data = response.data;
      if (data == null) return null;
      return Uint8List.fromList(data);
    } on DioException {
      return null;
    }
  }

  /// `GET /api/v1/staff/procedure-steps?include_retired=` — the shop-wide shared checklist
  /// catalogue, referenced by id from any service's own `procedure_step_ids`.
  Future<List<ProcedureStep>?> procedureSteps({bool includeRetired = false}) async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/staff/procedure-steps',
          queryParameters: {'include_retired': includeRetired});
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['procedure_steps'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => ProcedureStep.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `POST /api/v1/staff/procedure-steps` — creates one new shared checklist line.
  Future<ProcedureStep?> createProcedureStep({
    required String text,
    String severity = 'normal',
    String trainingNote = '',
  }) async {
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/staff/procedure-steps', data: {
        'text': text,
        'severity': severity,
        if (trainingNote.isNotEmpty) 'training_note': trainingNote,
      });
      final body = response.data;
      if (body is! Map) return null;
      return ProcedureStep.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  /// `PATCH /api/v1/staff/procedure-steps/{id}` — `active: false` retires it (no delete route,
  /// same doctrine as services themselves).
  Future<ProcedureStep?> updateProcedureStep(
    String id, {
    String? text,
    String? severity,
    String? trainingNote,
    bool? active,
  }) async {
    try {
      final response = await apiClient.dio.patch<dynamic>('/api/v1/staff/procedure-steps/$id', data: {
        if (text != null) 'text': text,
        if (severity != null) 'severity': severity,
        if (trainingNote != null) 'training_note': trainingNote,
        if (active != null) 'active': active,
      });
      final body = response.data;
      if (body is! Map) return null;
      return ProcedureStep.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  /// `POST /api/v1/staff/procedure-checklist/export` — one or more services' ordered checklists,
  /// merged into one branded document (a step shared by more than one selected service is printed
  /// once, deduped server-side). Raw bytes (PDF/DOCX), never JSON — the caller writes them to a
  /// temp file and hands that to the OS share sheet, same convention `RatingsService.
  /// exportStaffPerformance` already established.
  Future<List<int>?> exportProcedureChecklist({
    required List<String> serviceIds,
    String fileFormat = 'pdf',
    String locale = 'ar',
  }) async {
    try {
      final response = await apiClient.dio.post<List<int>>(
        '/api/v1/staff/procedure-checklist/export',
        data: {'service_ids': serviceIds, 'file_format': fileFormat, 'locale': locale},
        options: Options(responseType: ResponseType.bytes),
      );
      return response.data;
    } on DioException {
      return null;
    }
  }

  // ── the reminders/loyalty settings TREE — services/reminders/app/api/v1/owner.py's own
  // `/reminders/settings*` routes and services/loyalty/app/api/v1/loyalty.py's own
  // `/loyalty/settings*` routes. Two separate services, deliberately two separate calls per
  // write here — this file's own header comment on why (`Services.tsx`'s "two stores behind one
  // form" doctrine): reminders owns the cycle/follow-up/groups, loyalty owns points, and merging
  // them behind one helper is exactly the mistake that produced "I changed the cycle and nothing
  // happened" the first time.

  /// `GET /api/v1/reminders/settings` — the whole tree in one call.
  Future<ReminderSettingsTree?> reminderSettings() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/reminders/settings');
      final body = response.data;
      if (body is! Map) return null;
      return ReminderSettingsTree.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  /// `PUT /api/v1/reminders/settings` — the tenant-wide default; reaches every service that
  /// still follows it and leaves every customised one alone.
  Future<bool> setGeneralReminderSettings({int? intervalDays, int? followUpDays}) async {
    try {
      await apiClient.dio.put<dynamic>('/api/v1/reminders/settings', data: {
        if (intervalDays != null) 'interval_days': intervalDays,
        if (followUpDays != null) 'follow_up_days': followUpDays,
      });
      return true;
    } on DioException {
      return false;
    }
  }

  /// `PUT /api/v1/reminders/settings/service/{id}` — gives one service its own override.
  Future<bool> setServiceReminderSettings(String serviceId, {int? intervalDays, int? followUpDays}) async {
    try {
      await apiClient.dio.put<dynamic>('/api/v1/reminders/settings/service/$serviceId', data: {
        if (intervalDays != null) 'interval_days': intervalDays,
        if (followUpDays != null) 'follow_up_days': followUpDays,
      });
      return true;
    } on DioException {
      return false;
    }
  }

  /// `DELETE /api/v1/reminders/settings/service/{id}` — «العودة للعام»: deletes the override so
  /// the service starts following general again, rather than freezing today's number into it.
  Future<bool> followGeneralReminderSettings(String serviceId) async {
    try {
      await apiClient.dio.delete<dynamic>('/api/v1/reminders/settings/service/$serviceId');
      return true;
    } on DioException {
      return false;
    }
  }

  /// `PUT /api/v1/reminders/settings/group/{name}` — creates the group if new, and puts the
  /// listed services into it; membership only, no values, unless `intervalDays`/`followUpDays`
  /// are explicitly passed.
  Future<bool> setReminderGroup(String name, {List<String> serviceIds = const [], int? intervalDays, int? followUpDays}) async {
    try {
      await apiClient.dio.put<dynamic>('/api/v1/reminders/settings/group/${Uri.encodeComponent(name)}', data: {
        'service_ids': serviceIds,
        if (intervalDays != null) 'interval_days': intervalDays,
        if (followUpDays != null) 'follow_up_days': followUpDays,
      });
      return true;
    } on DioException {
      return false;
    }
  }

  /// `DELETE /api/v1/reminders/settings/group/{name}/service/{id}` — takes one service out of
  /// its group; it returns to following general.
  Future<bool> leaveReminderGroup(String groupName, String serviceId) async {
    try {
      await apiClient.dio.delete<dynamic>(
          '/api/v1/reminders/settings/group/${Uri.encodeComponent(groupName)}/service/$serviceId');
      return true;
    } on DioException {
      return false;
    }
  }

  /// `DELETE /api/v1/reminders/settings/group/{name}` — deletes the group itself; its members
  /// stay exactly where they are, now ungrouped.
  Future<bool> deleteReminderGroup(String name) async {
    try {
      await apiClient.dio.delete<dynamic>('/api/v1/reminders/settings/group/${Uri.encodeComponent(name)}');
      return true;
    } on DioException {
      return false;
    }
  }

  /// `GET /api/v1/reminders/settings/suggest-group` — a proposal only, never acted on unless the
  /// owner agrees to it.
  Future<GroupSuggestion?> suggestReminderGroup() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/reminders/settings/suggest-group');
      final body = response.data;
      if (body is! Map) return null;
      return GroupSuggestion.fromJson(body['suggestion'] as Map<String, dynamic>?);
    } on DioException {
      return null;
    }
  }

  /// `GET /api/v1/loyalty/settings` — the earning tree, four levels deep.
  Future<EarnSettingsTree?> earnSettings() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/loyalty/settings');
      final body = response.data;
      if (body is! Map) return null;
      return EarnSettingsTree.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  /// `PUT /api/v1/loyalty/settings/mode` — the programme's own earning switch (spec §9.3):
  /// "services" (each service carries its own point value) or "invoice" (one point per riyal
  /// actually charged). Refused with the server's own real sentence when switching to "invoice"
  /// while any active service is still unpriced — `operations` computes the invoice amount from
  /// the catalogue's own prices, so an unpriced service would silently undercount. `null` on
  /// success, the refusal sentence otherwise.
  Future<String?> setEarnMode({required String mode, int pointsPerRiyal = 1}) async {
    try {
      final response = await apiClient.dio.put<dynamic>('/api/v1/loyalty/settings/mode', data: {
        'mode': mode,
        'points_per_riyal': pointsPerRiyal,
      });
      final status = response.statusCode ?? 0;
      if (status >= 200 && status < 300) return null;
      return _refusal(response.data);
    } on DioException catch (e) {
      return _refusal(e.response?.data);
    }
  }

  String _refusal(dynamic data) {
    if (data is! Map) return '';
    final message = data['message'] as String?;
    final reason = data['reason'] as String?;
    return (message?.isNotEmpty == true ? message : reason) ?? '';
  }

  /// `PUT /api/v1/loyalty/settings/general` — the tenant-wide points-per-visit default.
  Future<bool> setGeneralPoints(int points) async {
    try {
      await apiClient.dio.put<dynamic>('/api/v1/loyalty/settings/general', data: {'points': points});
      return true;
    } on DioException {
      return false;
    }
  }

  /// `PUT /api/v1/loyalty/settings/service/{id}` — one service's own points, overriding general.
  Future<bool> setServicePoints(String serviceId, int points) async {
    try {
      await apiClient.dio.put<dynamic>('/api/v1/loyalty/settings/service/$serviceId', data: {'points': points});
      return true;
    } on DioException {
      return false;
    }
  }

  /// `DELETE /api/v1/loyalty/settings/service/{id}` — «العودة للعام» for points, same "delete the
  /// override, never freeze today's number" doctrine as the reminder settings above.
  Future<bool> followGeneralPoints(String serviceId) async {
    try {
      await apiClient.dio.delete<dynamic>('/api/v1/loyalty/settings/service/$serviceId');
      return true;
    } on DioException {
      return false;
    }
  }

  // ── «الباقات» — services/operations/app/api/v1/staff.py's own `/staff/packages*` routes.
  // Mobile writes only the "manual" fields (name/services/price/description); the scheduling
  // fields the server also accepts default to "always offerable" (none of them are sent).

  /// `GET /api/v1/staff/packages?include_retired=`.
  Future<List<ServicePackage>?> listPackages({bool includeRetired = false}) async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/staff/packages',
          queryParameters: {'include_retired': includeRetired});
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['packages'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => ServicePackage.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `POST /api/v1/staff/packages` — at least two active service ids, a price above zero.
  Future<ServicePackage?> createPackage({
    required String name,
    required List<String> serviceIds,
    required int priceMinor,
    String description = '',
  }) async {
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/staff/packages', data: {
        'name': name,
        'service_ids': serviceIds,
        'price_minor': priceMinor,
        if (description.isNotEmpty) 'description': description,
      });
      final body = response.data;
      if (body is! Map) return null;
      return ServicePackage.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  /// `PATCH /api/v1/staff/packages/{id}` — `active: false` retires it (deactivate, never delete —
  /// a past visit that fulfilled this package must still make sense a year from now).
  Future<ServicePackage?> updatePackage(
    String id, {
    String? name,
    List<String>? serviceIds,
    int? priceMinor,
    String? description,
    bool? active,
  }) async {
    try {
      final response = await apiClient.dio.patch<dynamic>('/api/v1/staff/packages/$id', data: {
        if (name != null) 'name': name,
        if (serviceIds != null) 'service_ids': serviceIds,
        if (priceMinor != null) 'price_minor': priceMinor,
        if (description != null) 'description': description,
        if (active != null) 'active': active,
      });
      final body = response.data;
      if ((response.statusCode ?? 0) >= 400 || body is! Map) return null;
      return ServicePackage.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  /// `POST /api/v1/staff/services/bulk_import` — rows already parsed client-side (the server "has
  /// no business knowing what a .csv or .xlsx looks like", per its own docstring). Returns the
  /// created/updated/reactivated/deactivated counts on success, or `null` on a genuine failure;
  /// the one real refusal case (duplicate names in the file) surfaces via [BulkImportRefusal].
  Future<Map<String, int>?> bulkImportServices(
    List<Map<String, dynamic>> rows, {
    bool deactivateMissing = false,
  }) async {
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/staff/services/bulk_import', data: {
        'rows': rows,
        'deactivate_missing': deactivateMissing,
      });
      final body = response.data;
      if (body is! Map) return null;
      if (body['error'] != null) throw BulkImportRefusal(body['reason'] as String? ?? '');
      int asInt(dynamic v) => v is num ? v.toInt() : 0;
      return {
        'created': asInt(body['created']),
        'updated': asInt(body['updated']),
        'reactivated': asInt(body['reactivated']),
        'deactivated': asInt(body['deactivated']),
      };
    } on DioException catch (e) {
      final body = e.response?.data;
      if (body is Map && body['reason'] != null) {
        throw BulkImportRefusal(body['reason'] as String? ?? '');
      }
      return null;
    }
  }
}

/// The one real, named refusal `bulk_import_services` can give — duplicate names within the
/// uploaded file itself, or a malformed image cell — carrying the server's own Arabic sentence
/// rather than a generic failure message.
class BulkImportRefusal implements Exception {
  final String reason;
  const BulkImportRefusal(this.reason);
}
