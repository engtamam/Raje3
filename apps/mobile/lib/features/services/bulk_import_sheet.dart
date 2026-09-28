import 'dart:convert';
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import 'package:raje3_mobile/core/services/services_catalogue_service.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';

/// «استيراد خدمات من ملف» — CSV only (see services_catalogue_service.dart's own note on why:
/// the server parses no file format itself, and a real .xlsx reader is a separate, heavier
/// dependency this pass does not add). Expected header row, any order, Latin column names:
/// name, price, duration_minutes, cycle_days, description — the same fields
/// `operations.create_service`/`update_service` already accept by hand, one row per service.
class BulkImportSheet extends StatefulWidget {
  const BulkImportSheet({super.key, required this.service});
  final ServicesCatalogueService service;

  @override
  State<BulkImportSheet> createState() => _BulkImportSheetState();
}

enum _Step { pick, preview, done }

class _BulkImportSheetState extends State<BulkImportSheet> {
  _Step _step = _Step.pick;
  String? _fileName;
  List<Map<String, dynamic>>? _rows;
  String? _error;
  bool _deactivateMissing = false;
  bool _importing = false;
  Map<String, int>? _result;

  Future<void> _pickFile() async {
    setState(() => _error = null);
    final result = await FilePicker.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['csv'],
    );
    if (result.isEmpty) return;
    final file = result.first;
    Uint8List? bytes;
    try {
      bytes = await file.readAsBytes();
    } catch (_) {
      bytes = null;
    }
    if (!mounted) return;
    if (bytes == null) {
      setState(() => _error = S.of(context)!.servicesImportReadFailed);
      return;
    }
    final s = S.of(context)!;
    try {
      final rows = _parseCsv(utf8.decode(bytes));
      if (!mounted) return;
      setState(() {
        _fileName = file.name;
        _rows = rows;
        _step = _Step.preview;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = s.servicesImportParseFailed);
    }
  }

  List<Map<String, dynamic>> _parseCsv(String text) {
    final lines = text
        .split(RegExp(r'\r\n|\n|\r'))
        .where((l) => l.trim().isNotEmpty)
        .toList();
    if (lines.isEmpty) return const [];
    final header = _splitCsvLine(lines.first).map((h) => h.trim().toLowerCase()).toList();
    final nameIdx = header.indexOf('name');
    if (nameIdx == -1) throw const FormatException('no name column');
    final priceIdx = header.indexOf('price');
    final durationIdx = header.indexOf('duration_minutes');
    final cycleIdx = header.indexOf('cycle_days');
    final descIdx = header.indexOf('description');
    final out = <Map<String, dynamic>>[];
    for (final line in lines.skip(1)) {
      final cells = _splitCsvLine(line);
      final name = nameIdx < cells.length ? cells[nameIdx].trim() : '';
      if (name.isEmpty) continue;
      final priceSar = priceIdx != -1 && priceIdx < cells.length
          ? double.tryParse(cells[priceIdx].trim())
          : null;
      out.add({
        'name': name,
        'price_minor': priceSar != null ? (priceSar * 100).round() : 0,
        'duration_minutes': durationIdx != -1 && durationIdx < cells.length
            ? int.tryParse(cells[durationIdx].trim()) ?? 0
            : 0,
        'cycle_days': cycleIdx != -1 && cycleIdx < cells.length
            ? int.tryParse(cells[cycleIdx].trim()) ?? 0
            : 0,
        'description': descIdx != -1 && descIdx < cells.length ? cells[descIdx].trim() : '',
      });
    }
    return out;
  }

  /// A minimal RFC4180 split — quoted fields (`"a, b"`) and doubled quotes (`""`) inside them,
  /// which is the one shape a real spreadsheet export actually produces for a description with a
  /// comma in it.
  List<String> _splitCsvLine(String line) {
    final out = <String>[];
    final buf = StringBuffer();
    var inQuotes = false;
    for (var i = 0; i < line.length; i++) {
      final ch = line[i];
      if (inQuotes) {
        if (ch == '"' && i + 1 < line.length && line[i + 1] == '"') {
          buf.write('"');
          i++;
        } else if (ch == '"') {
          inQuotes = false;
        } else {
          buf.write(ch);
        }
      } else if (ch == '"') {
        inQuotes = true;
      } else if (ch == ',') {
        out.add(buf.toString());
        buf.clear();
      } else {
        buf.write(ch);
      }
    }
    out.add(buf.toString());
    return out;
  }

  Future<void> _import() async {
    final s = S.of(context)!;
    setState(() {
      _importing = true;
      _error = null;
    });
    try {
      final result = await widget.service
          .bulkImportServices(_rows!, deactivateMissing: _deactivateMissing);
      if (!mounted) return;
      if (result == null) {
        setState(() {
          _importing = false;
          _error = s.servicesActionFailed;
        });
        return;
      }
      setState(() {
        _importing = false;
        _result = result;
        _step = _Step.done;
      });
    } on BulkImportRefusal catch (e) {
      if (!mounted) return;
      setState(() {
        _importing = false;
        _error = e.reason.isNotEmpty ? e.reason : s.servicesActionFailed;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: Container(
        padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xl),
        decoration: const BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(s.servicesImportTitle, style: AppTextStyles.headlineSmall),
            const SizedBox(height: 4),
            Text(s.servicesImportHint, style: AppTextStyles.bodySmall.copyWith(color: AppColors.textMuted)),
            const SizedBox(height: AppSpacing.lg),
            if (_step == _Step.pick) ...[
              OutlinedButton.icon(
                onPressed: _pickFile,
                icon: const Icon(Icons.upload_file_rounded),
                label: Text(s.servicesImportPickFile),
              ),
            ] else if (_step == _Step.preview) ...[
              Text(_fileName ?? '', style: AppTextStyles.bodySmall),
              const SizedBox(height: 4),
              Text(s.servicesImportRowCount(_rows!.length), style: AppTextStyles.bodyMedium),
              const SizedBox(height: AppSpacing.sm),
              SizedBox(
                height: 160,
                child: ListView.builder(
                  itemCount: _rows!.length,
                  itemBuilder: (context, i) => Text('• ${_rows![i]['name']}', style: AppTextStyles.caption),
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              Material(
                color: Colors.transparent,
                child: SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(s.servicesImportDeactivateMissing),
                  subtitle: Text(s.servicesImportDeactivateMissingHint,
                      style: AppTextStyles.caption.copyWith(color: AppColors.textMuted)),
                  value: _deactivateMissing,
                  onChanged: (v) => setState(() => _deactivateMissing = v),
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              PrimaryButton(
                text: _importing ? s.servicesSaving : s.servicesImportConfirm,
                isLoading: _importing,
                onPressed: _importing ? null : _import,
              ),
            ] else ...[
              const Icon(Icons.check_circle_rounded, color: AppColors.success, size: 40),
              const SizedBox(height: AppSpacing.sm),
              Text(
                s.servicesImportDone(
                    _result!['created']!, _result!['updated']!, _result!['reactivated']!),
                style: AppTextStyles.bodyMedium,
              ),
              const SizedBox(height: AppSpacing.lg),
              PrimaryButton(text: s.servicesImportClose, onPressed: () => Navigator.of(context).pop(true)),
            ],
            if (_error != null) ...[
              const SizedBox(height: AppSpacing.md),
              AppAlert(type: AlertType.error, message: _error!),
            ],
          ],
        ),
      ),
    );
  }
}
