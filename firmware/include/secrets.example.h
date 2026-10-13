#pragma once
// Copy to firmware/include/secrets.h and replace placeholders.
// NEVER commit secrets.h or put real patient data on this development server.
#define MOI_WIFI_SSID "YOUR_LOCAL_WIFI"
#define MOI_WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define MOI_API_BASE "http://192.168.1.10:8000"
#define MOI_DEVICE_ID "esp32-01"
// Must match MOIMETRO_DEVICE_KEY set on local server (32+ random characters).
#define MOI_DEVICE_KEY "REPLACE_WITH_RANDOM_SECRET_AT_LEAST_32_CHARS"
