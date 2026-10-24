# Dowser Probe (ESP32 firmware)

Handheld field probe for the Dowser app. It reads an analog input, shows it on a small OLED, and POSTs it once a second to the Convex ingest endpoint (`POST /ingest/reading`, see the root README).

> **The input is a potentiometer, not a gas sensor.** Readings are sent with `isReplay: true` so the app shows "Simulated". Values are ADC counts (0..4095), not methane concentrations. An uncalibrated MQ-4 would not change that.

Tested on: Elegoo ESP32-WROOM-32 (38-pin), 0.96" SSD1306 128x64 I2C OLED, 10k potentiometer, iPhone hotspot. Verified on the device: Wi-Fi connects and the server answers HTTP 201. The sketch also selects pins for an ESP32-S3, which is untested.

## Wiring (classic ESP32-WROOM-32)

| Part | Part pin | Board pin |
|---|---|---|
| Potentiometer | outer legs | 3V3 and GND |
| Potentiometer | middle leg (wiper) | D34 (ADC1) |
| OLED | VCC, GND | 3V3, GND |
| OLED | SDA, SCL | D21, D22 |
| Button (optional, real sensor only) | one side | D18, other side to GND |

ESP32-S3: pot GPIO4, SDA GPIO8, SCL GPIO9, button GPIO5. Pins are picked automatically by `CONFIG_IDF_TARGET_ESP32S3` in the sketch.

The pot must stay on an ADC1 pin: ADC2 does not work while Wi-Fi is on. Never use GPIO 6-11 on the classic ESP32 (flash).

## Flash it (Arduino IDE 2)

1. Boards Manager: install "esp32 by Espressif Systems". Library Manager: `Adafruit SSD1306` and `Adafruit GFX Library`.
2. Board: **ESP32 Dev Module**. Pick the `/dev/cu.usbserial-*` port. Hold BOOT while "Connecting..." if the upload stalls.
3. In `dowser_probe/`, copy `secrets.h.example` to `secrets.h` and fill in your hotspot and the ingest token. **Never commit `secrets.h`** (it is git-ignored; the repo is public).
4. iPhone hotspot: Settings > Personal Hotspot > Allow Others to Join, and turn on Maximize Compatibility (the ESP32 is 2.4 GHz only). Avoid an apostrophe in the phone name.
5. Upload, open the Serial Monitor at 115200, press EN.

## Reading the screen

- Yellow band: `DOWSER PROBE`, Wi-Fi status, mode (`SIMULATED: POT INPUT`).
- Big number: value. With the pot it is the raw knob position; with a real sensor (`IS_REPLAY = false`) it is raw minus a baseline taken at boot.
- `CLEAN` / `ELEVATED` (>= 300) / `HIGH` (>= 1000). 1000 is the backend's auto-confirm threshold (`convex/readings.ts`).
- Bottom line: `OK <candidate id>` once the phone has paired a candidate, `OK - not paired` if not, `BAD TOKEN (401)`, `no WiFi - not sent`, or `send fail <code>`.

## Read this before pairing a candidate

The backend flips a paired candidate to `confirmed_leaking` after 3 readings >= 1000 within 30 s, and it does **not** look at `isReplay`. Do not turn the knob up while a real candidate is paired on the production deployment. Use the dev deployment or fake candidates for tests.

## USB fallback

If Wi-Fi fails, the sketch also prints each sample as one JSON line on serial. `serial_bridge.py` forwards those lines to the endpoint:

```bash
pip install pyserial requests
export INGEST_URL=https://<deployment>.convex.site/ingest/reading
export INGEST_TOKEN=...
python firmware/serial_bridge.py /dev/cu.usbserial-XXXX
```
