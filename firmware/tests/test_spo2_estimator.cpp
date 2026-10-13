// Native, synthetic-only algorithm contract tests. NO human/clinical data.
// Run: g++ -std=c++17 -Wall -Wextra -Werror -Ifirmware/include
//       firmware/tests/test_spo2_estimator.cpp -o /tmp/moimetro_spo2 && /tmp/moimetro_spo2
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include "spo2_estimator.h"

static constexpr double kPi = 3.14159265358979323846;

static void signal(moi::Spo2Estimator &estimate, unsigned length = 150,
                   float redAC = 1800, float irAC = 2500,
                   bool decorrelate = false) {
  for (unsigned n = 0; n < length; ++n) {
    const double phase = 2 * kPi * 1.2 * n / 25;
    const uint32_t red = static_cast<uint32_t>(
        105000.0 + redAC * std::sin(phase + (decorrelate ? kPi / 2 : 0)));
    const uint32_t ir = static_cast<uint32_t>(
        110000.0 + irAC * std::sin(phase));
    estimate.add(red, ir);
  }
}

int main() {
  {
    moi::Spo2Estimator estimate;
    const auto &initial = estimate.result();
    assert(!initial.hasRatio);
    assert(!initial.hasExperimentalSpO2);
    signal(estimate);
    const auto &state = estimate.result();
    assert(state.quality == moi::OpticalQuality::ValidPPG);
    assert(state.hasRatio);
    const double theoretical =
        (1800.0 / 105000.0) / (2500.0 / 110000.0);
    assert(std::fabs(state.ratio - theoretical) < 0.05);
    // Real input produces a measured R, but NEVER a fake saturation.
    assert(!state.hasExperimentalSpO2);
    assert(std::isnan(state.experimentalSpO2));

    estimate.add(95000, 1); // Finger removed
    assert(estimate.result().quality == moi::OpticalQuality::NoContact);
    assert(!estimate.result().hasRatio);
    signal(estimate);
    assert(estimate.result().hasRatio); // Full fresh window required.
  }
  {
    moi::Spo2Estimator estimate;
    for (unsigned n = 0; n < 150; ++n) {
      estimate.add(100000, 110000); // DC with no pulsatile AC
    }
    assert(estimate.result().quality == moi::OpticalQuality::WeakSignal);
    assert(!estimate.result().hasRatio);
  }
  {
    moi::Spo2Estimator estimate;
    for (unsigned n = 0; n < 150; ++n) {
      estimate.add(100000 + 5 * n, 110000 + 8 * n);
    }
    // Pure drift, no pulsatile AC, rejected after linear detrending.
    assert(!estimate.result().hasRatio);
  }
  {
    moi::Spo2Estimator estimate;
    signal(estimate, 150, 1800, 2500, true);
    assert(estimate.result().quality == moi::OpticalQuality::Unstable);
    assert(!estimate.result().hasRatio);
  }
  {
    moi::Spo2Estimator estimate;
    signal(estimate, 150, 1800, 2500);
    assert(estimate.result().hasRatio);
    estimate.add(250001, 110000);
    assert(estimate.result().quality == moi::OpticalQuality::Saturated);
    assert(!estimate.result().hasRatio);
  }
  {
    // Synthetic calibration proves that the coefficients are APPLIED,
    // not that these example coefficients are appropriate for people.
    moi::Calibration lab = {true, 0.0f, -25.0f, 110.0f, 0.3f, 1.5f};
    moi::Spo2Estimator estimate(lab);
    signal(estimate);
    const auto &state = estimate.result();
    assert(state.hasRatio && state.hasExperimentalSpO2);
    assert(std::fabs(state.experimentalSpO2 -
                     (110.0f - 25.0f * state.ratio)) < 0.01f);
    // No value when outside the model's declared calibration interval.
    moi::Calibration restrictive = {true, 0, -25, 110, 1.8f, 2.0f};
    moi::Spo2Estimator outOfRange(restrictive);
    signal(outOfRange);
    assert(outOfRange.result().hasRatio);
    assert(!outOfRange.result().hasExperimentalSpO2);
    assert(std::isnan(outOfRange.result().experimentalSpO2));
  }
  std::puts("SpO2 PPG bench processing: synthetic contract tests passed.");
  return 0;
}
