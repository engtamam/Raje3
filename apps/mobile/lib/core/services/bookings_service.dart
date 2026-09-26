import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/models/booking_model.dart';

/// «الحجوزات» — every route apps/console/src/screens/Bookings.tsx/BookingDialog.tsx already
/// call, same contract services/bookings/app/api/v1/bookings.py serves. RAW `apiClient.dio`
/// calls, same convention every other mobile service in this app already holds to.
class BookingsService {
  final ApiClient apiClient;

  BookingsService({required this.apiClient});

  /// `GET /api/v1/bookings` — every booking for one branch, one business day (`YYYY-MM-DD`).
  Future<List<Booking>?> list({required String branchId, required String date}) async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/bookings',
          queryParameters: {'branch_id': branchId, 'date': date});
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['bookings'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => Booking.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `GET /api/v1/bookings/risk` — how many of her last five CLOSED appointments she did not
  /// attend. `null` on failure is read as "no signal," never as "safe."
  Future<NoShowRisk?> risk(String customerId) async {
    try {
      final response = await apiClient.dio
          .get<dynamic>('/api/v1/bookings/risk', queryParameters: {'customer_id': customerId});
      final body = response.data;
      if (body is! Map) return null;
      return NoShowRisk.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  /// `GET /api/v1/bookings/nearest-any` — ONE call across every eligible operator; each
  /// returned slot names the operator it actually belongs to.
  Future<List<BookingSlot>?> nearestSlotsAny({
    required String branchId,
    required List<String> operatorIds,
    required List<String> serviceIds,
    required int after,
    required int windowEnd,
    required int maxSlots,
    String? excludeBookingId,
    Map<String, int>? quantities,
  }) async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/bookings/nearest-any', queryParameters: {
        'branch_id': branchId,
        'operator_ids': operatorIds.join(','),
        'service_ids': serviceIds.join(','),
        'after': after,
        'window_end': windowEnd,
        'max_slots': maxSlots,
        if (excludeBookingId != null) 'exclude_booking_id': excludeBookingId,
        if (quantities != null && quantities.isNotEmpty) 'quantities': _quantitiesJson(quantities),
      });
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['slots'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => BookingSlot.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `GET /api/v1/bookings/nearest` — the whole-horizon single-operator search behind "أقرب
  /// يوم فيه موعد" (jump to the next day something is actually free).
  Future<int?> nearestSlot({
    required String branchId,
    required String operatorId,
    required List<String> serviceIds,
    required int after,
    String? excludeBookingId,
    Map<String, int>? quantities,
  }) async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/bookings/nearest', queryParameters: {
        'branch_id': branchId,
        'operator_id': operatorId,
        'service_ids': serviceIds.join(','),
        'after': after,
        if (excludeBookingId != null) 'exclude_booking_id': excludeBookingId,
        if (quantities != null && quantities.isNotEmpty) 'quantities': _quantitiesJson(quantities),
      });
      final body = response.data;
      if (body is! Map || body['starts_at'] == null) return null;
      return (body['starts_at'] as num).toInt();
    } on DioException {
      return null;
    }
  }

  /// `POST /api/v1/bookings` — the customer must already be resolved (ensure/pick) before this.
  Future<Booking?> create({
    required String branchId,
    required String operatorId,
    required String customerId,
    required List<String> serviceIds,
    required int startsAt,
    Map<String, int>? quantities,
    String? note,
    String? idempotencyKey,
    String paymentStatus = 'none',
    int? depositAmountMinor,
    String? intendedRewardId,
  }) async {
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/bookings', data: {
        'branch_id': branchId,
        'operator_id': operatorId,
        'customer_id': customerId,
        'service_ids': serviceIds,
        if (quantities != null && quantities.isNotEmpty) 'quantities': quantities,
        'starts_at': startsAt,
        if (note != null && note.isNotEmpty) 'note': note,
        if (idempotencyKey != null) 'idempotency_key': idempotencyKey,
        'payment_status': paymentStatus,
        if (depositAmountMinor != null) 'deposit_amount_minor': depositAmountMinor,
        if (intendedRewardId != null) 'intended_reward_id': intendedRewardId,
      });
      final body = response.data;
      if (body is! Map) return null;
      return Booking.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  Future<Booking?> _patch(String path, Map<String, dynamic> data) async {
    try {
      final response = await apiClient.dio.patch<dynamic>(path, data: data);
      final body = response.data;
      if (body is! Map) return null;
      return Booking.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  Future<Booking?> reschedule(String id, int startsAt, {String? operatorId}) => _patch(
        '/api/v1/bookings/${Uri.encodeComponent(id)}/reschedule',
        {'starts_at': startsAt, if (operatorId != null && operatorId.isNotEmpty) 'operator_id': operatorId},
      );

  Future<Booking?> editServices(String id, List<String> serviceIds, {Map<String, int>? quantities}) =>
      _patch('/api/v1/bookings/${Uri.encodeComponent(id)}/services',
          {'service_ids': serviceIds, 'quantities': quantities ?? const {}});

  Future<Booking?> editNote(String id, String note) =>
      _patch('/api/v1/bookings/${Uri.encodeComponent(id)}/note', {'note': note});

  Future<Booking?> editPayment(String id, String paymentStatus, {int? depositAmountMinor}) => _patch(
        '/api/v1/bookings/${Uri.encodeComponent(id)}/payment',
        {'payment_status': paymentStatus, if (depositAmountMinor != null) 'deposit_amount_minor': depositAmountMinor},
      );

  Future<Booking?> editReward(String id, String? rewardId) =>
      _patch('/api/v1/bookings/${Uri.encodeComponent(id)}/reward', {'reward_id': rewardId});

  Future<Booking?> cancel(String id, {String? reason}) => _patch(
      '/api/v1/bookings/${Uri.encodeComponent(id)}/cancel', {if (reason != null) 'reason': reason});

  Future<Booking?> attend(String id, {int? occurredAt}) => _patch(
      '/api/v1/bookings/${Uri.encodeComponent(id)}/attend', {if (occurredAt != null) 'occurred_at': occurredAt});

  Future<Booking?> noShow(String id, {String? reason}) => _patch(
      '/api/v1/bookings/${Uri.encodeComponent(id)}/no-show', {if (reason != null) 'reason': reason});

  String _quantitiesJson(Map<String, int> quantities) => jsonEncode(quantities);
}
