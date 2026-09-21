import 'dart:async';
import 'dart:typed_data';

import 'package:flutter_litert/flutter_litert.dart';
import 'package:mic_stream/mic_stream.dart';
import 'package:raje3_mobile/core/wakeword/micro_frontend.dart';
import 'package:raje3_mobile/core/wakeword/wake_word_model.dart';

/// The real device: `mic_stream` for raw 16kHz mono PCM, [MicroFrontend] to turn it into the
/// same 40-channel features microWakeWord trained on, and `flutter_litert`'s classic
/// `Interpreter` to run the trained classifier (`assets/wakeword/raje_wakeword.tflite`) — see
/// this app's own wake-word training notes for the model's real, verified tensor signature:
/// input `[1, 3, 40]` int8 (scale 0.10196078568696976, zero_point -128), output `[1, 1]` uint8
/// (scale 0.00390625, zero_point 0). The model's own internal streaming state is handled by the
/// runtime automatically as long as the SAME [Interpreter] instance is reused call after call in
/// order — never recreated per inference.
///
/// A NEW MODEL RUN EVERY 3 FEATURE FRAMES (30ms of audio) — `stride: 3` in the real training
/// config, matching the fixed `[1, 3, 40]` input shape exactly; a partial group of frames at the
/// end of a listening session is simply dropped, never padded or guessed.
///
/// FAILS CLOSED ON ANYTHING UNEXPECTED: a denied microphone permission, a missing/corrupt model
/// asset, or an unsupported platform all resolve [isAvailable] to `false` rather than throwing —
/// same contract [PlatformSpeechInputModel] already holds.
///
/// DOES NOT WATCH APP LIFECYCLE ITSELF — a caller (the UI layer already owns a
/// WidgetsBindingObserver for other reasons) is responsible for calling [stop] when the app is
/// backgrounded; this port only ever listens for as long as it is told to, deliberately, so it
/// never silently keeps the microphone open once nothing owns the decision anymore.
class PlatformWakeWordModel implements WakeWordModel {
  static const String _assetPath = 'assets/wakeword/raje_wakeword.tflite';

  // From the real trained model's own tensor signature — verified via a Python TFLite
  // Interpreter against the exported .tflite, never guessed.
  static const double _inputScale = 0.10196078568696976;
  static const int _inputZeroPoint = -128;
  static const double _outputScale = 0.00390625;
  static const int _outputZeroPoint = 0;
  static const int _framesPerInference = 3;

  // From the model's own ROC evaluation on held-out data (see this project's wake-word training
  // notes) — the operating point chosen to favor few false accepts over a slightly higher miss
  // rate, appropriate for a voice trigger a user can always fall back to tapping instead.
  static const double _detectionThreshold = 0.90;

  Interpreter? _interpreter;
  final MicroFrontend _frontend = MicroFrontend();
  StreamSubscription<Uint8List>? _micSubscription;
  final List<Float64List> _pendingFrames = [];
  bool _listening = false;
  bool? _availableCache;

  @override
  String get driver => 'platform';

  @override
  bool get isListening => _listening;

  @override
  Future<bool> isAvailable() async {
    if (_availableCache != null) return _availableCache!;
    try {
      _interpreter ??= await Interpreter.fromAsset(_assetPath);
      _availableCache = true;
    } catch (_) {
      // Missing/corrupt asset, unsupported platform, or any other load failure — fail closed,
      // same contract every other port's isAvailable() holds.
      _availableCache = false;
    }
    return _availableCache!;
  }

  @override
  Future<void> start({required void Function() onDetected}) async {
    if (_listening) return;
    if (!await isAvailable()) return;

    _frontend.reset();
    _pendingFrames.clear();
    _listening = true;

    late final Stream<Uint8List> mic;
    try {
      mic = MicStream.microphone(
        sampleRate: MicroFrontend.sampleRate,
        channelConfig: ChannelConfig.CHANNEL_IN_MONO,
        audioFormat: AudioFormat.ENCODING_PCM_16BIT,
      );
    } catch (_) {
      _listening = false;
      return;
    }

    _micSubscription = mic.listen(
      (bytes) => _onAudioChunk(bytes, onDetected),
      onError: (_) => stop(),
      cancelOnError: true,
    );
  }

  void _onAudioChunk(Uint8List bytes, void Function() onDetected) {
    if (!_listening || _interpreter == null) return;
    // mic_stream's own bytes are little-endian 16-bit PCM pairs — reinterpret in place, no copy.
    final pcm16 = bytes.buffer.asInt16List(bytes.offsetInBytes, bytes.lengthInBytes ~/ 2);
    final frames = _frontend.process(pcm16);
    if (frames.isEmpty) return;
    _pendingFrames.addAll(frames);

    while (_pendingFrames.length >= _framesPerInference) {
      final group = _pendingFrames.sublist(0, _framesPerInference);
      _pendingFrames.removeRange(0, _framesPerInference);
      final score = _runInference(group);
      if (score >= _detectionThreshold) {
        onDetected();
        stop();
        return;
      }
    }
  }

  double _runInference(List<Float64List> frames) {
    final interpreter = _interpreter!;
    final input = List.generate(
      1,
      (_) => List.generate(
        _framesPerInference,
        (f) => List.generate(
          MicroFrontend.numChannels,
          (c) => _quantizeInput(frames[f][c]),
        ),
      ),
    );
    final output = [
      [0]
    ];
    interpreter.run(input, output);
    final raw = output[0][0];
    return (raw - _outputZeroPoint) * _outputScale;
  }

  static int _quantizeInput(double value) {
    final q = (value / _inputScale).round() + _inputZeroPoint;
    return q.clamp(-128, 127);
  }

  @override
  Future<void> stop() async {
    _listening = false;
    await _micSubscription?.cancel();
    _micSubscription = null;
    _pendingFrames.clear();
  }

  @override
  Future<void> dispose() async {
    await stop();
    _interpreter?.close();
    _interpreter = null;
  }
}
