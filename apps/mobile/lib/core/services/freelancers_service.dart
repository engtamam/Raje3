import 'package:dio/dio.dart';
import 'package:raje3_mobile/core/network/api_client.dart';

/// «خدمات ما بعد البيع» — every real route
/// services/operations/app/api/v1/freelancers.py + freelancer_portal.py exposes, same shape
/// apps/console/src/screens/Freelancers.tsx already calls. Raw `apiClient.dio` calls, same
/// "plain JSON, never this app's own {success, data} envelope" posture [WhatsAppOrdersService]
/// already takes.
class FreelancerLink {
  final String id;
  final String phone;
  final String displayName;
  final bool active;
  final int created;

  FreelancerLink({
    required this.id,
    required this.phone,
    required this.displayName,
    required this.active,
    required this.created,
  });

  factory FreelancerLink.fromJson(Map<String, dynamic> j) => FreelancerLink(
        id: (j['id'] as String?) ?? '',
        phone: (j['phone'] as String?) ?? '',
        displayName: (j['display_name'] as String?) ?? '',
        active: (j['active'] as bool?) ?? false,
        created: (j['created'] as num?)?.toInt() ?? 0,
      );
}

class FreelancerRules {
  final int cooldownDays;
  final int dailyCap;

  FreelancerRules({required this.cooldownDays, required this.dailyCap});

  factory FreelancerRules.fromJson(Map<String, dynamic> j) => FreelancerRules(
        cooldownDays: (j['cooldown_days'] as num?)?.toInt() ?? 30,
        dailyCap: (j['daily_cap'] as num?)?.toInt() ?? 5,
      );
}

class RewardOption {
  final String id;
  final String kind; // discount | points | gift
  final String label;
  final int percent;
  final int points;

  RewardOption({
    required this.id,
    required this.kind,
    required this.label,
    required this.percent,
    required this.points,
  });

  factory RewardOption.fromJson(Map<String, dynamic> j) => RewardOption(
        id: (j['id'] as String?) ?? '',
        kind: (j['kind'] as String?) ?? '',
        label: (j['label'] as String?) ?? '',
        percent: (j['percent'] as num?)?.toInt() ?? 0,
        points: (j['points'] as num?)?.toInt() ?? 0,
      );
}

class FreelancerEscalation {
  final String id;
  final String customerId;
  final String note;
  final String status;
  final int created;

  FreelancerEscalation({
    required this.id,
    required this.customerId,
    required this.note,
    required this.status,
    required this.created,
  });

  factory FreelancerEscalation.fromJson(Map<String, dynamic> j) => FreelancerEscalation(
        id: (j['id'] as String?) ?? '',
        customerId: (j['customer_id'] as String?) ?? '',
        note: (j['note'] as String?) ?? '',
        status: (j['status'] as String?) ?? '',
        created: (j['created'] as num?)?.toInt() ?? 0,
      );
}

class FreelancerCustomerRow {
  final String customerId;
  final String name;
  final String phone;
  final int lastVisit;
  final String lastStatus;

  FreelancerCustomerRow({
    required this.customerId,
    required this.name,
    required this.phone,
    required this.lastVisit,
    required this.lastStatus,
  });

  factory FreelancerCustomerRow.fromJson(Map<String, dynamic> j) => FreelancerCustomerRow(
        customerId: (j['customer_id'] as String?) ?? '',
        name: (j['name'] as String?) ?? '',
        phone: (j['phone'] as String?) ?? '',
        lastVisit: (j['last_visit'] as num?)?.toInt() ?? 0,
        lastStatus: (j['last_status'] as String?) ?? '',
      );
}

class FreelancersService {
  final ApiClient apiClient;

  FreelancersService({required this.apiClient});

  static const String _manage = '/api/v1/staff/freelancers';
  static const String _portal = '/api/v1/staff/freelancer-portal';

  // ── roster ──────────────────────────────────────────────────────────────────────────────────
  Future<List<FreelancerLink>?> list() async {
    try {
      final response = await apiClient.dio.get<dynamic>(_manage);
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['freelancers'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => FreelancerLink.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  Future<FreelancerLink?> add({required String phone, required String displayName}) async {
    try {
      final response = await apiClient.dio
          .post<dynamic>(_manage, data: {'phone': phone, 'display_name': displayName});
      final body = response.data;
      if (body is! Map) return null;
      return FreelancerLink.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  Future<bool> deactivate(String linkId) async {
    try {
      await apiClient.dio.post<dynamic>('$_manage/$linkId/deactivate');
      return true;
    } on DioException {
      return false;
    }
  }

  // ── business rules ─────────────────────────────────────────────────────────────────────────
  Future<FreelancerRules?> getRules() async {
    try {
      final response = await apiClient.dio.get<dynamic>('$_manage/rules');
      final body = response.data;
      if (body is! Map) return null;
      return FreelancerRules.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  Future<FreelancerRules?> setRules({required int cooldownDays, required int dailyCap}) async {
    try {
      final response = await apiClient.dio.post<dynamic>('$_manage/rules',
          data: {'cooldown_days': cooldownDays, 'daily_cap': dailyCap});
      final body = response.data;
      if (body is! Map) return null;
      return FreelancerRules.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  // ── reward catalog ──────────────────────────────────────────────────────────────────────────
  Future<List<RewardOption>?> listRewardOptions() async {
    try {
      final response = await apiClient.dio.get<dynamic>('$_manage/reward-options');
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['options'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => RewardOption.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  Future<RewardOption?> addRewardOption({
    required String kind,
    required String label,
    int percent = 0,
    int points = 0,
  }) async {
    try {
      final response = await apiClient.dio.post<dynamic>('$_manage/reward-options',
          data: {'kind': kind, 'label': label, 'percent': percent, 'points': points});
      final body = response.data;
      if (body is! Map) return null;
      return RewardOption.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  // ── escalation inbox ───────────────────────────────────────────────────────────────────────
  Future<List<FreelancerEscalation>?> listEscalations({String statusFilter = ''}) async {
    try {
      final response = await apiClient.dio.get<dynamic>('$_manage/escalations',
          queryParameters: statusFilter.isEmpty ? null : {'status_filter': statusFilter});
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['escalations'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => FreelancerEscalation.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  Future<bool> resolveEscalation(String escalationId) async {
    try {
      await apiClient.dio.post<dynamic>('$_manage/escalations/$escalationId/resolve');
      return true;
    } on DioException {
      return false;
    }
  }

  // ── export ──────────────────────────────────────────────────────────────────────────────────
  Future<String?> exportNotes({required int since, required int until, bool includePii = false}) async {
    try {
      final response = await apiClient.dio.get<dynamic>('$_manage/notes/export',
          queryParameters: {'since': since, 'until': until, 'include_pii': includePii});
      final body = response.data;
      if (body is! Map) return null;
      return (body['text'] as String?) ?? '';
    } on DioException {
      return null;
    }
  }

  // ── workbench (the shared freelancer/internal-workspace door) ─────────────────────────────
  Future<List<FreelancerCustomerRow>?> listCustomers({String search = '', String statusFilter = ''}) async {
    try {
      final response = await apiClient.dio.get<dynamic>('$_portal/customers', queryParameters: {
        if (search.isNotEmpty) 'search': search,
        if (statusFilter.isNotEmpty) 'status_filter': statusFilter,
      });
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['customers'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => FreelancerCustomerRow.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  Future<bool> rateCustomer(String customerId, String status) async {
    try {
      await apiClient.dio
          .post<dynamic>('$_portal/customers/$customerId/rate', data: {'status': status});
      return true;
    } on DioException {
      return false;
    }
  }

  Future<bool> doNotDisturb(String customerId) async {
    try {
      await apiClient.dio.post<dynamic>('$_portal/customers/$customerId/do-not-disturb');
      return true;
    } on DioException {
      return false;
    }
  }

  Future<bool> grantReward(String customerId, String optionId) async {
    try {
      await apiClient.dio
          .post<dynamic>('$_portal/customers/$customerId/reward', data: {'option_id': optionId});
      return true;
    } on DioException {
      return false;
    }
  }

  Future<bool> escalate(String customerId, String note) async {
    try {
      await apiClient.dio.post<dynamic>('$_portal/customers/$customerId/escalate', data: {'note': note});
      return true;
    } on DioException {
      return false;
    }
  }

  Future<bool> addNote(String customerId, {required String text, required String status}) async {
    try {
      await apiClient.dio.post<dynamic>('$_portal/customers/$customerId/notes',
          data: {'text': text, 'status': status});
      return true;
    } on DioException {
      return false;
    }
  }
}
