// Dowser Probe firmware: ESP32 / ESP32-S3 + potentiometer + SSD1306 OLED.
//
// Reads a potentiometer (stand-in for the MQ-4 gas sensor). The OLED shows the LIVE value and redraws
// about 20 times a second, independent of the network. A separate task POSTs the freshest value to the
// Convex ingest endpoint as fast as the server answers: immediately when the value moved by SEND_DELTA or
// more (but never more often than SEND_MIN_GAP_MS), and at least every HEARTBEAT_MS when it is still.
// The bottom line of the OLED shows the last value the server confirmed (APP n), so you can see exactly
// what the app has and how far it lags (about one network round trip).
// Every sample is also printed to USB serial as one JSON line, so serial_bridge.py can post it if Wi-Fi
// fails at the venue.
//
// With the potentiometer (IS_REPLAY = true) value = raw ADC count (0..4095, knob position).
// With a real gas sensor (IS_REPLAY = false) value = raw minus an ambient baseline taken at boot.
// The reading is a RELATIVE value in ADC counts. It is not a methane concentration.
//
// WARNING: the backend marks a paired candidate "confirmed_leaking" after 3 values >= 1000 within 30 s
// (convex/readings.ts) and ignores isReplay. With CAP_HIGH_VALUES = false (the default now) the exact
// value is sent, so a high knob position WILL flip a paired candidate. Pair only fake or dev candidates
// while testing. Set CAP_HIGH_VALUES = true to send at most SERVER_CAP unless you hold the BOOT button
// for 2 s to arm real high values; a reset disarms it again.

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "secrets.h"  // WIFI_SSID, WIFI_PASS, INGEST_URL, INGEST_TOKEN, DEVICE_ID
// Wi-Fi: put the venue network in secrets.h. A password network or an open network needs no code change.
// For WPA2-Enterprise (username + password login) define WIFI_USE_ENTERPRISE in secrets.h; see secrets.h.example.

// ---- Pins: chosen by chip. Pot MUST be on an ADC1 pin (ADC2 stops working when Wi-Fi is on). ----
#if CONFIG_IDF_TARGET_ESP32S3
// ESP32-S3 (e.g. N16R8): avoid GPIO 19/20 (USB), 35-37 (PSRAM), 0/3/45/46 (boot pins).
constexpr uint8_t PIN_POT = 4;   // ADC1
constexpr uint8_t PIN_SDA = 8;
constexpr uint8_t PIN_SCL = 9;
constexpr uint8_t PIN_BTN = 5;   // optional: hold 1 s to re-take the baseline (real sensor only)
#else
// Classic ESP32-WROOM-32 (Elegoo 38-pin dev board). Never use GPIO 6-11 (flash).
constexpr uint8_t PIN_POT = 34;  // ADC1, input-only: fine for a pot wiper
constexpr uint8_t PIN_SDA = 21;  // default I2C
constexpr uint8_t PIN_SCL = 22;  // default I2C
constexpr uint8_t PIN_BTN = 18;  // optional: hold 1 s to re-take the baseline (real sensor only)
#endif
constexpr uint8_t PIN_BOOT = 0;  // on-board BOOT button (no wiring): arm/disarm when CAP_HIGH_VALUES is on

// ---- Display ----
constexpr int OLED_W = 128;
constexpr int OLED_H = 64;
constexpr uint8_t OLED_ADDR = 0x3C;  // some modules use 0x3D
Adafruit_SSD1306 display(OLED_W, OLED_H, &Wire, -1);

// ---- Behaviour ----
// Keep true while the input is a potentiometer: the app then shows a "Simulated" badge.
constexpr bool IS_REPLAY = true;
constexpr bool USE_BASELINE = !IS_REPLAY;  // a pot has no "ambient"; only a real sensor needs a baseline
constexpr uint32_t SAMPLE_WINDOW_MS = 50;   // the live value is the average of the last 50 ms
constexpr uint32_t DRAW_INTERVAL_MS = 50;   // OLED redraw (~20 per second)
constexpr uint32_t SEND_MIN_GAP_MS = 150;   // never POST more often than this (limits database rows)
constexpr uint32_t HEARTBEAT_MS = 1000;     // POST at least this often, even if the value is unchanged
constexpr int SEND_DELTA = 8;               // POST early when the value moved by this many counts
constexpr uint32_t BASELINE_MS = 3000;
constexpr uint32_t ARM_HOLD_MS = 2000;
constexpr int ADC_MAX = 4095;
constexpr int ELEVATED_AT = 300;
constexpr int HIGH_AT = 1000;             // same number as the backend's auto-confirm threshold
constexpr int SERVER_CAP = HIGH_AT - 10;  // largest value sent while capped
// false = send the exact value (OLED and app always agree). true = cap at SERVER_CAP unless armed.
constexpr bool CAP_HIGH_VALUES = false;
constexpr int NO_WIFI = -100;  // lastHttp marker for "Wi-Fi is down" (HTTPClient errors are -1..-11)

// Live values, computed in loop() and read by draw() and the network task.
int baseline = 0;
int lastRaw = 0;    // average raw of the latest window
int lastValue = 0;  // live value (OLED shows this)

// Network task results.
volatile int sentReal = -10000;  // live value at the time of the last POST attempt (drives "moved by")
volatile int ackedValue = 0;     // last value the server confirmed with 201: what the app has
volatile int lastHttp = 0;       // 0 = nothing sent yet, NO_WIFI = Wi-Fi down, other <0 = transport error
volatile bool lastAutoConfirm = false;
volatile bool armed = false;     // only matters when CAP_HIGH_VALUES is true; false after every reset
char pairedId[48] = "";
uint32_t lastDraw = 0, lastWifiTry = 0, btnDownAt = 0, bootDownAt = 0;
bool bootHandled = false;

static int readRaw() {
  uint32_t sum = 0;
  for (int i = 0; i < 16; i++) {
    sum += analogRead(PIN_POT);
    delayMicroseconds(200);
  }
  return (int)(sum / 16);
}

static void showMessage(const char* l1, const char* l2 = "", const char* l3 = "") {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setTextWrap(false);
  display.setCursor(0, 0);
  display.println(l1);
  display.setCursor(0, 20);
  display.println(l2);
  display.setCursor(0, 32);
  display.println(l3);
  display.display();
}

static void scanI2C() {
  Serial.println("# I2C scan:");
  int found = 0;
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      Serial.printf("#   device at 0x%02X\n", a);
      found++;
    }
  }
  if (!found) Serial.println("#   none found: check SDA/SCL/VCC/GND wiring");
}

static void takeBaseline() {
  showMessage("BASELINE", "Sensor in clean air", "and hold still...");
  uint32_t t0 = millis(), n = 0, sum = 0;
  while (millis() - t0 < BASELINE_MS) {
    sum += readRaw();
    n++;
    delay(20);
  }
  baseline = n ? (int)(sum / n) : 0;
  Serial.printf("# baseline = %d\n", baseline);
}

static void beginWifi() {
#ifdef WIFI_USE_ENTERPRISE
  // WPA2-Enterprise (PEAP / MSCHAPv2). Compiles, but has not been tested on a real enterprise network.
  WiFi.begin(WIFI_SSID, WPA2_AUTH_PEAP, WIFI_EAP_IDENTITY, WIFI_EAP_USERNAME, WIFI_EAP_PASSWORD);
#else
  WiFi.begin(WIFI_SSID, WIFI_PASS);  // WPA2-Personal, or an open network when WIFI_PASS is ""
#endif
}

static void connectWifi(uint32_t waitMs) {
  WiFi.mode(WIFI_STA);
  beginWifi();
  lastWifiTry = millis();
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < waitMs) {
    delay(250);
  }
}

// Two-colour OLED: the top 16 px are yellow, the rest is blue. Keep the yellow band to exactly two
// 8 px text lines (y = 0 and y = 8) so no text straddles the colour edge.
static void draw() {
  int value = lastValue;  // LIVE value
  int raw = lastRaw;
  bool capNow = CAP_HIGH_VALUES && !armed && value >= HIGH_AT;

  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextWrap(false);  // clip instead of wrapping stray characters onto the next line
  display.setTextSize(1);

  // Yellow band
  display.setCursor(0, 0);
  display.print("DOWSER PROBE");
  display.setCursor(84, 0);
  display.print(WiFi.status() == WL_CONNECTED ? "WiFi OK" : "no WiFi");
  display.setCursor(0, 8);
  display.print((CAP_HIGH_VALUES && armed) ? "SIMULATED - ARMED" : (IS_REPLAY ? "SIMULATED: POT INPUT" : "LIVE SENSOR"));

  // Blue area: big value on the left, state and raw count on the right.
  display.setTextSize(3);
  display.setCursor(0, 20);
  display.print(value);
  display.setTextSize(1);

  const char* state = value >= HIGH_AT ? "HIGH" : (value >= ELEVATED_AT ? "ELEVATED" : "CLEAN");
  if (value >= HIGH_AT) {
    display.fillRect(78, 20, 50, 10, SSD1306_WHITE);  // inverted box so HIGH stands out
    display.setTextColor(SSD1306_BLACK);
  }
  display.setCursor(79, 21);
  display.print(state);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(78, 34);
  display.printf("raw %d", raw);

  display.drawRect(0, 46, OLED_W, 8, SSD1306_WHITE);
  int w = (int)((long)value * (OLED_W - 2) / ADC_MAX);
  if (w > 0) display.fillRect(1, 47, w, 6, SSD1306_WHITE);

  // Bottom line: what the app has (last value the server confirmed) or what is wrong.
  display.setCursor(0, 56);
  int http = lastHttp;
  if (capNow) {
    display.printf("CAPPED  APP %d", (int)ackedValue);
  } else if (lastAutoConfirm) {
    display.print("SERVER AUTO-CONFIRM!");
  } else if (http == 401) {
    display.print("BAD TOKEN (401)");
  } else if (http == NO_WIFI) {
    display.print("no WiFi - not sent");
  } else if (http == 0) {
    display.print("waiting...");
  } else if (http == 200 || (http >= 300 && http < 400)) {
    display.printf("login page? HTTP %d", http);  // a sign-in page is intercepting the request
  } else if (http != 201) {
    display.printf("APP %d  send fail %d", (int)ackedValue, http);
  } else {
    display.printf("APP %d  %s", (int)ackedValue, pairedId[0] ? "paired" : "no pair");
  }
  display.display();
}

static void sendReading() {
  int raw = lastRaw;     // snapshot of the freshest live window
  int real = lastValue;
  int value = real;
  if (CAP_HIGH_VALUES && !armed && value >= HIGH_AT) value = SERVER_CAP;  // optional guard
  sentReal = real;

  char body[160];
  snprintf(body, sizeof(body),
           "{\"deviceId\":\"%s\",\"value\":%d,\"raw\":%d,\"isReplay\":%s}",
           DEVICE_ID, value, raw, IS_REPLAY ? "true" : "false");
  Serial.println(body);  // one JSON line per sample: used by serial_bridge.py as the Wi-Fi fallback

  if (WiFi.status() != WL_CONNECTED) {
    lastHttp = NO_WIFI;
    return;
  }

  static WiFiClientSecure client;  // kept between sends so the HTTPS connection can be reused
  static bool clientReady = false;
  if (!clientReady) {
    client.setInsecure();  // demo only: skips certificate checks (kept as noted in the team README)
    clientReady = true;
  }

  HTTPClient http;
  http.setReuse(true);
  http.setTimeout(1500);
  if (!http.begin(client, INGEST_URL)) {
    lastHttp = -2;
    return;
  }
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Dowser-Token", INGEST_TOKEN);
  int code = http.POST((uint8_t*)body, strlen(body));
  lastHttp = code;
  if (code == 201) {
    ackedValue = value;
    String resp = http.getString();
    char tmp[sizeof(pairedId)] = "";
    int k = resp.indexOf("\"candidateId\":\"");
    if (k >= 0) {
      k += 15;
      int e = resp.indexOf('"', k);
      if (e > k) resp.substring(k, e).toCharArray(tmp, sizeof(tmp));
    }
    strncpy(pairedId, tmp, sizeof(pairedId) - 1);
    pairedId[sizeof(pairedId) - 1] = 0;
    lastAutoConfirm = resp.indexOf("\"autoConfirmed\":true") >= 0;
  }
  Serial.printf("# POST -> %d paired=%s\n", code, pairedId);
  http.end();
  if (code < 0) client.stop();  // drop a broken connection so the next send starts fresh
}

// Runs on its own task so network waits never freeze the screen or the pot reading. Always sends the
// freshest live value: right away when it moved, otherwise once per HEARTBEAT_MS.
static void netTask(void*) {
  uint32_t lastSentAt = 0;
  for (;;) {
    uint32_t now = millis();
    int moved = abs(lastValue - (int)sentReal);
    bool due = (lastSentAt == 0) || (moved >= SEND_DELTA) || (now - lastSentAt >= HEARTBEAT_MS);
    if (due && (lastSentAt == 0 || now - lastSentAt >= SEND_MIN_GAP_MS)) {
      sendReading();
      lastSentAt = millis();
      if (lastHttp < 0) vTaskDelay(pdMS_TO_TICKS(300));  // brief back-off after a failure
    }
    vTaskDelay(pdMS_TO_TICKS(5));
  }
}

void setup() {
  Serial.begin(115200);
  delay(300);
  pinMode(PIN_BTN, INPUT_PULLUP);
  pinMode(PIN_BOOT, INPUT_PULLUP);
  analogReadResolution(12);
  analogSetPinAttenuation(PIN_POT, ADC_11db);

  Wire.begin(PIN_SDA, PIN_SCL);
  Wire.setClock(400000);  // faster screen refresh (SSD1306 supports 400 kHz)
  scanI2C();
  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    Serial.println("# OLED init failed (wrong address? see I2C scan above). Continuing without screen.");
  }
  showMessage("DOWSER PROBE", "Connecting WiFi...", WIFI_SSID);
  connectWifi(20000);  // venue networks can be slow to hand out an address
  Serial.printf("# MAC address: %s (some venues ask for it to allow the board)\n", WiFi.macAddress().c_str());
  Serial.printf("# WiFi status=%d (3=connected, 1=network not found, 4 or 6=found but could not join)\n", WiFi.status());
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("# joined \"%s\"  ip %s  %d dBm  channel %d\n", WIFI_SSID, WiFi.localIP().toString().c_str(), WiFi.RSSI(), WiFi.channel());
  } else {
    Serial.println("# note: the ESP32 sees 2.4 GHz networks only. If the venue has separate 2.4 and 5 GHz names, use the 2.4 GHz one.");
  }
  if (WiFi.status() != WL_CONNECTED) {
    int n = WiFi.scanNetworks();
    Serial.printf("# %d networks visible (looking for \"%s\"):\n", n, WIFI_SSID);
    for (int i = 0; i < n; i++) {
      Serial.printf("#   %s (ch %d, %d dBm)\n", WiFi.SSID(i).c_str(), WiFi.channel(i), WiFi.RSSI(i));
    }
  }
  if (USE_BASELINE) takeBaseline();
  if (CAP_HIGH_VALUES) {
    Serial.printf("# live OLED; POST on change (>= %d) or every %u ms. Cap ON: values >= %d are sent as %d. Hold BOOT 2 s to arm.\n",
                  SEND_DELTA, (unsigned)HEARTBEAT_MS, HIGH_AT, SERVER_CAP);
  } else {
    Serial.printf("# live OLED; POST on change (>= %d) or every %u ms. Cap OFF: the exact value is sent. Values >= %d can auto-confirm a PAIRED candidate.\n",
                  SEND_DELTA, (unsigned)HEARTBEAT_MS, HIGH_AT);
  }
  xTaskCreatePinnedToCore(netTask, "net", 12288, nullptr, 1, nullptr, 0);
}

void loop() {
  static uint32_t accSum = 0, accN = 0, windowStart = 0;
  uint32_t now = millis();

  // Average everything read in the current window and publish it as the live value.
  accSum += readRaw();
  accN++;
  if (now - windowStart >= SAMPLE_WINDOW_MS) {
    windowStart = now;
    lastRaw = accN ? (int)(accSum / accN) : 0;
    lastValue = max(0, lastRaw - baseline);
    accSum = 0;
    accN = 0;
  }

  // Only when the cap is on: hold the on-board BOOT button for 2 s to arm / disarm sending values >= HIGH_AT.
  if (CAP_HIGH_VALUES && digitalRead(PIN_BOOT) == LOW) {
    if (!bootDownAt) bootDownAt = now;
    if (!bootHandled && now - bootDownAt > ARM_HOLD_MS) {
      armed = !armed;
      bootHandled = true;
      Serial.printf("# armed = %d (%s)\n", armed ? 1 : 0, armed ? "real high values WILL be sent" : "high values are capped");
    }
  } else {
    bootDownAt = 0;
    bootHandled = false;
  }

  // Hold the optional button for 1 s to re-take the baseline (real sensor only).
  if (USE_BASELINE && digitalRead(PIN_BTN) == LOW) {
    if (!btnDownAt) btnDownAt = now;
    if (now - btnDownAt > 1000) {
      takeBaseline();
      btnDownAt = 0;
    }
  } else {
    btnDownAt = 0;
  }

  if (WiFi.status() != WL_CONNECTED && now - lastWifiTry > 5000) {
    WiFi.disconnect();
    beginWifi();
    lastWifiTry = now;
  }

  if (now - lastDraw >= DRAW_INTERVAL_MS) {
    lastDraw = now;
    draw();
  }
}
