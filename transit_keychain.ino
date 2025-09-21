/*
 * Transit Keychain - Arduino Nano ESP32
 *
 * Wiring (Arduino Nano ESP32):
 * - Piezo buzzer  -> D6  (BUZZER_PIN)
 * - Green LED     -> D7  (GREEN_LED_PIN)  (Destination / Nearby)
 * - Red LED       -> D8  (RED_LED_PIN)    (Stop)
 * - Blue LED      -> D9  (BLUE_LED_PIN)   (Status)
 *
 * Notes:
 * - Avoid D0/D1 (USB serial).
 * - Use 220Ω series resistors for LEDs.
 * - This drives a PASSIVE buzzer (via tone).
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
 void noToneESP32(int pin) {
   (void)pin;
   ledcWriteTone(_TONE_LEDC_CHANNEL, 0);
 }
 #define TONE(pin, f, d) toneESP32((pin), (f), (d))
 #define NOTONE(pin)     noToneESP32((pin))
 #else
 #define TONE(pin, f, d) tone((pin), (f), (d))
 #define NOTONE(pin)     noTone((pin))
 #endif
 
 // ================== Pins (Nano ESP32) ==================
 const int BUZZER_PIN     = 6;   // D6
 const int GREEN_LED_PIN  = 7;   // D7
 const int RED_LED_PIN    = 8;   // D8
 const int BLUE_LED_PIN   = 9;   // D9
 
 // ================== Defaults ==================
 const int NEARBY_FREQ   = 1500;
 const int APPROACH_FREQ = 1300;
 const int STOP_FREQ     = 1000;
 
 void simpleAlert(int ledPin, int frequency, int duration);
 void stopAlert();
 void urgentAlert();
 void statusUpdate();
 void ledStatusOrigin();
 void ledStatusDest();
 void ledStatusNone();
 void handleCommand(String command);
 
 void setup() {
   // Match Python baud: 115200
   Serial.begin(115200);
 
   pinMode(BUZZER_PIN, OUTPUT);
   pinMode(RED_LED_PIN, OUTPUT);
   pinMode(GREEN_LED_PIN, OUTPUT);
   pinMode(BLUE_LED_PIN, OUTPUT);
 
   digitalWrite(RED_LED_PIN, LOW);
   digitalWrite(GREEN_LED_PIN, LOW);
   digitalWrite(BLUE_LED_PIN, LOW);
 
   // Small startup demo + READY line so Python can wait for it
   Serial.println("Transit Keychain Ready (Nano ESP32)");
   Serial.println("READY");
   // Quick self-test
   digitalWrite(GREEN_LED_PIN, HIGH);  TONE(BUZZER_PIN, 1500, 200); delay(250);
   digitalWrite(GREEN_LED_PIN, LOW);   NOTONE(BUZZER_PIN);          delay(150);
   digitalWrite(RED_LED_PIN, HIGH);    TONE(BUZZER_PIN, 1000, 200); delay(250);
   digitalWrite(RED_LED_PIN, LOW);     NOTONE(BUZZER_PIN);          delay(150);
   digitalWrite(BLUE_LED_PIN, HIGH);   TONE(BUZZER_PIN, 1200, 200); delay(250);
   digitalWrite(BLUE_LED_PIN, LOW);    NOTONE(BUZZER_PIN);
 }
 
 void loop() {
   if (Serial.available()) {
     String command = Serial.readStringUntil('\n');
     command.trim();
     command.toUpperCase();
 
     if (command.length() == 0) return;
     Serial.print("RX: ");
     Serial.println(command);
 
     handleCommand(command);
   }
 }
 
 // ================== Command handling ==================
 void handleCommand(String command) {
   // Generic buzzer: "BUZZ <freqHz> <durationMs>"
   if (command.startsWith("BUZZ")) {
     // Split tokens
     int firstSpace = command.indexOf(' ');
     int secondSpace = command.indexOf(' ', firstSpace + 1);
     if (firstSpace > 0 && secondSpace > firstSpace) {
       int freq = command.substring(firstSpace + 1, secondSpace).toInt();
       int dur  = command.substring(secondSpace + 1).toInt();
       digitalWrite(BLUE_LED_PIN, HIGH);
       TONE(BUZZER_PIN, freq, dur);
       NOTONE(BUZZER_PIN);
       digitalWrite(BLUE_LED_PIN, LOW);
       Serial.println("OK BUZZ");
     } else {
       Serial.println("ERR BUZZ SYNTAX");
     }
     return;
   }
 
   // High-level alerts
   if (command == "ORIGIN_NEARBY")      { simpleAlert(GREEN_LED_PIN, NEARBY_FREQ,   3000); Serial.println("OK ORIGIN_NEARBY"); }
   else if (command == "ORIGIN_APPROACH"){ simpleAlert(GREEN_LED_PIN, APPROACH_FREQ, 5000); Serial.println("OK ORIGIN_APPROACH"); }
   else if (command == "ORIGIN_STOP")   { simpleAlert(RED_LED_PIN,   STOP_FREQ,     8000); Serial.println("OK ORIGIN_STOP"); }
   else if (command == "DEST_NEARBY")   { simpleAlert(GREEN_LED_PIN, NEARBY_FREQ,   3000); Serial.println("OK DEST_NEARBY"); }
   else if (command == "DEST_APPROACH") { simpleAlert(GREEN_LED_PIN, APPROACH_FREQ, 5000); Serial.println("OK DEST_APPROACH"); }
   else if (command == "DEST_STOP")     { simpleAlert(RED_LED_PIN,   STOP_FREQ,     8000); Serial.println("OK DEST_STOP"); }
   else if (command == "IDLE")          { stopAlert();                               Serial.println("OK IDLE"); }
   else if (command == "URGENT")        { urgentAlert();                             Serial.println("OK URGENT"); }
   else if (command == "STATUS_UPDATE") { statusUpdate();                            Serial.println("OK STATUS"); }
   else if (command == "LED_STATUS_ORIGIN") { ledStatusOrigin();                     Serial.println("OK LED_ORIGIN"); }
   else if (command == "LED_STATUS_DEST")   { ledStatusDest();                       Serial.println("OK LED_DEST"); }
   else if (command == "LED_STATUS_NONE")   { ledStatusNone();                       Serial.println("OK LED_NONE"); }
   else if (command == "PING")              { Serial.println("PONG"); }
   else {
     Serial.println("ERR UNKNOWN");
   }
 }
 
 // ================== Alert helpers ==================
 void simpleAlert(int ledPin, int frequency, int duration) {
   digitalWrite(ledPin, HIGH);
   digitalWrite(BLUE_LED_PIN, HIGH);
   TONE(BUZZER_PIN, frequency, duration);
   delay(duration);
   digitalWrite(ledPin, LOW);
   digitalWrite(BLUE_LED_PIN, LOW);
   NOTONE(BUZZER_PIN);
 }
 
 void stopAlert() {
   NOTONE(BUZZER_PIN);
   digitalWrite(RED_LED_PIN, LOW);
   digitalWrite(GREEN_LED_PIN, LOW);
   digitalWrite(BLUE_LED_PIN, LOW);
 }
 
 void urgentAlert() {
   for (int i = 0; i < 6; i++) {
     digitalWrite(RED_LED_PIN, HIGH);
     digitalWrite(GREEN_LED_PIN, HIGH);
     digitalWrite(BLUE_LED_PIN, HIGH);
     TONE(BUZZER_PIN, 2500, 300);
     delay(150);
     digitalWrite(RED_LED_PIN, LOW);
     digitalWrite(GREEN_LED_PIN, LOW);
     digitalWrite(BLUE_LED_PIN, LOW);
     NOTONE(BUZZER_PIN);
     delay(150);
   }
 }
 
 void statusUpdate() {
   digitalWrite(BLUE_LED_PIN, HIGH);
   TONE(BUZZER_PIN, 1200, 200);
   delay(240);
   digitalWrite(BLUE_LED_PIN, LOW);
   NOTONE(BUZZER_PIN);
 }
 
 void ledStatusOrigin() {
   digitalWrite(GREEN_LED_PIN, HIGH);
   digitalWrite(BLUE_LED_PIN, HIGH);
   delay(500);
   digitalWrite(GREEN_LED_PIN, LOW);
   digitalWrite(BLUE_LED_PIN, LOW);
 }
 
 void ledStatusDest() {
   digitalWrite(GREEN_LED_PIN, HIGH);
   digitalWrite(BLUE_LED_PIN, HIGH);
   delay(500);
   digitalWrite(GREEN_LED_PIN, LOW);
   digitalWrite(BLUE_LED_PIN, LOW);
 }
 
 void ledStatusNone() {
   digitalWrite(GREEN_LED_PIN, LOW);
   digitalWrite(RED_LED_PIN, LOW);
   digitalWrite(BLUE_LED_PIN, LOW);
 }
 