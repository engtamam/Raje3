import 'dart:async';

import 'package:flutter/material.dart';

import 'package:raje3_mobile/core/services/customers_service.dart';
import 'package:raje3_mobile/models/customer_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

/// «متى موعدي الجاي؟» — search by phone, cross-date, cross-branch: the exact question a
/// receptionist answers by picking a customer here, mirroring apps/console/src/screens/
/// Bookings.tsx's own phone-search box (never a day/week grid question).
class BookingCustomerSearchSheet extends StatefulWidget {
  final CustomersService customersService;
  const BookingCustomerSearchSheet({super.key, required this.customersService});

  @override
  State<BookingCustomerSearchSheet> createState() => _BookingCustomerSearchSheetState();
}

class _BookingCustomerSearchSheetState extends State<BookingCustomerSearchSheet> {
  final _controller = TextEditingController();
  List<CustomerHit> _matches = const [];
  Timer? _debounce;
  bool _searching = false;

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _onChanged(String value) {
    _debounce?.cancel();
    if (value.trim().length < 3) {
      setState(() => _matches = const []);
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 250), () async {
      setState(() => _searching = true);
      final result = await widget.customersService.suggest(value.trim());
      if (!mounted) return;
      setState(() {
        _matches = result.hits;
        _searching = false;
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Container(
      constraints: BoxConstraints(maxHeight: appSheetMaxHeight(context)),
      padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.md, AppSpacing.lg, AppSpacing.xl),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('متى موعد عميل؟', style: AppTextStyles.headlineSmall.copyWith(color: colors.textPrimary)),
          const SizedBox(height: AppSpacing.md),
          KbAnchor(
            id: 'bookings.customer_search.phone_field',
            child: AppTextField(
              labelText: 'جوال العميل',
              controller: _controller,
              keyboardType: TextInputType.phone,
              textDirection: TextDirection.ltr,
              prefixIcon: Icons.phone_iphone_rounded,
              onChanged: _onChanged,
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          if (_searching)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: AppSpacing.lg),
              child: AppLoadingIndicator(size: 24),
            )
          else
            Flexible(
              child: SingleChildScrollView(
                child: KbAnchor(
                  id: 'bookings.customer_search.results',
                  child: Material(
                    type: MaterialType.transparency,
                    child: Column(
                      children: _matches
                          .map((hit) => ListTile(
                                onTap: () => Navigator.of(context).pop(hit),
                                leading: const Icon(Icons.person_outline),
                                title: Text(hit.name.isNotEmpty ? hit.name : hit.phone),
                                subtitle: hit.name.isNotEmpty
                                    ? Text(hit.phone, textDirection: TextDirection.ltr)
                                    : null,
                              ))
                          .toList(),
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
