import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/services/whatsapp_assistant_service.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_back_button.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

/// «المساعد الذكي عبر واتساب» — a FRESH design, never a port of the console's own gold/VIP
/// `WhatsAppAssistant.tsx` (the owner's own instruction, 2026-09-24: different layout entirely,
/// a WhatsApp-brand identity instead). Same four real doors that screen's cards already call
/// (`AiToggleCard`/`AiNotesCard`/`MsgWordLimitCard`/`WhatsAppAutoRegisterCard`), zero backend work.
///
/// NO RECEIPT NUMBERS HERE, DELIBERATELY (the owner's own call, same pass) — the console shows
/// conversations/AI-bookings/wallet-credit-remaining alongside these controls; none of that is
/// mirrored on mobile. Meta now runs the AI directly, so a manually-metered usage number is a
/// stale concept from before that shift, not something this screen resurrects.
class WhatsappAssistantScreen extends StatefulWidget {
  const WhatsappAssistantScreen({super.key});

  @override
  State<WhatsappAssistantScreen> createState() => _WhatsappAssistantScreenState();
}

/// WhatsApp's own brand green, scoped to this screen only — same "a VIP app gets its own accent,
/// never the platform's shared one" precedent apps_store_screen.dart's gold sets for بوت خدمة
/// العملاء الذكي.
const _kWaGreen = Color(0xFF25D366);
const _kWaGreenDark = Color(0xFF075E54);

class _WhatsappAssistantScreenState extends State<WhatsappAssistantScreen> {
  late final _service =
      WhatsappAssistantService(apiClient: context.read<AuthProvider>().apiClient);

  bool? _aiEnabled;
  bool _aiEnabledLoaded = false;
  String? _notes;
  bool _notesLoaded = false;
  int? _wordLimit;
  bool _wordLimitLoaded = false;
  bool? _autoRegister;
  bool _autoRegisterLoaded = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final results = await Future.wait([
      _service.fetchAiEnabled(),
      _service.fetchAiNotes(),
      _service.fetchWordLimit(),
      _service.fetchAutoRegister(),
    ]);
    if (!mounted) return;
    setState(() {
      _aiEnabled = results[0] as bool?;
      _aiEnabledLoaded = true;
      _notes = results[1] as String?;
      _notesLoaded = true;
      _wordLimit = results[2] as int?;
      _wordLimitLoaded = true;
      _autoRegister = results[3] as bool?;
      _autoRegisterLoaded = true;
    });
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return KbAnchor(
      id: 'whatsapp-assistant',
      child: Scaffold(
        backgroundColor: AppColors.surface0,
        body: SafeArea(
          child: RefreshIndicator(
            onRefresh: _load,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(
                  AppSpacing.lg, AppSpacing.md, AppSpacing.lg, AppSpacing.xxl),
              children: [
                Row(
                  children: [
                    AppBackButton(onPressed: () => Navigator.of(context).maybePop()),
                  ],
                ),
                const SizedBox(height: AppSpacing.sm),
                _Header(s: s),
                const SizedBox(height: AppSpacing.lg),
                if (!_aiEnabledLoaded)
                  const Padding(
                    padding: EdgeInsets.only(top: AppSpacing.xl),
                    child: Center(child: AppLoadingIndicator()),
                  )
                else if (_aiEnabled == null)
                  EmptyState(
                    icon: Icons.cloud_off_rounded,
                    title: s.whatsappAssistantLoadFailed,
                    actionText: s.retry,
                    onAction: _load,
                  )
                else ...[
                  KbAnchor(
                    id: 'whatsapp-assistant.toggle',
                    child: _ToggleCard(
                    icon: Icons.bolt_rounded,
                    title: s.whatsappAssistantToggleTitle,
                    desc: s.whatsappAssistantToggleDesc,
                    value: _aiEnabled == true,
                    onChanged: (next) => _confirmToggle(
                      title: next
                          ? s.whatsappAssistantToggleConfirmEnableTitle
                          : s.whatsappAssistantToggleConfirmDisableTitle,
                      body: next
                          ? s.whatsappAssistantToggleConfirmEnableBody
                          : s.whatsappAssistantToggleConfirmDisableBody,
                      danger: !next,
                      onConfirm: () async {
                        final ok = await _service.setAiEnabled(next);
                        if (ok && mounted) setState(() => _aiEnabled = next);
                        return ok;
                      },
                    ),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  if (_notesLoaded && _notes != null)
                    _NotesCard(s: s, initial: _notes!, service: _service),
                  if (_notesLoaded && _notes != null) const SizedBox(height: AppSpacing.md),
                  if (_wordLimitLoaded && _wordLimit != null)
                    _WordLimitCard(s: s, initial: _wordLimit!, service: _service),
                  if (_wordLimitLoaded && _wordLimit != null) const SizedBox(height: AppSpacing.md),
                  if (_autoRegisterLoaded && _autoRegister != null)
                    KbAnchor(
                      id: 'whatsapp-assistant.auto_register_toggle',
                      child: _ToggleCard(
                      icon: Icons.person_add_alt_1_rounded,
                      title: s.whatsappAssistantAutoRegisterTitle,
                      desc: s.whatsappAssistantAutoRegisterDesc,
                      value: _autoRegister == true,
                      onChanged: (next) => _confirmToggle(
                        title: next
                            ? s.whatsappAssistantAutoRegisterConfirmEnableTitle
                            : s.whatsappAssistantAutoRegisterConfirmDisableTitle,
                        body: next
                            ? s.whatsappAssistantAutoRegisterConfirmEnableBody
                            : s.whatsappAssistantAutoRegisterConfirmDisableBody,
                        danger: next,
                        onConfirm: () async {
                          final ok = await _service.setAutoRegister(next);
                          if (ok && mounted) setState(() => _autoRegister = next);
                          return ok;
                        },
                      ),
                      ),
                    ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _confirmToggle({
    required String title,
    required String body,
    required bool danger,
    required Future<bool> Function() onConfirm,
  }) async {
    final s = S.of(context)!;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(title),
        content: Text(body),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: Text(s.cancel)),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: Text(s.whatsappAssistantConfirm,
                style: TextStyle(color: danger ? AppColors.danger : _kWaGreenDark)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await onConfirm();
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.s});
  final S s;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft, end: Alignment.bottomRight,
          colors: [_kWaGreenDark, _kWaGreen],
        ),
        borderRadius: AppRadius.cardRadius,
      ),
      child: Row(
        children: [
          Container(
            width: 52, height: 52,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: Colors.white.withValues(alpha: 0.18),
            ),
            alignment: Alignment.center,
            child: const Icon(Icons.chat_bubble_rounded, color: Colors.white, size: 26),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(s.whatsappAssistantTitle,
                    style: AppTextStyles.headlineSmall.copyWith(color: Colors.white)),
                const SizedBox(height: 2),
                Text(s.whatsappAssistantSubtitle,
                    style: AppTextStyles.bodySmall.copyWith(color: Colors.white.withValues(alpha: 0.85))),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ToggleCard extends StatelessWidget {
  const _ToggleCard({
    required this.icon, required this.title, required this.desc,
    required this.value, required this.onChanged,
  });
  final IconData icon;
  final String title;
  final String desc;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Container(
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: BoxDecoration(
          color: colors.surface,
          border: Border.all(color: colors.borderSubtle),
          borderRadius: AppRadius.standardRadius,
        ),
        child: Row(
          children: [
            Container(
              width: 40, height: 40,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: (value ? _kWaGreen : colors.textMuted).withValues(alpha: 0.14),
              ),
              alignment: Alignment.center,
              child: Icon(icon, size: 19, color: value ? _kWaGreenDark : colors.textMuted),
            ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 2),
                  Text(desc, style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
                ],
              ),
            ),
            Switch(value: value, onChanged: onChanged, activeThumbColor: _kWaGreenDark),
          ],
        ),
    );
  }
}

class _NotesCard extends StatefulWidget {
  const _NotesCard({required this.s, required this.initial, required this.service});
  final S s;
  final String initial;
  final WhatsappAssistantService service;

  @override
  State<_NotesCard> createState() => _NotesCardState();
}

const _kAiNotesMax = 2000;

class _NotesCardState extends State<_NotesCard> {
  late final _controller = TextEditingController(text: widget.initial);
  late String _saved = widget.initial;
  bool _busy = false;
  String _error = '';

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  bool get _dirty => _controller.text != _saved;
  bool get _overCap => _controller.text.length > _kAiNotesMax;

  Future<void> _save() async {
    if (_overCap || _busy) return;
    setState(() { _busy = true; _error = ''; });
    final out = await widget.service.saveAiNotes(_controller.text);
    if (!mounted) return;
    setState(() {
      _busy = false;
      if (out != null) {
        _saved = out;
        _controller.text = out;
      } else {
        _error = widget.s.whatsappAssistantSaveFailed;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.s;
    final colors = context.appColors;
    return KbAnchor(
      id: 'whatsapp-assistant.notes_field',
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: BoxDecoration(
          color: colors.surface,
          border: Border.all(color: colors.borderSubtle),
          borderRadius: AppRadius.standardRadius,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(s.whatsappAssistantNotesTitle, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 2),
            Text(s.whatsappAssistantNotesDesc, style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
            const SizedBox(height: AppSpacing.sm),
            TextField(
              controller: _controller,
              maxLines: 5,
              onChanged: (_) => setState(() {}),
              decoration: InputDecoration(
                filled: true, fillColor: colors.surfaceAlt,
                border: OutlineInputBorder(borderRadius: AppRadius.standardRadius, borderSide: BorderSide.none),
              ),
            ),
            const SizedBox(height: 4),
            Text('${_controller.text.length} / $_kAiNotesMax',
                style: AppTextStyles.caption.copyWith(color: _overCap ? AppColors.danger : colors.textMuted)),
            if (_error.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(_error, style: AppTextStyles.caption.copyWith(color: AppColors.danger)),
            ],
            const SizedBox(height: AppSpacing.sm),
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: FilledButton(
                onPressed: (!_dirty || _overCap || _busy) ? null : _save,
                style: FilledButton.styleFrom(backgroundColor: _kWaGreenDark),
                child: _busy
                    ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : Text(s.servicesSave),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

const _kWordLimitMin = 20;
const _kWordLimitMax = 300;

class _WordLimitCard extends StatefulWidget {
  const _WordLimitCard({required this.s, required this.initial, required this.service});
  final S s;
  final int initial;
  final WhatsappAssistantService service;

  @override
  State<_WordLimitCard> createState() => _WordLimitCardState();
}

class _WordLimitCardState extends State<_WordLimitCard> {
  late int _value = widget.initial;
  late int _saved = widget.initial;
  bool _busy = false;
  String _error = '';

  Future<void> _save() async {
    if (_busy) return;
    setState(() { _busy = true; _error = ''; });
    final out = await widget.service.saveWordLimit(_value);
    if (!mounted) return;
    setState(() {
      _busy = false;
      if (out != null) {
        _saved = out;
        _value = out;
      } else {
        _error = widget.s.whatsappAssistantSaveFailed;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.s;
    final colors = context.appColors;
    return KbAnchor(
      id: 'whatsapp-assistant.word_limit_field',
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: BoxDecoration(
          color: colors.surface,
          border: Border.all(color: colors.borderSubtle),
          borderRadius: AppRadius.standardRadius,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(s.whatsappAssistantWordLimitTitle, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 2),
            Text(s.whatsappAssistantWordLimitDesc, style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
            const SizedBox(height: AppSpacing.sm),
            Row(
              children: [
                IconButton(
                  onPressed: _value > _kWordLimitMin ? () => setState(() => _value -= 10) : null,
                  icon: const Icon(Icons.remove_circle_outline_rounded),
                ),
                SizedBox(
                  width: 70,
                  child: Text('$_value', textAlign: TextAlign.center, style: AppTextStyles.headlineSmall),
                ),
                IconButton(
                  onPressed: _value < _kWordLimitMax ? () => setState(() => _value += 10) : null,
                  icon: const Icon(Icons.add_circle_outline_rounded),
                ),
                const Spacer(),
                FilledButton(
                  onPressed: (_value == _saved || _busy) ? null : _save,
                  style: FilledButton.styleFrom(backgroundColor: _kWaGreenDark),
                  child: _busy
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : Text(s.servicesSave),
                ),
              ],
            ),
            if (_error.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(_error, style: AppTextStyles.caption.copyWith(color: AppColors.danger)),
            ],
          ],
        ),
      ),
    );
  }
}
