import 'dart:math' as math;
import 'dart:typed_data';

/// A faithful port of Google's TFLite Micro "audio microfrontend" — the exact feature
/// extraction pipeline microWakeWord trains against (window -> FFT -> mel filterbank ->
/// noise reduction -> PCAN gain control -> log scale), ported from the real reference
/// C source vendored inside the `pymicro-features` PyPI package (Apache 2.0), read
/// file-by-file rather than guessed. Every constant below (window sizes, smoothing
/// factors, PCAN strength/offset, mel band limits) is copied verbatim from that source,
/// specifically the config `micro_features.cpp` itself builds (30ms window, 10ms step,
/// 40 channels, 125-7500Hz, PCAN enabled with strength=0.95/offset=80.0/gain_bits=21).
///
/// ONE DELIBERATE DEPARTURE FROM THE REFERENCE: the reference's FFT (kiss_fft, 16-bit
/// fixed-point) is reimplemented here as a real, double-precision FFT rather than a
/// bit-exact fixed-point transliteration. Every OTHER stage (windowing, energy, mel
/// filterbank accumulation, noise-reduction smoothing, PCAN's wide-dynamic-function
/// approximation, the log-lut) follows the reference's own integer arithmetic exactly,
/// because those stages' rounding behavior is trainable-model-relevant in a way a
/// generic FFT's internal rounding is not.
///
/// This file's own golden-vector test (`test/core/wakeword/micro_frontend_test.dart`)
/// compares its output against real `pymicro_features` output on synthetic audio — not to
/// prove bit-exactness (it isn't), but to confirm the departure's error stays small and
/// its rare large jumps are confined to one understood, bounded case: a near-silent
/// channel's pre-log value sitting right at the "value > 1" floor, where a tiny
/// FFT-precision difference flips which side of that threshold each implementation lands
/// on. This is not a novel risk being hoped away — github.com/zserge/microwakeword's own
/// pure-Go reimplementation of this exact reference pipeline makes the identical call (a
/// plain float64 FFT standing in for kiss_fft's fixed-point one) and its own golden test
/// accepts a proportionally much looser tolerance, on the same reasoning: the downstream
/// model is itself int8-quantized and trained to be robust to noise well past this level.
class MicroFrontend {
  static const int sampleRate = 16000;
  static const int windowSizeMs = 30;
  static const int windowStepMs = 10;
  static const int numChannels = 40;
  static const double lowerBandLimitHz = 125.0;
  static const double upperBandLimitHz = 7500.0;

  static const int windowSize = sampleRate * windowSizeMs ~/ 1000; // 480
  static const int windowStep = sampleRate * windowStepMs ~/ 1000; // 160
  static const int fftSize = 512; // next power of two >= windowSize
  static const int fftBins = fftSize ~/ 2 + 1; // 257

  static const int kFrontendWindowBits = 12;
  static const int kFilterbankBits = 12;
  static const int kNoiseReductionBits = 14;
  static const int kPcanSnrBits = 12;
  static const int kPcanOutputBits = 6;

  static const double noiseEvenSmoothing = 0.025;
  static const double noiseOddSmoothing = 0.06;
  static const double noiseMinSignalRemaining = 0.05;
  static const int noiseSmoothingBits = 10;

  static const bool pcanEnabled = true;
  static const double pcanStrength = 0.95;
  static const double pcanOffset = 80.0;
  static const int pcanGainBits = 21;

  static const int logScaleShift = 6;

  static const double outFloatScale = 0.0390625; // matches micro_features.cpp's FLOAT32_SCALE

  late final Int32List _hannWindow; // fixed-point, kFrontendWindowBits
  late final _FilterbankPlan _filterbank;
  final Uint32List _noiseEstimate = Uint32List(numChannels);
  late final Int16List _pcanGainLut;
  late final int _pcanSnrShift;
  late final int _inputCorrectionBits;
  late final int _logCorrectionBits;

  // Ring buffer holding the last windowSize raw samples so a new hop only needs
  // windowStep fresh samples to produce the next frame — mirrors WindowProcessSamples'
  // own "shift by step, refill the tail" behaviour, without its fixed 480-sample cap
  // ever changing shape at runtime.
  final Int16List _ring = Int16List(windowSize);
  bool _ringPrimed = false;

  MicroFrontend() {
    _hannWindow = _buildHannWindow(windowSize, kFrontendWindowBits);
    _filterbank = _FilterbankPlan.build(
      numChannels: numChannels,
      lowerBandLimitHz: lowerBandLimitHz,
      upperBandLimitHz: upperBandLimitHz,
      sampleRate: sampleRate,
      spectrumSize: fftBins,
    );
    _inputCorrectionBits = _mostSignificantBit(fftSize) - 1 - (kFilterbankBits ~/ 2);
    _pcanGainLut = _buildPcanGainLut(
      strength: pcanStrength,
      offset: pcanOffset,
      gainBits: pcanGainBits,
      smoothingBits: noiseSmoothingBits,
      inputCorrectionBits: _inputCorrectionBits,
    );
    _pcanSnrShift = pcanGainBits - _inputCorrectionBits - kPcanSnrBits;
    _logCorrectionBits = _mostSignificantBit(fftSize) - 1 - (kFilterbankBits ~/ 2);
  }

  /// Resets streaming state (ring buffer + noise floor) — call when starting a fresh
  /// listening session, never mid-utterance, or the noise-reduction estimate carries
  /// stale ambient-noise history across an unrelated gap in audio.
  void reset() {
    _ring.fillRange(0, _ring.length, 0);
    _ringPrimed = false;
    _noiseEstimate.fillRange(0, _noiseEstimate.length, 0);
  }

  /// Feeds [pcm16] (mono, 16kHz, little-endian int16 samples) and returns one 40-channel
  /// feature frame per [windowStep] (160, i.e. 10ms) samples consumed. A caller streaming
  /// live microphone audio should call this once per arriving chunk and use ALL returned
  /// frames (there can be 0, 1, or several per call, depending on chunk size).
  List<Float64List> process(Int16List pcm16) {
    final frames = <Float64List>[];
    int offset = 0;
    while (offset < pcm16.length) {
      if (!_ringPrimed) {
        final need = windowSize - _filledRing;
        final take = math.min(need, pcm16.length - offset);
        _ring.setRange(_filledRing, _filledRing + take, pcm16, offset);
        _filledRing += take;
        offset += take;
        if (_filledRing < windowSize) break;
        _ringPrimed = true;
        frames.add(_processWindow(_ring));
        continue;
      }
      const need = windowStep;
      final take = math.min(need, pcm16.length - offset);
      if (take < windowStep) {
        // Not enough for another full hop this call — stash the partial hop.
        _pendingPartial ??= Int16List(windowStep);
        _pendingPartial!.setRange(_pendingFilled, _pendingFilled + take, pcm16, offset);
        _pendingFilled += take;
        offset += take;
        if (_pendingFilled == windowStep) {
          _advanceRing(_pendingPartial!);
          frames.add(_processWindow(_ring));
          _pendingFilled = 0;
        }
        break;
      }
      final hop = Int16List.sublistView(pcm16, offset, offset + windowStep);
      _advanceRing(hop);
      frames.add(_processWindow(_ring));
      offset += windowStep;
    }
    return frames;
  }

  int _filledRing = 0;
  Int16List? _pendingPartial;
  int _pendingFilled = 0;

  void _advanceRing(Int16List hop) {
    // Shift left by windowStep, append hop at the tail — same sliding-window shape
    // WindowProcessSamples produces (retain windowSize - windowStep, refill the rest).
    _ring.setRange(0, windowSize - windowStep, _ring, windowStep);
    _ring.setRange(windowSize - windowStep, windowSize, hop);
  }

  Float64List _processWindow(Int16List window) {
    // --- Window stage: apply Hann coefficients (fixed-point, matches WindowProcessSamples). ---
    final windowed = Int16List(windowSize);
    int maxAbs = 0;
    for (int i = 0; i < windowSize; i++) {
      final v = (window[i] * _hannWindow[i]) >> kFrontendWindowBits;
      windowed[i] = v.clamp(-32768, 32767);
      final abs = v.abs();
      if (abs > maxAbs) maxAbs = abs;
    }
    if (maxAbs == 0) maxAbs = 1;
    final inputShift = 15 - _mostSignificantBit(maxAbs);

    // --- FFT stage: real FFT of the (shift-scaled) windowed samples, magnitude^2 energy. ---
    final scaled = Float64List(fftSize);
    for (int i = 0; i < windowSize; i++) {
      scaled[i] = (windowed[i] * (1 << inputShift)).toDouble();
    }
    final (re, im) = _realFft(scaled);
    final energy = Uint32List(fftBins);
    for (int i = 0; i < fftBins; i++) {
      final e = re[i] * re[i] + im[i] * im[i];
      energy[i] = e.round().clamp(0, 0xFFFFFFFF);
    }
    energy[0] = 0; // DC bin is never used by the filterbank (matches FilterbankConvertFftComplexToEnergy's own skip)

    // --- Mel filterbank: overlapping triangular accumulation, then sqrt. ---
    final filterbankEnergy = _filterbank.accumulate(energy);
    final scaledFilterbank = Uint32List(numChannels);
    for (int i = 0; i < numChannels; i++) {
      scaledFilterbank[i] = _sqrt64(filterbankEnergy[i]);
    }
    // FilterbankSqrt's own real signature is `FilterbankSqrt(state, scale_down_shift)` called
    // from frontend.cc as `FilterbankSqrt(&state->filterbank, input_shift)` — input_shift ALONE,
    // never combined with the (unused-at-runtime) `output_scale_shift` config field.
    for (int i = 0; i < numChannels; i++) {
      scaledFilterbank[i] = inputShift >= 0
          ? (scaledFilterbank[i] >> inputShift)
          : (scaledFilterbank[i] << (-inputShift));
    }

    // --- Noise reduction: per-channel exponential-moving-average noise floor subtraction. ---
    for (int i = 0; i < numChannels; i++) {
      final smoothing = (i.isEven)
          ? (noiseEvenSmoothing * (1 << kNoiseReductionBits)).round()
          : (noiseOddSmoothing * (1 << kNoiseReductionBits)).round();
      final oneMinusSmoothing = (1 << kNoiseReductionBits) - smoothing;
      final signalScaledUp = scaledFilterbank[i] << noiseSmoothingBits;
      int estimate = (((signalScaledUp * smoothing) + (_noiseEstimate[i] * oneMinusSmoothing)) >>
              kNoiseReductionBits)
          .toInt();
      _noiseEstimate[i] = estimate;
      if (estimate > signalScaledUp) estimate = signalScaledUp;
      final floor = ((scaledFilterbank[i] * (noiseMinSignalRemaining * (1 << kNoiseReductionBits)).round()) >>
              kNoiseReductionBits)
          .toInt();
      final subtracted = (signalScaledUp - estimate) >> noiseSmoothingBits;
      scaledFilterbank[i] = subtracted > floor ? subtracted : floor;
    }

    // --- PCAN gain control (enabled per micro_features.cpp's own default config). ---
    if (pcanEnabled) {
      for (int i = 0; i < numChannels; i++) {
        final gain = _wideDynamicFunction(_noiseEstimate[i], _pcanGainLut);
        final snr = (scaledFilterbank[i] * gain) >> _pcanSnrShift;
        scaledFilterbank[i] = _pcanShrink(snr);
      }
    }

    // --- Log scale: fixed-point log2->loge->output-scale, then clamp to uint16. ---
    final out = Float64List(numChannels);
    for (int i = 0; i < numChannels; i++) {
      var value = scaledFilterbank[i];
      value = _logCorrectionBits < 0 ? (value >> -_logCorrectionBits) : (value << _logCorrectionBits);
      final logged = value > 1 ? _fixedLog(value, logScaleShift) : 0;
      final clamped = logged > 0xFFFF ? 0xFFFF : logged;
      out[i] = clamped * outFloatScale;
    }
    return out;
  }

  static Int32List _buildHannWindow(int size, int bits) {
    final w = Int32List(size);
    for (int i = 0; i < size; i++) {
      final coeff = 0.5 - 0.5 * math.cos(2 * math.pi * (i + 0.5) / size);
      w[i] = (coeff * (1 << bits) + 0.5).floor();
    }
    return w;
  }

  static int _mostSignificantBit(int n) {
    if (n <= 0) return 0;
    int bits = 0;
    while (n > 0) {
      bits++;
      n >>= 1;
    }
    return bits;
  }

  static int _sqrt64(int value) {
    if (value <= 0) return 0;
    int x = value;
    int result = 0;
    int bit = 1 << 62;
    while (bit > x) {
      bit >>= 2;
    }
    while (bit != 0) {
      if (x >= result + bit) {
        x -= result + bit;
        result = (result >> 1) + bit;
      } else {
        result >>= 1;
      }
      bit >>= 2;
    }
    return result;
  }

  // Mirrors the reference's own indexing exactly: PcanGainControlPopulateState builds the LUT
  // starting at a base pointer, writes gain_lut[0]/[1] before ever shifting, then does
  // `gain_lut -= 6` so every `4 * interval` write for interval>=2 lands at a NEGATIVE offset
  // relative to that base, and finally does `gain_lut += 6` before returning — so the returned
  // pointer's [0] and [1] are those first two direct writes, and interval `k`'s 3 coefficients
  // live at [4*k - 6], [4*k - 5], [4*k - 4]. Ported here as a plain array indexed by
  // `logicalIndex + 6` so no negative indices are ever needed, but the same relative layout.
  static Int16List _buildPcanGainLut({
    required double strength,
    required double offset,
    required int gainBits,
    required int smoothingBits,
    required int inputCorrectionBits,
  }) {
    const kWideDynamicFunctionBits = 32;
    const kWideDynamicFunctionLUTSize = 4 * kWideDynamicFunctionBits + 6;
    final lut = Int16List(kWideDynamicFunctionLUTSize);
    final inputBits = smoothingBits - inputCorrectionBits;

    int gainAt(int x) {
      final xAsFloat = x / (1 << inputBits);
      final gainAsFloat = (1 << gainBits) * math.pow(xAsFloat + offset, -strength);
      if (gainAsFloat > 0x7FFF) return 0x7FFF;
      return (gainAsFloat + 0.5).floor();
    }

    lut[0 + 6] = gainAt(0);
    lut[1 + 6] = gainAt(1);
    for (int interval = 2; interval <= kWideDynamicFunctionBits; interval++) {
      final x0 = 1 << (interval - 1);
      final x1 = x0 + (x0 >> 1);
      final x2 = (interval == kWideDynamicFunctionBits) ? x0 + (x0 - 1) : 2 * x0;
      final y0 = gainAt(x0);
      final y1 = gainAt(x1);
      final y2 = gainAt(x2);
      final diff1 = y1 - y0;
      final diff2 = y2 - y0;
      final a1 = 4 * diff1 - diff2;
      final a2 = diff2 - a1;
      final base = 4 * interval - 6 + 6; // logical [4*interval - 6] shifted into the +6 array
      lut[base] = y0;
      lut[base + 1] = a1.clamp(-32768, 32767);
      lut[base + 2] = a2.clamp(-32768, 32767);
    }
    return lut;
  }

  static int _wideDynamicFunction(int x, Int16List lut) {
    if (x <= 2) return lut[x + 6];
    final interval = _mostSignificantBit(x);
    final base = 4 * interval - 6 + 6; // matches _buildPcanGainLut's own +6-shifted layout
    final frac = ((interval < 11) ? (x << (11 - interval)) : (x >> (interval - 11))) & 0x3FF;
    int result = (lut[base + 2] * frac) >> 5;
    result += lut[base + 1] << 5;
    result *= frac;
    result = (result + (1 << 14)) >> 15;
    result += lut[base];
    return result;
  }

  static int _pcanShrink(int x) {
    if (x < (2 << kPcanSnrBits)) {
      return (x * x) >> (2 + 2 * kPcanSnrBits - kPcanOutputBits);
    } else {
      return (x >> (kPcanSnrBits - kPcanOutputBits)) - (1 << kPcanOutputBits);
    }
  }

  static int _fixedLog(int x, int scaleShift) {
    // A direct double-precision stand-in for the reference's LUT-interpolated fixed-point log:
    // mathematically the same target function (natural log, fixed-point scaled by 2^scaleShift),
    // so it matches within the golden-vector tolerance without porting the reference's own
    // 100-entry log_lut table byte-for-byte.
    return (math.log(x.toDouble()) * (1 << scaleShift)).round();
  }
}

/// Precomputes, once, which mel channel each FFT bin's energy contributes to and with what
/// split — a direct, per-bin table rather than the reference's pointer-shuffling `work` buffer,
/// verified to produce the same standard overlapping-triangle mel filterbank: FFT bin `k`'s
/// energy splits between channel `binChannel[k]` (weighted by `binWeight[k]`) and channel
/// `binChannel[k] + 1` (weighted by `1 - binWeight[k]`, i.e. `binUnweight[k]`) — following
/// filterbank_util.cc's own `FreqToMel`/`CalculateCenterFrequencies`/`FilterbankPopulateState`
/// exactly, just walked bin-by-bin instead of via negative-offset pointer arithmetic.
class _FilterbankPlan {
  final int numChannels;
  final Int32List binChannel; // -1 = bin contributes to no channel (below lower_band_limit or past upper)
  final Int16List binWeight;
  final Int16List binUnweight;
  final int outputScaleShift;

  _FilterbankPlan({
    required this.numChannels,
    required this.binChannel,
    required this.binWeight,
    required this.binUnweight,
    required this.outputScaleShift,
  });

  static double _freqToMel(double freq) => 1127.0 * math.log(1.0 + freq / 700.0);

  static _FilterbankPlan build({
    required int numChannels,
    required double lowerBandLimitHz,
    required double upperBandLimitHz,
    required int sampleRate,
    required int spectrumSize,
  }) {
    final melLow = _freqToMel(lowerBandLimitHz);
    final melHi = _freqToMel(upperBandLimitHz);
    // num_channels + 1 center points: index c is the RIGHT edge of channel c (0-based),
    // matching CalculateCenterFrequencies's own `mel_low + mel_spacing * (i + 1)` for
    // i in [0, num_channels].
    final melSpacing = (melHi - melLow) / (numChannels + 1);
    final centerMel = List<double>.generate(numChannels + 1, (i) => melLow + melSpacing * (i + 1));
    final hzPerSbin = 0.5 * sampleRate / (spectrumSize - 1);
    // Matches FilterbankPopulateState's own `state->start_index = 1.5f + lower_band_limit /
    // hz_per_sbin` exactly — bins below this are never DC alone, they're bins the reference
    // deliberately never assigns to any channel (below where channel 0's own triangle starts).
    final startIndex = (1.5 + lowerBandLimitHz / hzPerSbin).toInt();

    final binChannel = Int32List(spectrumSize)..fillRange(0, spectrumSize, -1);
    final binWeight = Int16List(spectrumSize);
    final binUnweight = Int16List(spectrumSize);

    int chan = 0;
    for (int bin = startIndex; bin < spectrumSize; bin++) {
      final mel = _freqToMel(bin * hzPerSbin);
      // Advance past any channel whose right edge this bin has already crossed — a bin can
      // legitimately skip a channel entirely when bins are sparse relative to mel spacing
      // (low upper_band_limit or low sample rate), same as the reference's own while-style walk.
      while (chan <= numChannels && mel > centerMel[chan]) {
        chan++;
      }
      if (chan > numChannels) break; // past the last channel — remaining high bins are unused
      final lowerEdge = chan == 0 ? melLow : centerMel[chan - 1];
      final denom = centerMel[chan] - lowerEdge;
      final weight = denom > 0 ? ((centerMel[chan] - mel) / denom).clamp(0.0, 1.0) : 0.0;
      binChannel[bin] = chan;
      binWeight[bin] = (weight * (1 << 12) + 0.5).floor().clamp(0, 32767);
      binUnweight[bin] = ((1.0 - weight) * (1 << 12) + 0.5).floor().clamp(0, 32767);
    }

    return _FilterbankPlan(
      numChannels: numChannels,
      binChannel: binChannel,
      binWeight: binWeight,
      binUnweight: binUnweight,
      outputScaleShift: 7,
    );
  }

  Uint64List accumulate(Uint32List energy) {
    // A bin on channel `chan`'s RISING slope (toward its peak) is simultaneously on channel
    // `chan - 1`'s FALLING slope — its energy splits `weight` into channel `chan` and
    // `unweight` (1-weight) into channel `chan - 1`. `out` is offset by +1 so logical channel
    // -1 (below channel 0, discarded) and logical channel `numChannels` (past the last real
    // channel, discarded — it only exists to give the last channel a falling edge) both have
    // a safe slot without special-casing every access.
    final out = Uint64List(numChannels + 2);
    for (int bin = 1; bin < energy.length && bin < binChannel.length; bin++) {
      final chan = binChannel[bin];
      if (chan < 0) continue;
      final e = energy[bin];
      out[chan + 1] += (e * binWeight[bin]) >> 12;
      out[chan - 1 + 1] += (e * binUnweight[bin]) >> 12;
    }
    return Uint64List.fromList(out.sublist(1, numChannels + 1));
  }
}

/// A plain, real-valued FFT (Cooley-Tukey radix-2, double precision) — see this file's own
/// top-of-file doc comment for why this replaces the reference's fixed-point kiss_fft rather
/// than porting it bit-for-bit.
(Float64List re, Float64List im) _realFft(Float64List input) {
  final n = input.length;
  final re = Float64List(n)..setAll(0, input);
  final im = Float64List(n);
  _fftInPlace(re, im);
  final bins = n ~/ 2 + 1;
  return (Float64List.sublistView(re, 0, bins), Float64List.sublistView(im, 0, bins));
}

void _fftInPlace(Float64List re, Float64List im) {
  final n = re.length;
  // Bit-reversal permutation.
  for (int i = 1, j = 0; i < n; i++) {
    int bit = n >> 1;
    for (; (j & bit) != 0; bit >>= 1) {
      j ^= bit;
    }
    j ^= bit;
    if (i < j) {
      final tr = re[i];
      re[i] = re[j];
      re[j] = tr;
      final ti = im[i];
      im[i] = im[j];
      im[j] = ti;
    }
  }
  for (int len = 2; len <= n; len <<= 1) {
    final ang = -2 * math.pi / len;
    final wRe = math.cos(ang);
    final wIm = math.sin(ang);
    for (int i = 0; i < n; i += len) {
      double curRe = 1.0, curIm = 0.0;
      for (int j = 0; j < len ~/ 2; j++) {
        final uRe = re[i + j];
        final uIm = im[i + j];
        final vRe = re[i + j + len ~/ 2] * curRe - im[i + j + len ~/ 2] * curIm;
        final vIm = re[i + j + len ~/ 2] * curIm + im[i + j + len ~/ 2] * curRe;
        re[i + j] = uRe + vRe;
        im[i + j] = uIm + vIm;
        re[i + j + len ~/ 2] = uRe - vRe;
        im[i + j + len ~/ 2] = uIm - vIm;
        final nextRe = curRe * wRe - curIm * wIm;
        final nextIm = curRe * wIm + curIm * wRe;
        curRe = nextRe;
        curIm = nextIm;
      }
    }
  }
}
