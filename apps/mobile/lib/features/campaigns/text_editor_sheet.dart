import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/services/messages_service.dart';
import 'package:raje3_mobile/models/messages_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/features/campaigns/campaigns_i18n.dart';

/// Writing his own wording for one message — with blanks he cannot get wrong.
///
/// THE PROBLEM EVERY TEMPLATE EDITOR HAS (TextEditor.tsx's own header note, ported whole): WhatsApp
/// numbers its blanks and names nothing — the body that leaves is «أهلاً {{1}}، حان وقت {{2}}». An
/// owner asked to type that will mistype it, leave a gap, or ask for a blank this message has no
/// value for. So he never types a number: he taps a named chip and the numbering is generated from
/// the order the chips sit in when he saves.
///
/// SIMPLIFIED FROM THE CONSOLE'S OWN CONTENTEDITABLE PORT (documented, not hidden): a chip can only
/// be appended after whatever he has already typed, never inserted mid-sentence at an arbitrary
/// caret position — Flutter has no inline-widget-inside-a-text-field primitive the way a browser's
/// `contenteditable` does. Re-ordering a message still works; it just means typing the words before
/// a blank BEFORE tapping that blank's chip, not tapping it and going back to insert words earlier.
Future<void> showTextEditorSheet(
  BuildContext context, {
  required String reasonId,
  required String label,
  required List<Slot> slots,
  Mandatory? mandatory,
  String initialBody = '',
  String replaces = '',
  required VoidCallback onSaved,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => _TextEditorSheet(
      reasonId: reasonId, label: label, slots: slots, mandatory: mandatory,
      initialBody: initialBody, replaces: replaces, onSaved: onSaved,
    ),
  );
}

/// One piece of the composed message: either a literal run of text, or a named chip.
class _Part {
  final String? text;
  final Slot? slot;
  const _Part.text(this.text) : slot = null;
  const _Part.chip(this.slot) : text = null;
  bool get isChip => slot != null;
}

/// Splits an already-saved `{{n}}`-numbered body back into parts, so re-editing a text opens on
/// what was actually written rather than a blank box — the other direction from [_serialize].
List<_Part> _parse(String body, List<Slot> slots) {
  final parts = <_Part>[];
  final pattern = RegExp(r'\{\{(\d+)\}\}');
  var last = 0;
  for (final m in pattern.allMatches(body)) {
    if (m.start > last) parts.add(_Part.text(body.substring(last, m.start)));
    final n = int.parse(m.group(1)!);
    final slot = n >= 1 && n <= slots.length ? slots[n - 1] : null;
    // A number with no slot behind it (a template we no longer understand) is kept as literal
    // text rather than silently dropped — same rule the console's own `toHtml` keeps.
    parts.add(slot != null ? _Part.chip(slot) : _Part.text(m.group(0)!));
    last = m.end;
  }
  if (last < body.length) parts.add(_Part.text(body.substring(last)));
  return parts;
}

/// The other direction — parts back into WhatsApp's own `{{n}}` numbering, generated from
/// POSITION, never typed by the shop (a gap or a wrong number is impossible this way).
({String body, List<String> fills}) _serialize(List<_Part> parts) {
  final fills = <String>[];
  final buf = StringBuffer();
  for (final p in parts) {
    if (p.isChip) {
      fills.add(p.slot!.id);
      buf.write('{{${fills.length}}}');
    } else {
      buf.write(p.text ?? '');
    }
  }
  return (body: buf.toString().trim(), fills: fills);
}

/// What the customer would actually read — the same substitution the preview does, done live.
String _sample(List<_Part> parts, Mandatory? mandatory) {
  final buf = StringBuffer();
  for (final p in parts) {
    buf.write(p.isChip ? (p.slot!.sample.isNotEmpty ? p.slot!.sample : p.slot!.label) : (p.text ?? ''));
  }
  var shown = buf.toString();
  if (mandatory != null) {
    shown = '$shown ${mandatory.sample.isNotEmpty ? mandatory.sample : mandatory.label}';
  }
  return shown;
}

class _TextEditorSheet extends StatefulWidget {
  const _TextEditorSheet({
    required this.reasonId,
    required this.label,
    required this.slots,
    required this.mandatory,
    required this.initialBody,
    required this.replaces,
    required this.onSaved,
  });

  final String reasonId;
  final String label;
  final List<Slot> slots;
  final Mandatory? mandatory;
  final String initialBody;
  final String replaces;
  final VoidCallback onSaved;

  @override
  State<_TextEditorSheet> createState() => _TextEditorSheetState();
}

class _TextEditorSheetState extends State<_TextEditorSheet> {
  late final MessagesService _service;
  late List<_Part> _parts;
  final _trailingController = TextEditingController();
  bool _saving = false;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _service = MessagesService(apiClient: context.read<AuthProvider>().apiClient);
    _parts = _parse(widget.initialBody, widget.slots);
    // THE TRAILING TEXT IS ITS OWN FIELD, not the last item of `_parts` — a `TextField` needs a
    // stable controller to type into; folding it back into `_parts` happens once, at save/insert.
    if (_parts.isNotEmpty && !_parts.last.isChip) {
      _trailingController.text = _parts.removeLast().text ?? '';
    }
  }

  @override
  void dispose() {
    _trailingController.dispose();
    super.dispose();
  }

  List<_Part> get _allParts => [
        ..._parts,
        if (_trailingController.text.isNotEmpty) _Part.text(_trailingController.text),
      ];

  void _insertChip(Slot slot) {
    setState(() {
      if (_trailingController.text.isNotEmpty) {
        _parts.add(_Part.text(_trailingController.text));
        _trailingController.clear();
      }
      _parts.add(_Part.chip(slot));
    });
  }

  Future<void> _save() async {
    final (:body, :fills) = _serialize(_allParts);
    if (body.trim().isEmpty) {
      setState(() => _error = ct(context, 'textEditorEmptyError'));
      return;
    }
    setState(() {
      _saving = true;
      _error = '';
    });
    final refusal = await _service.writeTemplate(
      reasonId: widget.reasonId, body: body, fills: fills, replaces: widget.replaces,
    );
    if (!mounted) return;
    if (refusal == null) {
      widget.onSaved();
      Navigator.of(context).pop();
      return;
    }
    setState(() {
      _saving = false;
      _error = refusal;
    });
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Container(
      constraints: BoxConstraints(maxHeight: appSheetMaxHeight(context)),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
      ),
      padding: const EdgeInsets.all(AppSpacing.md),
      child: SafeArea(
        top: false,
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(children: [
                Expanded(child: Text(ct(context, 'textEditorTitle', {'label': widget.label}), style: AppTextStyles.headlineSmall)),
                IconButton(icon: const Icon(Icons.close), onPressed: () => Navigator.of(context).pop()),
              ]),
              Text(ct(context, 'textEditorSubtitle'), style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary)),
              const SizedBox(height: AppSpacing.md),
              // THE PALETTE — only what THIS message can fill (never a blank this message has no
              // value for; a wording that then renders nothing is exactly the failure the
              // reason registry exists to prevent).
              Wrap(spacing: 6, runSpacing: 6, children: [
                for (final s in widget.slots)
                  ActionChip(
                    avatar: const Icon(Icons.add, size: 14),
                    label: Text(s.label),
                    onPressed: () => _insertChip(s),
                  ),
              ]),
              const SizedBox(height: AppSpacing.sm),
              // THE COMPOSED MESSAGE SO FAR — chips as real chips, never raw `{{1}}`.
              if (_parts.isNotEmpty)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(AppSpacing.sm),
                  decoration: BoxDecoration(color: colors.surfaceAlt, borderRadius: AppRadius.standardRadius),
                  child: Wrap(spacing: 4, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
                    for (final p in _parts)
                      p.isChip
                          ? Chip(label: Text(p.slot!.label), visualDensity: VisualDensity.compact)
                          : Text(p.text ?? '', style: AppTextStyles.bodySmall),
                  ]),
                ),
              const SizedBox(height: AppSpacing.sm),
              AppTextField(
                controller: _trailingController,
                maxLines: 3,
                hintText: ct(context, 'textEditorContinueHint'),
                onChanged: (_) => setState(() {}),
              ),
              // THE ONE BLANK HE DOES NOT CHOOSE, shown rather than hidden — an owner who does
              // not see it in his text believes it is not in his text.
              if (widget.mandatory != null) ...[
                const SizedBox(height: AppSpacing.sm),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: 6),
                  decoration: BoxDecoration(
                    border: Border.all(color: colors.borderSubtle, style: BorderStyle.solid),
                    borderRadius: AppRadius.standardRadius,
                  ),
                  child: Row(children: [
                    Icon(Icons.lock_outline, size: 14, color: colors.textSecondary),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        '${ct(context, 'textEditorMandatoryLine')} ${widget.mandatory!.label} — ${widget.mandatory!.note}',
                        style: AppTextStyles.caption,
                      ),
                    ),
                  ]),
                ),
              ],
              const SizedBox(height: AppSpacing.md),
              Text(ct(context, 'textEditorPreviewTitle'), style: AppTextStyles.labelMedium),
              const SizedBox(height: AppSpacing.sm),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFDCF8C6),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Text(
                  _sample(_allParts, widget.mandatory).isEmpty ? '…' : _sample(_allParts, widget.mandatory),
                  style: const TextStyle(color: Color(0xFF111B21), fontSize: 14, height: 1.5, fontFamily: 'Cairo'),
                ),
              ),
              if (_error.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.sm),
                Text(_error, style: AppTextStyles.bodySmall.copyWith(color: context.isDark ? AppDarkColors.danger : AppColors.danger)),
              ],
              const SizedBox(height: AppSpacing.md),
              Row(children: [
                Expanded(child: Text(ct(context, 'textEditorApprovalNote'), style: AppTextStyles.caption)),
                const SizedBox(width: AppSpacing.sm),
                PrimaryButton(text: ct(context, 'textEditorSave'), isLoading: _saving, onPressed: _save, width: 120),
              ]),
            ],
          ),
        ),
      ),
    );
  }
}
