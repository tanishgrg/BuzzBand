/*
 * Transit Keychain - Arduino Nano ESP32
 * Urgency → Color (per request):
 *   FAR (least urgent)    → RED    (D9)
 *   MIDDLE (approaching)  → YELLOW (D8)
 *   CLOSEST / ARRIVING    → GREEN  (D7)
 *
 * Wiring:
 * - Piezo buzzer  -> D6  (BUZZER_PIN)
 * - Green LED     -> D7  (GREEN_LED_PIN)
 * - Yellow LED    -> D8  (YELLOW_LED_PIN)
 * - Red LED       -> D9  (RED_LED_PIN)
 * - Status LED    -> D5  (STATUS_LED_PIN)
 *
 * Notes:
 * - Avoid D0/D1 (USB serial).
 * - Use 220Ω series resistors for LEDs.
 * - Passive buzzer (tone).
 */

#if defined(ARDUINO_ARCH_ESP32)
#include <driver/ledc.h>
static const int _TONE_LEDC_CHANNEL = 0;
static const int _TONE_LEDC_TIMER   = 0;

void toneESP32(int pin, unsigned int freq, unsigned long dur = 0) {
  ledcAttachPin(pin, _TONE_LEDC_CHANNEL);
  ledcSetup(_TONE_LEDC_CHANNEL, 2000 /*base*/, 10);
  ledcWriteTone(_TONE_LEDC_CHANNEL, freq);
  if (dur > 0) {
    delay(dur);
    ledcWriteTone(_TONE_LEDC_CHANNEL, 0);
  }
}
void noToneESP32(int pin) { (void)pin; ledcWriteTone(_TONE_LEDC_CHANNEL, 0); }
#define TONE(pin, f, d) toneESP32((pin), (f), (d))
#define NOTONE(pin)     noToneESP32((pin))
#define TONE_BLOCKS     1   // ESP32 helper: TONE with duration blocks & stops
#else
#define TONE(pin, f, d) tone((pin), (f), (d))
#define NOTONE(pin)     noTone((pin))
#define TONE_BLOCKS     0   // AVR tone(duration) is non-blocking
#endif

// ================== Pins (Nano ESP32) ==================
const int BUZZER_PIN      = 6;   // D6
const int GREEN_LED_PIN   = 7;   // D7 (closest/urgent)
const int YELLOW_LED_PIN  = 8;   // D8 (middle)
const int RED_LED_PIN     = 9;   // D9 (far)
const int STATUS_LED_PIN  = 5;   // D5 (status / debug)

// ================== Sound defaults ==================
const int FAR_FREQ        = 1500; // red
const int MID_FREQ        = 1300; // yellow
const int CLOSE_FREQ      = 1000; // green

// Pulse pattern (LED + buzzer in sync)
const unsigned PULSE_ON_MS  = 300;
const unsigned PULSE_OFF_MS = 200;

// ======= Feature switches =======
const bool ENABLE_DEST_ALERTS = false;  // keep destination ETA alerts disabled

// ======= Prototypes =======
void stopAll();
void statusPing();
void alertFlashing(int ledPin, int freq, unsigned total_ms);
void handleCommand(String command);

void setup() {
  Serial.begin(115200);

  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(GREEN_LED_PIN, OUTPUT);
  pinMode(YELLOW_LED_PIN, OUTPUT);
  pinMode(RED_LED_PIN, OUTPUT);
  pinMode(STATUS_LED_PIN, OUTPUT);

  stopAll();

  Serial.println("Transit Keychain Ready (Nano ESP32)");
  Serial.println("READY");

  // Self-test: RED (far) → YELLOW (mid) → GREEN (closest) → STATUS
  alertFlashing(RED_LED_PIN,   FAR_FREQ,   500);
  delay(150);
  alertFlashing(YELLOW_LED_PIN,MID_FREQ,   500);
  delay(150);
  alertFlashing(GREEN_LED_PIN, CLOSE_FREQ, 500);
  delay(150);
  digitalWrite(STATUS_LED_PIN, HIGH); TONE(BUZZER_PIN, 1200, 160);
  delay(200); digitalWrite(STATUS_LED_PIN, LOW);
}

void loop() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    command.toUpperCase();
    if (!command.length()) return;

    Serial.print("RX: "); Serial.println(command);
    handleCommand(command);
  }
}

// ================== Helpers ==================
// Play flashing LED + buzzer in-phase for total_ms.
// Ensures LED on-time == buzzer on-time (no extra hold).
void alertFlashing(int ledPin, int freq, unsigned total_ms) {
  unsigned elapsed = 0;
  while (elapsed < total_ms) {
    unsigned chunk = min(PULSE_ON_MS, total_ms - elapsed);

    // ON phase
    digitalWrite(ledPin, HIGH);
    if (TONE_BLOCKS) {
      TONE(BUZZER_PIN, freq, chunk);    // blocks and stops (ESP32)
    } else {
      TONE(BUZZER_PIN, freq, chunk);    // non-blocking (AVR)
      delay(chunk);
      NOTONE(BUZZER_PIN);
    }
    digitalWrite(ledPin, LOW);

    elapsed += chunk;
    if (elapsed >= total_ms) break;

    // OFF phase
    unsigned offChunk = min(PULSE_OFF_MS, total_ms - elapsed);
    delay(offChunk);
    elapsed += offChunk;
  }
}

void stopAll() {
  NOTONE(BUZZER_PIN);
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(YELLOW_LED_PIN, LOW);
  digitalWrite(RED_LED_PIN, LOW);
  digitalWrite(STATUS_LED_PIN, LOW);
}

void statusPing() {
  digitalWrite(STATUS_LED_PIN, HIGH);
  TONE(BUZZER_PIN, 1200, 120);
  delay(150);
  digitalWrite(STATUS_LED_PIN, LOW);
}

// ================== Command handling ==================
void handleCommand(String command) {
  // Generic buzzer: "BUZZ <freqHz> <durationMs>" (status LED blips only)
  if (command.startsWith("BUZZ")) {
    int s1 = command.indexOf(' ');
    int s2 = command.indexOf(' ', s1 + 1);
    if (s1 > 0 && s2 > s1) {
      int freq = command.substring(s1 + 1, s2).toInt();
      int dur  = command.substring(s2 + 1).toInt();
      statusPing();
#if TONE_BLOCKS
      TONE(BUZZER_PIN, freq, dur);
#else
      TONE(BUZZER_PIN, freq, dur);
      delay(dur);
      NOTONE(BUZZER_PIN);
#endif
      Serial.println("OK BUZZ");
    } else {
      Serial.println("ERR BUZZ SYNTAX");
    }
    return;
  }

  // -------- ORIGIN alerts (mapped to new color order) --------
  if (command == "ORIGIN_NEARBY")       { alertFlashing(RED_LED_PIN,    FAR_FREQ,   3000);  Serial.println("OK ORIGIN_NEARBY");   return; } // far → RED
  if (command == "ORIGIN_APPROACH")     { alertFlashing(YELLOW_LED_PIN, MID_FREQ,   5000);  Serial.println("OK ORIGIN_APPROACH"); return; } // mid → YELLOW
  if (command == "ORIGIN_STOP")         { alertFlashing(GREEN_LED_PIN,  CLOSE_FREQ, 8000);  Serial.println("OK ORIGIN_STOP");     return; } // closest → GREEN

  // -------- DESTINATION alerts (no-op unless enabled) --------
  if (command == "DEST_NEARBY" || command == "DEST_APPROACH" || command == "DEST_STOP") {
    if (ENABLE_DEST_ALERTS) {
      if (command == "DEST_NEARBY")       { alertFlashing(RED_LED_PIN,    FAR_FREQ,   3000); Serial.println("OK DEST_NEARBY"); }
      else if (command == "DEST_APPROACH"){ alertFlashing(YELLOW_LED_PIN, MID_FREQ,   5000); Serial.println("OK DEST_APPROACH"); }
      else if (command == "DEST_STOP")    { alertFlashing(GREEN_LED_PIN,  CLOSE_FREQ, 8000); Serial.println("OK DEST_STOP"); }
    } else {
      Serial.println("OK DEST_IGNORED");
    }
    return;
  }

  // -------- Utilities --------
  if (command == "IDLE")              { stopAll();        Serial.println("OK IDLE"); return; }
  if (command == "URGENT")            { alertFlashing(GREEN_LED_PIN, 2500, 2000); Serial.println("OK URGENT"); return; } // quick intense green strobe
  if (command == "STATUS_UPDATE")     { statusPing();     Serial.println("OK STATUS"); return; }
  if (command == "LED_STATUS_ORIGIN") { digitalWrite(GREEN_LED_PIN, HIGH); delay(300); digitalWrite(GREEN_LED_PIN, LOW); Serial.println("OK LED_ORIGIN"); return; }
  if (command == "LED_STATUS_DEST")   { Serial.println(ENABLE_DEST_ALERTS ? "OK LED_DEST" : "OK LED_DEST_IGNORED"); return; }
  if (command == "LED_STATUS_NONE")   { stopAll();        Serial.println("OK LED_NONE"); return; }
  if (command == "PING")              { Serial.println("PONG"); return; }

  Serial.println("ERR UNKNOWN");
}
