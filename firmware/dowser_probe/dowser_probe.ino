// Dowser Probe firmware: ESP32 / ESP32-S3 + potentiometer + SSD1306 OLED.
//
// Reads a potentiometer (stand-in for the MQ-4 gas sensor), shows the value on the OLED, and POSTs it
// to the Convex ingest endpoint once a second. Sending runs in its own task, so the screen and the pot
// stay smooth while the network works. Every sample is also printed to USB serial as one JSON line, so
// serial_bridge.py can post it if Wi-Fi fails at the venue.
//
// With the potentiometer (IS_REPLAY = true) value = raw ADC count (0..4095, knob position).
// With a real gas sensor (IS_REPLAY = false) value = raw minus an ambient baseline taken at boot.
// The reading is a RELATIVE value in ADC counts. It is not a methane concentration.

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "secrets.h"  // WIFI_SSID, WIFI_PASS, INGEST_URL, INGEST_TOKEN, DEVICE_ID

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

// ---- Display ----
constexpr int OLED_W = 128;
constexpr int OLED_H = 64;
constexpr uint8_t OLED_ADDR = 0x3C;  // some modules use 0x3D
Adafruit_SSD1306 display(OLED_W, OLED_H, &Wire, -1);

// ---- Behaviour ----
// Keep true while the input is a potentiometer: the app then shows a "Simulated" badge.
// NOTE: the backend's auto-confirm rule ignores this flag (3 values >= 1000 within 30 s on a paired
// candidate flips it to confirmed_leaking). Point INGEST_URL at the DEV deployment when you can.
constexpr bool IS_REPLAY = true;
constexpr bool USE_BASELINE = !IS_REPLAY;  // a pot has no "ambient"; only a real sensor needs a baseline
constexpr uint32_t SEND_INTERVAL_MS = 1000;
constexpr uint32_t DRAW_INTERVAL_MS = 100;
constexpr uint32_t BASELINE_MS = 3000;
constexpr int ADC_MAX = 4095;
constexpr int ELEVATED_AT = 300;
constexpr int HIGH_AT = 1000;  // same number as the backend's auto-confirm threshold (convex/readings.ts)

// Shared between the main loop (reads the pot, draws) and the network task (sends).
int baseline = 0;
int lastRaw = 0;
int lastValue = 0;
volatile int lastHttp = 0;  // 0 = nothing sent yet, <0 = transport error
volatile bool lastAutoConfirm = false;
char pairedId[48] = "";
uint32_t lastDraw = 0, lastWifiTry = 0, btnDownAt = 0;

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

static void connectWifi(uint32_t waitMs) {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  lastWifiTry = millis();
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < waitMs) {
    delay(250);
  }
}

// Two-colour OLED: the top 16 px are yellow, the rest is blue. Keep the yellow band to exactly two
// 8 px text lines (y = 0 and y = 8) so no text straddles the colour edge.
static void draw() {
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
  display.print(IS_REPLAY ? "SIMULATED: POT INPUT" : "LIVE SENSOR");

  // Blue area: big value on the left, state and raw count on the right.
  display.setTextSize(3);
  display.setCursor(0, 20);
  display.print(lastValue);
  display.setTextSize(1);

  const char* state = lastValue >= HIGH_AT ? "HIGH" : (lastValue >= ELEVATED_AT ? "ELEVATED" : "CLEAN");
  if (lastValue >= HIGH_AT) {
    display.fillRect(78, 20, 50, 10, SSD1306_WHITE);  // inverted box so HIGH stands out
    display.setTextColor(SSD1306_BLACK);
  }
  display.setCursor(79, 21);
  display.print(state);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(78, 34);
  display.printf("raw %d", lastRaw);

  display.drawRect(0, 46, OLED_W, 8, SSD1306_WHITE);
  int w = (int)((long)lastValue * (OLED_W - 2) / ADC_MAX);
  if (w > 0) display.fillRect(1, 47, w, 6, SSD1306_WHITE);

  display.setCursor(0, 56);
  int http = lastHttp;
  if (lastAutoConfirm) {
    display.print("SERVER AUTO-CONFIRM!");
  } else if (http == 201) {
    if (pairedId[0]) {
      display.printf("OK %s", pairedId);
    } else {
      display.print("OK - not paired");
    }
  } else if (http == 401) {
    display.print("BAD TOKEN (401)");
  } else if (http == -1) {
    display.print("no WiFi - not sent");
  } else if (http != 0) {
    display.printf("send fail %d", http);
  } else {
    display.print("waiting...");
  }
  display.display();
}

static void sendReading() {
  char body[160];
  int value = lastValue;
  int raw = lastRaw;
  snprintf(body, sizeof(body),
           "{\"deviceId\":\"%s\",\"value\":%d,\"raw\":%d,\"isReplay\":%s}",
           DEVICE_ID, value, raw, IS_REPLAY ? "true" : "false");
  Serial.println(body);  // one JSON line per sample: used by serial_bridge.py as the Wi-Fi fallback

  if (WiFi.status() != WL_CONNECTED) {
    lastHttp = -1;
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
  http.setTimeout(4000);
  if (!http.begin(client, INGEST_URL)) {
    lastHttp = -2;
    return;
  }
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Dowser-Token", INGEST_TOKEN);
  int code = http.POST((uint8_t*)body, strlen(body));
  lastHttp = code;
  if (code == 201) {
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

// Runs on its own task so network waits never freeze the screen or the pot reading.
static void netTask(void*) {
  for (;;) {
    sendReading();
    vTaskDelay(pdMS_TO_TICKS(SEND_INTERVAL_MS));
  }
}

void setup() {
  Serial.begin(115200);
  delay(300);
  pinMode(PIN_BTN, INPUT_PULLUP);
  analogReadResolution(12);
  analogSetPinAttenuation(PIN_POT, ADC_11db);

  Wire.begin(PIN_SDA, PIN_SCL);
  scanI2C();
  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    Serial.println("# OLED init failed (wrong address? see I2C scan above). Continuing without screen.");
  }
  showMessage("DOWSER PROBE", "Connecting WiFi...", WIFI_SSID);
  connectWifi(15000);
  Serial.printf("# WiFi status=%d (3=connected, 1=network not found, 4 or 6=found but could not join)\n", WiFi.status());
  if (WiFi.status() != WL_CONNECTED) {
    int n = WiFi.scanNetworks();
    Serial.printf("# %d networks visible (looking for \"%s\"):\n", n, WIFI_SSID);
    for (int i = 0; i < n; i++) {
      Serial.printf("#   %s (ch %d, %d dBm)\n", WiFi.SSID(i).c_str(), WiFi.channel(i), WiFi.RSSI(i));
    }
  }
  if (USE_BASELINE) takeBaseline();
  xTaskCreatePinnedToCore(netTask, "net", 12288, nullptr, 1, nullptr, 0);
}

void loop() {
  uint32_t now = millis();

  lastRaw = readRaw();
  lastValue = max(0, lastRaw - baseline);

  // Hold the button for 1 s to re-take the baseline (real sensor only).
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
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    lastWifiTry = now;
  }

  if (now - lastDraw >= DRAW_INTERVAL_MS) {
    lastDraw = now;
    draw();
  }
}
