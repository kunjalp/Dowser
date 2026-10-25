# Dowser Probe (ESP32 firmware)

Handheld field probe for the Dowser app. It reads an analog input, shows it on a small OLED, and sends it to the Convex ingest endpoint (`POST /ingest/reading`, see the root README).

> **The input is a potentiometer, not a gas sensor.** Readings are sent with `isReplay: true`, so the app shows "Simulated". Values are ADC counts (0 to 4095), not methane concentrations. An uncalibrated sensor would not change that.

Tested on an Elegoo ESP32-WROOM-32 (38-pin), a 0.96" SSD1306 128x64 I2C OLED and a 10k potentiometer. On the device, Wi-Fi joins, the server answers HTTP 201, and the readings appear in the app. That testing used an iPhone hotspot. The venue Wi-Fi path is the same code. The ESP32-S3 pin selection is in the sketch but untested.

## Wiring (classic ESP32-WROOM-32)

| Part | Part pin | Board pin |
|---|---|---|
| Potentiometer | outer legs | 3V3 and GND |
| Potentiometer | middle leg (wiper) | D34 (ADC1) |
| OLED | VCC, GND | 3V3, GND |
| OLED | SDA, SCL | D21, D22 |

Keep the pot on an ADC1 pin: ADC2 does not work while Wi-Fi is on. Never use GPIO 6 to 11 on the classic ESP32 (flash). ESP32-S3: pot GPIO4, SDA GPIO8, SCL GPIO9.

## Flash it (Arduino IDE 2)

1. Boards Manager: install "esp32 by Espressif Systems". Library Manager: `Adafruit SSD1306` and `Adafruit GFX Library`.
2. Board: **ESP32 Dev Module**. Pick the `/dev/cu.usbserial-*` port. Hold BOOT while "Connecting..." shows if the upload stalls.
3. In `dowser_probe/`, copy `secrets.h.example` to `secrets.h` and fill it in. **Never commit `secrets.h`**: it is git-ignored and the repo is public.
4. Upload, open the Serial Monitor at 115200, press EN.

If the Serial Monitor shows garbled characters, the speed is wrong: set 115200 baud.

## Wi-Fi at the venue

- **Password network:** set `WIFI_SSID` and `WIFI_PASS` in `secrets.h`. No code change.
- **Open network:** set `WIFI_PASS` to `""`.
- **2.4 GHz only.** The ESP32 cannot see 5 GHz networks. If the venue has two names, use the 2.4 GHz one.
- **Sign-in page (captive portal):** the board cannot sign in. The OLED shows `login page? HTTP 302`. Ask the organizers to allow the board's MAC address (the serial log prints it), or use another network.
- **WPA2-Enterprise (username and password login):** define `WIFI_USE_ENTERPRISE` and the three `WIFI_EAP_*` values in `secrets.h`. This compiles but is untested on a real enterprise network.

At boot the serial log prints the MAC address, whether the join worked, and the IP address and signal strength. If the join fails, it lists the networks the board can see.

## Reading the screen

- **Yellow header:** `DOWSER PROBE`, Wi-Fi status, and the mode label (`SIMULATED: POT INPUT`).
- **Big number:** the live value, 0 to 4095, with the raw count beside it.
- **Status word:** `CLEAN` below 300, `ELEVATED` from 300, `HIGH` from 1000. 1000 is the backend's auto-confirm threshold (`convex/readings.ts`).
- **Bar:** the value as a share of the full scale.
- **Bottom line:** `APP <value>  paired` or `no pair` is the last value the server confirmed, which is what the app has. Errors show here: `BAD TOKEN (401)`, `no WiFi - not sent`, `login page? HTTP <code>`, `send fail <code>`.

The screen redraws up to 20 times a second and never waits on the network. A separate task sends a reading when the value moves by 8 counts or more (at most about six a second), and at least once a second when it is still.

## Read this before pairing a candidate

By default the exact value is sent. The backend marks a paired candidate `confirmed_leaking` after eight readings of 1000 or more within ten seconds, and it does **not** look at `isReplay`. Pair only the agreed demo well. To cap what is sent at 990 instead, set `CAP_HIGH_VALUES = true` in the sketch; holding the on-board BOOT button for 2 seconds then arms real high values until the next reset.

## USB fallback

The sketch also prints each sample as one JSON line on serial. `serial_bridge.py` forwards those lines to the endpoint if Wi-Fi fails. It has not been tested with this version of the sketch.

```bash
pip install pyserial requests
export INGEST_URL=https://<deployment>.convex.site/ingest/reading
export INGEST_TOKEN=...
python firmware/serial_bridge.py /dev/cu.usbserial-XXXX
```
