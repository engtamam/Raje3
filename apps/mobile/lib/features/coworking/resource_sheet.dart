import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import 'package:raje3_mobile/core/services/auth_service.dart' show Branch;
import 'package:raje3_mobile/core/services/coworking_service.dart';
import 'package:raje3_mobile/models/coworking_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/date_time_picker_sheet.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

const List<String> _dayLabels = ['الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد'];

/// Create/edit one resource — name, branch, description, hourly price, a simple one-window-per-
/// day availability grid, and its one photo. Everything a real `showModalBottomSheet`, capped
/// with [appSheetMaxHeight] like every other growable sheet in this app.
class ResourceSheet extends StatefulWidget {
  const ResourceSheet({super.key, required this.service, required this.branches, this.existing});
  final CoworkingService service;
  final List<Branch> branches;
  final CoworkingResource? existing;

  @override
  State<ResourceSheet> createState() => _ResourceSheetState();
}

class _ResourceSheetState extends State<ResourceSheet> {
  late final TextEditingController _nameController;
  late final TextEditingController _descriptionController;
  late final TextEditingController _priceController;
  String _branchId = '';
  bool _active = true;
  bool _saving = false;
  String? _error;

  // One open window per weekday, weekday int -> (startMinute, endMinute), absent == closed.
  late Map<int, CoworkingWindow> _weekly;

  Uint8List? _newPhotoBytes;
  String? _newPhotoContentType;
  bool _uploadingPhoto = false;

  bool get _isEdit => widget.existing != null;

  @override
  void initState() {
    super.initState();
    final r = widget.existing;
    _nameController = TextEditingController(text: r?.name ?? '');
    _descriptionController = TextEditingController(text: r?.description ?? '');
    _priceController = TextEditingController(text: r != null ? (r.hourlyPriceMinor / 100).toStringAsFixed(0) : '');
    _branchId = r?.branchId ?? '';
    _active = r?.active ?? true;
    _weekly = {
      for (final entry in (r?.weekly ?? const {}).entries)
        if (entry.value.isNotEmpty) entry.key: entry.value.first,
    };
  }

  @override
  void dispose() {
    _nameController.dispose();
    _descriptionController.dispose();
    _priceController.dispose();
    super.dispose();
  }

  Future<void> _pickPhoto() async {
    try {
      final picker = ImagePicker();
      final file = await picker.pickImage(source: ImageSource.gallery, maxWidth: 1080, imageQuality: 85);
      if (file == null) return;
      final bytes = await file.readAsBytes();
      setState(() {
        _newPhotoBytes = bytes;
        _newPhotoContentType = file.mimeType ?? 'image/jpeg';
      });
    } catch (_) {
      // A picker failure (permission denied, no camera roll on this platform) is silent here —
      // the field simply stays empty, same posture services_screen.dart's own picker already takes.
    }
  }

  Future<void> _submit() async {
    final name = _nameController.text.trim();
    if (name.isEmpty) {
      setState(() => _error = 'اسم المورد مطلوب');
      return;
    }
    final priceRiyals = double.tryParse(_priceController.text.trim()) ?? 0;
    setState(() {
      _saving = true;
      _error = null;
    });

    String? resourceId = widget.existing?.id;
    String? reason;
    if (_isEdit) {
      reason = await widget.service.updateResource(
        resourceId!,
        name: name,
        active: _active,
        branchId: _branchId,
        description: _descriptionController.text.trim(),
      );
    } else {
      reason = await widget.service.createResource(
        name: name,
        branchId: _branchId,
        description: _descriptionController.text.trim(),
      );
      if (reason == null) {
        // The create route returns the resource itself, but this service's own `createResource`
        // deliberately mirrors the other create calls in this app (returns only the refusal, not
        // the row) — a fresh list load right after closing this sheet is what actually shows it,
        // same convention `points_screen.dart`'s own `_openAddSheet` already follows. Availability
        // and a photo on a BRAND NEW resource are added on the very next edit instead of chained
        // here, since this call gives us no id to attach them to yet.
      }
    }

    if (reason != null) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = reason!.isNotEmpty ? reason : 'تعذر الحفظ';
      });
      return;
    }

    if (_isEdit && resourceId != null) {
      await widget.service.setAvailability(
        resourceId,
        weekly: {for (final entry in _weekly.entries) entry.key: [entry.value]},
        hourlyPriceMinor: (priceRiyals * 100).round(),
      );
      if (_newPhotoBytes != null) {
        setState(() => _uploadingPhoto = true);
        await widget.service.uploadImage(resourceId, bytes: _newPhotoBytes!, contentType: _newPhotoContentType ?? 'image/jpeg');
        if (!mounted) return;
        setState(() => _uploadingPhoto = false);
      }
    }

    if (!mounted) return;
    Navigator.of(context).pop(true);
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: Container(
        constraints: BoxConstraints(maxHeight: appSheetMaxHeight(context)),
        padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xl),
        decoration: BoxDecoration(
          color: colors.surface,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(_isEdit ? 'تعديل المورد' : 'مورد جديد', style: AppTextStyles.headlineSmall),
              const SizedBox(height: AppSpacing.lg),
              KbAnchor(
                id: 'coworking.resource_sheet.photo',
                child: GestureDetector(
                  onTap: _pickPhoto,
                  child: Container(
                    height: 90,
                    decoration: BoxDecoration(
                      color: colors.surfaceAlt,
                      borderRadius: AppRadius.cardRadius,
                      border: Border.all(color: colors.borderSubtle),
                    ),
                    child: _uploadingPhoto
                        ? const Center(child: CircularProgressIndicator())
                        : _newPhotoBytes != null
                            ? ClipRRect(
                                borderRadius: AppRadius.cardRadius,
                                child: Image.memory(_newPhotoBytes!, fit: BoxFit.cover, width: double.infinity),
                              )
                            : Center(
                                child: Column(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Icon(Icons.add_a_photo_outlined, color: colors.textMuted),
                                    const SizedBox(height: 4),
                                    Text(
                                      widget.existing?.hasImage == true ? 'استبدال الصورة' : 'إضافة صورة',
                                      style: AppTextStyles.caption.copyWith(color: colors.textMuted),
                                    ),
                                  ],
                                ),
                              ),
                  ),
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              KbAnchor(
                id: 'coworking.resource_sheet.name_field',
                child: TextField(
                  controller: _nameController,
                  decoration: const InputDecoration(isDense: true, hintText: 'اسم المورد (مثال: كرسي 1)'),
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              KbAnchor(
                id: 'coworking.resource_sheet.description_field',
                child: TextField(
                  controller: _descriptionController,
                  maxLines: 2,
                  decoration: const InputDecoration(isDense: true, hintText: 'وصف مختصر (اختياري)'),
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              KbAnchor(
                id: 'coworking.resource_sheet.price_field',
                child: TextField(
                  controller: _priceController,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(isDense: true, hintText: 'السعر بالساعة (ر.س)'),
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              Text('الفرع', style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary)),
              const SizedBox(height: AppSpacing.xs),
              KbAnchor(
                id: 'coworking.resource_sheet.branch_field',
                child: DropdownButtonFormField<String>(
                  initialValue: _branchId,
                  isExpanded: true,
                  decoration: const InputDecoration(isDense: true),
                  items: [
                    const DropdownMenuItem(value: '', child: Text('بدون فرع (يظهر لكل الفروع)')),
                    for (final b in widget.branches) DropdownMenuItem(value: b.id, child: Text(b.name)),
                  ],
                  onChanged: (v) => setState(() => _branchId = v ?? ''),
                ),
              ),
              if (_isEdit) ...[
                const SizedBox(height: AppSpacing.lg),
                Text('أوقات التوفر', style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary)),
                const SizedBox(height: AppSpacing.xs),
                for (var day = 0; day < 7; day++) _dayRow(day),
                const SizedBox(height: AppSpacing.md),
                KbAnchor(
                  id: 'coworking.resource_sheet.active_toggle',
                  child: SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('نشط', style: AppTextStyles.bodyMedium),
                    value: _active,
                    onChanged: (v) => setState(() => _active = v),
                  ),
                ),
              ],
              if (_error != null) ...[
                const SizedBox(height: AppSpacing.sm),
                AppAlert(type: AlertType.error, message: _error!),
              ],
              const SizedBox(height: AppSpacing.lg),
              KbAnchor(
                id: 'coworking.resource_sheet.submit',
                child: SizedBox(
                  width: double.infinity,
                  child: PrimaryButton(text: 'حفظ', isLoading: _saving, onPressed: _saving ? null : _submit),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _dayRow(int day) {
    final colors = context.appColors;
    final window = _weekly[day];
    final open = window != null;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          SizedBox(width: 70, child: Text(_dayLabels[day], style: AppTextStyles.bodySmall)),
          Switch(
            value: open,
            onChanged: (v) => setState(() {
              if (v) {
                _weekly[day] = const CoworkingWindow(startMinute: 9 * 60, endMinute: 17 * 60);
              } else {
                _weekly.remove(day);
              }
            }),
          ),
          if (open) ...[
            Expanded(
              child: OutlinedButton(
                onPressed: () => _pickTime(day, isStart: true),
                child: Text(_fmtMinute(window.startMinute)),
              ),
            ),
            const SizedBox(width: 6),
            const Text('—'),
            const SizedBox(width: 6),
            Expanded(
              child: OutlinedButton(
                onPressed: () => _pickTime(day, isStart: false),
                child: Text(_fmtMinute(window.endMinute)),
              ),
            ),
          ] else
            Expanded(
              child: Text('مغلق', textAlign: TextAlign.end,
                  style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
            ),
        ],
      ),
    );
  }

  // SAME REAL DOOR `booking_settings_sheet.dart`'s own weekly-hours editor already uses —
  // `pickTimeSheet`, never a hardcoded default a shop can't actually change.
  Future<void> _pickTime(int day, {required bool isStart}) async {
    final current = _weekly[day]!;
    final initial = TimeOfDay(
        hour: (isStart ? current.startMinute : current.endMinute) ~/ 60,
        minute: (isStart ? current.startMinute : current.endMinute) % 60);
    final picked = await pickTimeSheet(context, initial: initial);
    if (picked == null) return;
    final minutes = picked.hour * 60 + picked.minute;
    setState(() {
      _weekly[day] = isStart
          ? CoworkingWindow(startMinute: minutes, endMinute: current.endMinute)
          : CoworkingWindow(startMinute: current.startMinute, endMinute: minutes);
    });
  }

  String _fmtMinute(int minute) {
    final h = (minute ~/ 60).toString().padLeft(2, '0');
    final m = (minute % 60).toString().padLeft(2, '0');
    return '$h:$m';
  }
}
