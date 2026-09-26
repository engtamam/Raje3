import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
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
/// A CHIP INSERTS AT THE REAL CARET, mid-sentence, not just appended — the same freedom the
/// console's own `contenteditable` port gives. The trick: a chip's own label text is inserted into
/// the field LITERALLY (so the string the caret walks and the text he reads are the exact same
/// characters — no cursor-math hack), wrapped in a pair of zero-width-space markers (`U+200B`,
/// invisible, never typed by a human by accident) so the save step can tell "the shop's own words"
/// apart from "a chip's label that happens to read the same" without ambiguity. A custom
/// [TextEditingController] restyles exactly the text between a marker pair as a highlighted chip,
/// live, while he keeps typing around it.
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

const String _kMarker = '​';
final RegExp _kChipPattern = RegExp('$_kMarker(.*?)$_kMarker');

/// Turns an already-saved `{{n}}`-numbered body into the editor's own marker-wrapped display
/// text, so re-editing opens on what was actually written rather than a blank box. A number with
/// no slot behind it (a template we no longer understand) is kept as literal text rather than
/// silently dropped — same rule the console's own `toHtml` keeps.
String _toDisplayText(String body, List<Slot> slots) {
  return body.replaceAllMapped(RegExp(r'\{\{(\d+)\}\}'), (m) {
    final n = int.parse(m.group(1)!);
    final slot = n >= 1 && n <= slots.length ? slots[n - 1] : null;
    return slot != null ? '$_kMarker${slot.label}$_kMarker' : m.group(0)!;
  });
}

/// The other direction — display text back into WhatsApp's own `{{n}}` numbering, generated from
/// POSITION, never typed by the shop (a gap or a wrong number is impossible this way).
({String body, List<String> fills}) _serialize(String displayText, List<Slot> slots) {
  final byLabel = {for (final s in slots) s.label: s};
  final fills = <String>[];
  final body = displayText.replaceAllMapped(_kChipPattern, (m) {
    final slot = byLabel[m.group(1)];
    if (slot == null) return m.group(1) ?? ''; // an orphaned marker: keep the plain words
    fills.add(slot.id);
    return '{{${fills.length}}}';
  });
  return (body: body.trim(), fills: fills);
}

/// What the customer would actually read — the same substitution the preview does, done live.
String _sample(String displayText, List<Slot> slots, Mandatory? mandatory) {
  final byLabel = {for (final s in slots) s.label: s};
  var shown = displayText.replaceAllMapped(_kChipPattern, (m) {
    final slot = byLabel[m.group(1)];
    if (slot == null) return m.group(1) ?? '';
    return slot.sample.isNotEmpty ? slot.sample : slot.label;
  });
  if (mandatory != null) {
    shown = '$shown ${mandatory.sample.isNotEmpty ? mandatory.sample : mandatory.label}';
  }
  return shown;
}

/// Restyles exactly the text between a marker pair as a highlighted chip — a real, single string
/// of real characters, so the caret's own position math is never touched; only the paint colour
/// changes per run.
class _ChipEditingController extends TextEditingController {
  _ChipEditingController({super.text});

  @override
  TextSpan buildTextSpan({required BuildContext context, TextStyle? style, required bool withComposing}) {
    final chipStyle = style?.copyWith(
      backgroundColor: context.isDark ? AppDarkColors.accentSoft : AppColors.accentSoft,
      color: context.isDark ? AppDarkColors.accentOnSoft : AppColors.accentOnSoft,
      fontWeight: FontWeight.w600,
    );
    final spans = <InlineSpan>[];
    var last = 0;
    for (final m in _kChipPattern.allMatches(text)) {
      if (m.start > last) spans.add(TextSpan(text: text.substring(last, m.start), style: style));
      spans.add(TextSpan(text: m.group(1), style: chipStyle));
      last = m.end;
    }
    if (last < text.length) spans.add(TextSpan(text: text.substring(last), style: style));
    return TextSpan(style: style, children: spans);
  }
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
  late final _ChipEditingController _controller;
  bool _saving = false;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _service = MessagesService(apiClient: context.read<AuthProvider>().apiClient);
    _controller = _ChipEditingController(text: _toDisplayText(widget.initialBody, widget.slots));
    _controller.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  /// Inserts AT THE REAL CARET — where he was actually typing, not always the end. Falls back to
  /// the end only when the field has never been focused yet (a fresh, empty selection).
  void _insertChip(Slot slot) {
    final chip = '$_kMarker${slot.label}$_kMarker';
    final sel = _controller.selection;
    final at = sel.isValid ? sel.start : _controller.text.length;
    final end = sel.isValid ? sel.end : _controller.text.length;
    final newText = _controller.text.replaceRange(at, end, chip);
    _controller.value = _controller.value.copyWith(
      text: newText,
      selection: TextSelection.collapsed(offset: at + chip.length),
      composing: TextRange.empty,
    );
  }

  Future<void> _save() async {
    final (:body, :fills) = _serialize(_controller.text, widget.slots);
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
    final sample = _sample(_controller.text, widget.slots, widget.mandatory);
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
              // reason registry exists to prevent). Inserts at wherever he is actually typing.
              Wrap(spacing: 6, runSpacing: 6, children: [
                for (final s in widget.slots)
                  ActionChip(
                    avatar: const Icon(Icons.add, size: 14),
                    label: Text(s.label),
                    onPressed: () => _insertChip(s),
                  ),
              ]),
              const SizedBox(height: AppSpacing.sm),
              // ONE REAL TEXT FIELD — chips are the exact same characters he can see and the
              // caret walks, only restyled where a marker pair wraps them (`_ChipEditingController`).
              TextField(
                controller: _controller,
                maxLines: 4,
                minLines: 3,
                inputFormatters: [
                  // A HUMAN NEVER TYPES A ZERO-WIDTH SPACE — refusing it here means the marker
                  // alphabet stays exclusively ours, so a chip run can never be forged by typing.
                  FilteringTextInputFormatter.deny(_kMarker),
                ],
                style: const TextStyle(fontFamily: 'Cairo', fontSize: 14, height: 1.5),
                decoration: InputDecoration(
                  filled: true,
                  fillColor: colors.inputFill,
                  hintText: ct(context, 'textEditorContinueHint'),
                  border: OutlineInputBorder(borderRadius: AppRadius.standardRadius, borderSide: BorderSide(color: colors.borderSubtle)),
                ),
              ),
              // THE ONE BLANK HE DOES NOT CHOOSE, shown rather than hidden — an owner who does
              // not see it in his text believes it is not in his text.
              if (widget.mandatory != null) ...[
                const SizedBox(height: AppSpacing.sm),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: 6),
                  decoration: BoxDecoration(
                    border: Border.all(color: colors.borderSubtle),
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
                  sample.isEmpty ? '…' : sample,
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
