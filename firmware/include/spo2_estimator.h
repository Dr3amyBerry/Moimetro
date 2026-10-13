#pragma once
// Moimetro MAX30102 PPG ratio-of-ratios processing.
// Experimental bench signal processing, NOT clinically validated SpO2.
// No external dependency: native host tests compile the same implementation.
//
// R = (AC_red / DC_red) / (AC_ir / DC_ir)
// SpO2 = a*R^2 + b*R + c ONLY when coefficients for THIS optical assembly
// were obtained and validated by an appropriate reference calibration study.
#include <cmath>
#include <cstdint>

namespace moi {

enum class OpticalQuality : uint8_t {
  NoContact, Collecting, WeakSignal, Saturated, Unstable, ValidPPG
};

struct OpticalResult {
  OpticalQuality quality = OpticalQuality::Collecting;
  float ratio = NAN;
  float redPerfusion = NAN;
  float irPerfusion = NAN;
  float correlation = NAN;
  float experimentalSpO2 = NAN;
  bool hasRatio = false;
  bool hasExperimentalSpO2 = false;
};

struct Calibration {
  // No default curve: values MUST be provided for the assembled device.
  bool enabled = false;
  float a = NAN, b = NAN, c = NAN;
  float minRatio = NAN, maxRatio = NAN;
};

class Spo2Estimator {
 public:
  static constexpr unsigned kSamplesPerSecond = 25;
  static constexpr unsigned kWindow = 100; // 4 s of paired Red/IR
  static constexpr unsigned kUpdateEvery = 25; // 1 s sliding update
  static constexpr uint32_t kMinimumContactIR = 50000;
  static constexpr uint32_t kAdcSaturation = 250000; // 18-bit ADC guard

  explicit Spo2Estimator(Calibration calibration = {}) : calibration_(calibration) {}

  void reset(OpticalQuality why = OpticalQuality::NoContact) {
    count_ = 0;
    head_ = 0;
    stride_ = 0;
    hasPrevious_ = false;
    output_ = {};
    output_.quality = why;
  }

  const OpticalResult &result() const { return output_; }

  // Feed the PAIR from the same MAX30102 FIFO slot exactly once.
  // Returns true only when a fresh 4-second-window result is available.
  bool add(uint32_t red, uint32_t ir) {
    if (ir < kMinimumContactIR || red < 10000) {
      reset(OpticalQuality::NoContact);
      return false;
    }
    if (ir >= kAdcSaturation || red >= kAdcSaturation) {
      reset(OpticalQuality::Saturated);
      return false;
    }
    red_[head_] = red;
    ir_[head_] = ir;
    head_ = (head_ + 1) % kWindow;
    if (count_ < kWindow) ++count_;
    if (count_ != kWindow) {
      output_.quality = OpticalQuality::Collecting;
      return false;
    }
    if (++stride_ < kUpdateEvery && hasComputed_) return false;
    stride_ = 0;
    hasComputed_ = true;
    compute();
    return true;
  }

 private:
  uint32_t red_[kWindow] = {}, ir_[kWindow] = {};
  unsigned count_ = 0, head_ = 0, stride_ = 0;
  bool hasPrevious_ = false, hasComputed_ = false;
  float previousRatio_ = NAN;
  Calibration calibration_;
  OpticalResult output_;

  void compute() {
    OpticalResult next;
    // Two-pass linear detrending removes DC and slow drift before AC RMS.
    // Circular indexing keeps a bounded 100-sample memory footprint.
    double redMean = 0, irMean = 0;
    for (unsigned n = 0; n < kWindow; ++n) {
      const unsigned i = (head_ + n) % kWindow;
      redMean += red_[i]; irMean += ir_[i];
    }
    redMean /= kWindow;
    irMean /= kWindow;

    // Remove the least-squares linear trend. A monotonic ramp or motion
    // cannot masquerade as pulsatile AC by inflating standard deviation.
    double redSlope = 0, irSlope = 0;
    constexpr double center = (kWindow - 1) / 2.0;
    constexpr double timeVariance = (kWindow * (kWindow * kWindow - 1)) / 12.0;
    for (unsigned n = 0; n < kWindow; ++n) {
      const unsigned i = (head_ + n) % kWindow;
      const double t = static_cast<double>(n) - center;
      redSlope += t * (static_cast<double>(red_[i]) - redMean);
      irSlope += t * (static_cast<double>(ir_[i]) - irMean);
    }
    redSlope /= timeVariance;
    irSlope /= timeVariance;

    double r2 = 0, i2 = 0, cross = 0;
    // Split-half AC variation is a rough stability / movement screen.
    double redHalf[2] = {}, irHalf[2] = {};
    for (unsigned n = 0; n < kWindow; ++n) {
      const unsigned i = (head_ + n) % kWindow;
      const double t = static_cast<double>(n) - center;
      const double r = static_cast<double>(red_[i]) - redMean - redSlope * t;
      const double v = static_cast<double>(ir_[i]) - irMean - irSlope * t;
      r2 += r * r;
      i2 += v * v;
      cross += r * v;
      redHalf[n >= kWindow / 2] += r * r;
      irHalf[n >= kWindow / 2] += v * v;
    }
    const double redRms = std::sqrt(r2 / kWindow);
    const double irRms = std::sqrt(i2 / kWindow);
    const double pRed = redRms / redMean;
    const double pIr = irRms / irMean;
    if (!std::isfinite(pRed) || !std::isfinite(pIr) ||
        pRed < 0.002 || pIr < 0.002) {
      next.quality = OpticalQuality::WeakSignal;
      hasPrevious_ = false;
      output_ = next;
      return;
    }
    const double coherence = cross / std::sqrt(r2 * i2);
    next.correlation = static_cast<float>(coherence);
    next.redPerfusion = static_cast<float>(pRed);
    next.irPerfusion = static_cast<float>(pIr);
    // Pulsatile Red/IR signals should vary together, not independently.
    const double redBalance = std::sqrt(redHalf[0] / redHalf[1]);
    const double irBalance = std::sqrt(irHalf[0] / irHalf[1]);
    const double ratio = pRed / pIr;
    if (!std::isfinite(ratio) || ratio < 0.25 || ratio > 2.0 ||
        !std::isfinite(coherence) || coherence < 0.70 ||
        !std::isfinite(redBalance) || !std::isfinite(irBalance) ||
        redBalance < 0.40 || redBalance > 2.50 ||
        irBalance < 0.40 || irBalance > 2.50 ||
        (hasPrevious_ && std::fabs(ratio - previousRatio_) > 0.20)) {
      next.quality = OpticalQuality::Unstable;
      hasPrevious_ = false;
      output_ = next;
      return;
    }
    hasPrevious_ = true;
    previousRatio_ = static_cast<float>(ratio);
    next.quality = OpticalQuality::ValidPPG;
    next.hasRatio = true;
    next.ratio = static_cast<float>(ratio);

    // Never fill a missing calibration with a hardcoded saturation figure.
    if (calibration_.enabled && std::isfinite(calibration_.a) &&
        std::isfinite(calibration_.b) && std::isfinite(calibration_.c) &&
        std::isfinite(calibration_.minRatio) &&
        std::isfinite(calibration_.maxRatio) &&
        calibration_.minRatio < calibration_.maxRatio &&
        ratio >= calibration_.minRatio && ratio <= calibration_.maxRatio) {
      const double estimate = calibration_.a * ratio * ratio +
                              calibration_.b * ratio + calibration_.c;
      if (std::isfinite(estimate) && estimate >= 70 && estimate <= 100) {
        next.experimentalSpO2 = static_cast<float>(estimate);
        next.hasExperimentalSpO2 = true;
      }
    }
    output_ = next;
  }
};

inline const char *qualityName(OpticalQuality quality) {
  switch (quality) {
    case OpticalQuality::NoContact: return "sin_dedo";
    case OpticalQuality::Collecting: return "adquiriendo";
    case OpticalQuality::WeakSignal: return "senal_debil";
    case OpticalQuality::Saturated: return "saturacion_adc";
    case OpticalQuality::Unstable: return "movimiento_o_senal_inestable";
    case OpticalQuality::ValidPPG: return "ppg_valida_no_clinica";
  }
  return "desconocido";
}
} // namespace moi
