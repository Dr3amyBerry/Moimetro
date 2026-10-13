/*
 * Moímetro ESP32 firmware PROTOTYPE
 *
 * Sensors: DHT11 on GPIO18; DS18B20 on GPIO4;
 * MAX30102 I2C SDA21 / SCL22.
 *
 * No SpO2 is calculated: do not fabricate oxygen saturation values.
 * The local API rejects device SpO2 until clinical and technical validation.
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

void readPulse() {
  if (!maxReady) return;
  const long ir = maxSensor.getIR();
  if (ir < FINGER_IR_MIN) {
    fingerPresent = false;
    resetPulse();
    return;
  }
  fingerPresent = true;
  // If no valid beat has been detected for several seconds, invalidate old BPM.
  if (lastBeat != 0 && millis() - lastBeat > 4000) resetPulse();
  if (!checkForBeat(ir)) return;
  const uint32_t instant = millis();
  if (lastBeat != 0) {
    const uint32_t duration = instant - lastBeat;
    const float candidate = duration ? 60000.0f / duration : 0;
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
  addSample(values, "body_temp_c", bodyC);
  addSample(values, "pulse_bpm", bpm, maxReady && !fingerPresent ? "no_contact" : "unavailable");
  addSample(values, "ambient_temp_c", ambientC);
  addSample(values, "humidity_pct", humidity);
  // Deliberately NO SpO2 value: it is not measured by this firmware.

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
    maxSensor.setup();
    maxSensor.setPulseAmplitudeRed(0x0A);
    maxSensor.setPulseAmplitudeGreen(0);
    Serial.println("MAX30102 detectado.");
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
  readPulse(); // sample as frequently as possible
  readAmbient(t);
  readBody(t);
  keepWifi(t);

  // HTTP is time-bounded but still briefly blocks optical sampling.
  // Firmware timing and pulse accuracy require physical testing.
  if (t - pollAt >= POLL_INTERVAL_MS) {
    pollAt = t;
    pollCapture();
  }
  if (t - uploadAt >= UPLOAD_INTERVAL_MS) {
    uploadAt = t;
    uploadReadings();
  }
}
