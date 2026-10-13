/*
 * Moímetro ESP32 firmware PROTOTYPE
 *
 * Sensors: DHT11 on GPIO18; DS18B20 on GPIO4;
 * MAX30102 I2C SDA21 / SCL22.
 *
 * Experimental ratio-of-ratios from actual synchronized Red/IR PPG.
 * NO clinical SpO2 is reported. A device-specific, validated calibration
 * is needed before this can be used as a medical saturation measurement.
 * The local patient API deliberately rejects device SpO2.
 * For bench testing only. Do not use to make medical decisions.
 */
#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include "MAX30105.h"
#include "heartRate.h"
#include "spo2_estimator.h"
#include "secrets.h"

static constexpr int DHT_PIN = 18;
static constexpr int ONEWIRE_PIN = 4;
static constexpr int SDA_PIN = 21;
static constexpr int SCL_PIN = 22;
static constexpr uint32_t FINGER_IR_MIN = 50000; // bench-only heuristic
static constexpr unsigned long WIFI_RETRY_MS = 10000;
static constexpr unsigned long DHT_INTERVAL_MS = 2500;
static constexpr unsigned long DS_INTERVAL_MS = 2000;
static constexpr unsigned long UPLOAD_INTERVAL_MS = 3000;
static constexpr unsigned long POLL_INTERVAL_MS = 5000;
static constexpr unsigned long BODY_CONVERSION_MS = 250; // 10-bit DS18B20 approx 188 ms
static constexpr byte RATE_SIZE = 4;

DHT dht(DHT_PIN, DHT11);
OneWire wire(ONEWIRE_PIN);
DallasTemperature ds18b20(&wire);
MAX30105 maxSensor;

bool maxReady = false;
bool fingerPresent = false;
float ambientC = NAN, humidity = NAN, bodyC = NAN, bpm = NAN;
portMUX_TYPE opticalMux = portMUX_INITIALIZER_UNLOCKED;
moi::OpticalQuality opticalQuality = moi::OpticalQuality::Collecting;
float opticalRatio = NAN;
float benchSpo2 = NAN;
bool benchEstimateAvailable = false;

// Coefficients are NOT shipped: must come from calibration of THIS hardware.
// An optional LAB-only curve is configured in the untracked secrets.h file.
#if defined(MOI_SPO2_LAB_A) && defined(MOI_SPO2_LAB_B) &&     defined(MOI_SPO2_LAB_C) && defined(MOI_SPO2_LAB_R_MIN) &&     defined(MOI_SPO2_LAB_R_MAX)
moi::Calibration opticalCalibration = {
  true, MOI_SPO2_LAB_A, MOI_SPO2_LAB_B, MOI_SPO2_LAB_C,
  MOI_SPO2_LAB_R_MIN, MOI_SPO2_LAB_R_MAX
};
#else
moi::Calibration opticalCalibration = {};
#endif
moi::Spo2Estimator oxygenEstimator(opticalCalibration);
byte beatRates[RATE_SIZE] = {};
byte beatCount = 0, beatPosition = 0;
uint32_t lastBeat = 0;
unsigned long wifiAt = 0, dhtAt = 0, dsAt = 0, uploadAt = 0, pollAt = 0;
bool dsWaiting = false;
String captureId;

void resetPulse() {
  bpm = NAN;
  lastBeat = 0;
  beatCount = 0;
  beatPosition = 0;
  for (byte &value : beatRates) value = 0;
}

// Dedicated task prevents HTTP and Wi-Fi blocking the 25 Hz optical FIFO.
// MAX30102 is accessed from THIS task only, with Red + IR from the same slot.
// Linux/Windows never receives a lab SpO2 in its medical measurements API.
void opticalTask(void *arg) {
  (void)arg;
  unsigned long lastService = millis();
  uint32_t lastDiagnostic = 0;
  for (;;) {
    const unsigned long t = millis();
    if (t - lastService > 180) {
      // Cannot reconstruct dropped 25 Hz FIFO frames: restart the window.
      oxygenEstimator.reset(moi::OpticalQuality::Collecting);
      resetPulse();
      maxSensor.clearFIFO();
    }
    lastService = t;
    maxSensor.check();
    while (maxSensor.available()) {
      const uint32_t red = maxSensor.getFIFORed();
      const uint32_t ir = maxSensor.getFIFOIR();
      maxSensor.nextSample();

      const bool fresh = oxygenEstimator.add(red, ir);
      if (ir < FINGER_IR_MIN || red < 10000 || ir >= moi::Spo2Estimator::kAdcSaturation
          || red >= moi::Spo2Estimator::kAdcSaturation) {
        fingerPresent = false;
        resetPulse();
      } else {
        fingerPresent = true;
        const uint32_t instant = millis();
        if (lastBeat != 0 && instant - lastBeat > 4000) resetPulse();
        if (checkForBeat(ir)) {
          if (lastBeat != 0) {
            const uint32_t elapsed = instant - lastBeat;
            const float candidate = elapsed ? 60000.0f / elapsed : 0;
            if (candidate > 20 && candidate < 255) {
              beatRates[beatPosition] = static_cast<byte>(candidate);
              beatPosition = (beatPosition + 1) % RATE_SIZE;
              if (beatCount < RATE_SIZE) ++beatCount;
              uint16_t sum = 0;
              for (byte i = 0; i < beatCount; ++i) sum += beatRates[i];
              bpm = static_cast<float>(sum) / beatCount;
            }
          }
          lastBeat = instant;
        }
      }
      const moi::OpticalResult &state = oxygenEstimator.result();
      portENTER_CRITICAL(&opticalMux);
      opticalQuality = state.quality;
      opticalRatio = state.hasRatio ? state.ratio : NAN;
      benchSpo2 = state.hasExperimentalSpO2 ? state.experimentalSpO2 : NAN;
      benchEstimateAvailable = state.hasExperimentalSpO2;
      portEXIT_CRITICAL(&opticalMux);

      // Optical diagnostics: never equivalent to a validated oximeter.
      if (fresh && millis() - lastDiagnostic >= 1000) {
        lastDiagnostic = millis();
        Serial.printf("PPG BANCO: calidad=%s", moi::qualityName(state.quality));
        if (state.hasRatio) Serial.printf(" R=%.3f", state.ratio);
        if (state.hasExperimentalSpO2) {
          Serial.printf(" SpO2_ESTIMACION_EXPERIMENTAL=%.1f%%", state.experimentalSpO2);
        } else {
          Serial.print(" SpO2=NO_DISPONIBLE_SIN_CALIBRACION");
        }
        Serial.println(" (NO USO CLINICO)");
      }
    }
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

void readAmbient(unsigned long t) {
  if (t - dhtAt < DHT_INTERVAL_MS) return;
  dhtAt = t;
  const float c = dht.readTemperature();
  const float h = dht.readHumidity();
  ambientC = isfinite(c) ? c : NAN;
  humidity = isfinite(h) ? h : NAN;
}

void readBody(unsigned long t) {
  if (dsWaiting && t - dsAt >= BODY_CONVERSION_MS) {
    const float c = ds18b20.getTempCByIndex(0);
    bodyC = (c != DEVICE_DISCONNECTED_C && isfinite(c) && c > -55 && c < 125) ? c : NAN;
    dsWaiting = false;
  }
  if (!dsWaiting && t - dsAt >= DS_INTERVAL_MS) {
    ds18b20.requestTemperatures();
    dsAt = t;
    dsWaiting = true;
  }
}

void keepWifi(unsigned long t) {
  if (WiFi.status() == WL_CONNECTED) return;
  captureId = "";
  if (t - wifiAt >= WIFI_RETRY_MS) {
    wifiAt = t;
    WiFi.disconnect();
    WiFi.begin(MOI_WIFI_SSID, MOI_WIFI_PASSWORD);
    Serial.println("Reintentando WiFi local...");
  }
}

void pollCapture() {
  if (WiFi.status() != WL_CONNECTED) return;
  WiFiClient client;
  HTTPClient http;
  http.setTimeout(500);
  if (!http.begin(client, String(MOI_API_BASE) + "/api/device/active-session")) return;
  http.addHeader("X-Device-Key", MOI_DEVICE_KEY);
  int status = http.GET();
  if (status == HTTP_CODE_OK) {
    JsonDocument payload;
    const String body = http.getString();
    if (deserializeJson(payload, body) == DeserializationError::Ok) {
      captureId = payload["session_id"].isNull() ? "" :
                  payload["session_id"].as<String>();
    }
  } else if (status == HTTP_CODE_UNAUTHORIZED || status == HTTP_CODE_SERVICE_UNAVAILABLE) {
    captureId = "";
    Serial.println("Autenticación del dispositivo rechazada.");
  }
  http.end();
}

void addSample(JsonArray &values, const char *kind, float value, const char *invalidStatus = "unavailable") {
  JsonObject sample = values.add<JsonObject>();
  sample["kind"] = kind;
  if (isfinite(value)) {
    sample["quality"] = "ok";
    sample["value"] = value;
  } else {
    sample["quality"] = invalidStatus;
    sample["value"] = nullptr;
  }
}

void uploadReadings() {
  if (captureId.isEmpty() || WiFi.status() != WL_CONNECTED) return;
  JsonDocument payload;
  payload["session_id"] = captureId;
  payload["device_id"] = MOI_DEVICE_ID;
  JsonArray values = payload["samples"].to<JsonArray>();
  float pulseSnapshot;
  bool contactSnapshot;
  portENTER_CRITICAL(&opticalMux);
  pulseSnapshot = bpm;
  contactSnapshot = fingerPresent;
  portEXIT_CRITICAL(&opticalMux);
  addSample(values, "body_temp_c", bodyC);
  addSample(values, "pulse_bpm", pulseSnapshot,
            maxReady && !contactSnapshot ? "no_contact" : "unavailable");
  addSample(values, "ambient_temp_c", ambientC);
  addSample(values, "humidity_pct", humidity);
  // Deliberately NO spo2_pct sample: calibration/clinical validation are missing.
  // The local API rejects any device-supplied spo2_pct even in LAB mode.

  String serialized;
  serializeJson(payload, serialized);
  WiFiClient client;
  HTTPClient http;
  http.setTimeout(500);
  if (!http.begin(client, String(MOI_API_BASE) + "/api/device/measurements")) return;
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", MOI_DEVICE_KEY);
  const int status = http.POST(serialized);
  if (status != HTTP_CODE_CREATED) {
    Serial.printf("Error de envío: HTTP %d\n", status);
    if (status == HTTP_CODE_CONFLICT) captureId = "";
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  Serial.println("Moímetro: PROTOTIPO DE BANCO, NO USO MÉDICO");
  Wire.begin(SDA_PIN, SCL_PIN);
  dht.begin();
  ds18b20.begin();
  ds18b20.setResolution(10);
  ds18b20.setWaitForConversion(false);

  maxReady = maxSensor.begin(Wire, I2C_SPEED_FAST);
  if (maxReady) {
    // 100 SPS with 4-sample hardware averaging -> 25 paired frames per sec.
    // Use both red and IR channels; green is not present in the MAX30102.
    maxSensor.setup(0x1F, 4, 2, 100, 411, 4096);
    maxSensor.setPulseAmplitudeGreen(0);
    oxygenEstimator.reset(moi::OpticalQuality::Collecting);
    const BaseType_t task = xTaskCreatePinnedToCore(
        opticalTask, "optical_ppg", 6144, nullptr, 2, nullptr, 1);
    if (task != pdPASS) {
      maxReady = false;
      Serial.println("ERROR: no se pudo iniciar la captura PPG.");
    } else {
      Serial.println("MAX30102: Rojo/IR 25 Hz. SpO2 experimental SIN validar.");
    }
  } else {
    Serial.println("MAX30102 no detectado: BPM no disponible.");
  }
  resetPulse();
  WiFi.mode(WIFI_STA);
  WiFi.begin(MOI_WIFI_SSID, MOI_WIFI_PASSWORD);
  wifiAt = millis();
}

void loop() {
  const unsigned long t = millis();
  readAmbient(t);
  readBody(t);
  keepWifi(t);

  // The optical task independently drains the FIFO while network I/O runs.
  // Timing, calibration and clinical accuracy still require physical tests.
  if (t - pollAt >= POLL_INTERVAL_MS) {
    pollAt = t;
    pollCapture();
  }
  if (t - uploadAt >= UPLOAD_INTERVAL_MS) {
    uploadAt = t;
    uploadReadings();
  }
}
