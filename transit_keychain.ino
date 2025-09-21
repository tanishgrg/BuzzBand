/*
 * Transit Keychain - Arduino Code
 * 
 * A keychain that buzzes and flashes LEDs based on train proximity
 * 
 * Hardware:
 * - Piezo buzzer on pin 9
 * - Red LED on pin 10 (origin alerts)
 * - Green LED on pin 11 (destination alerts)
 * - Blue LED on pin 12 (status indicator)
 * 
 * Commands from Python:
 * - "ORIGIN_NEARBY" - Train approaching origin (red LED + buzzer)
 * - "ORIGIN_APPROACH" - Train very close to origin (red LED + buzzer)
 * - "ORIGIN_STOP" - Train at origin (red LED + buzzer)
 * - "DEST_NEARBY" - Train approaching destination (green LED + buzzer)
 * - "DEST_APPROACH" - Train very close to destination (green LED + buzzer)
 * - "DEST_STOP" - Train at destination (green LED + buzzer)
 * - "IDLE" - Stop all alerts
 */

// Pin definitions
const int BUZZER_PIN = 9;
const int GREEN_LED_PIN = 10;   // Nearby threshold indicator
const int RED_LED_PIN = 11;     // Stop threshold indicator
const int BLUE_LED_PIN = 12;    // Status indicator

// Alert patterns - Extended duration and more noticeable
const int NEARBY_PATTERN[] = {500, 200, 500, 200, 500, 200, 500};      // Extended short pattern
const int APPROACH_PATTERN[] = {800, 300, 800, 300, 800, 300, 800};     // Extended medium pattern
const int STOP_PATTERN[] = {1200, 400, 1200, 400, 1200, 400, 1200, 400, 1200};  // Extended long pattern

// Frequencies for different alert levels - More noticeable
const int NEARBY_FREQ = 1500;   // Higher pitch for attention
const int APPROACH_FREQ = 1300; // Medium-high pitch
const int STOP_FREQ = 1000;     // Medium pitch (more noticeable)

// Pattern lengths - Extended for more noticeable alerts
const int NEARBY_LENGTH = 7;     // 7 beeps for nearby (extended)
const int APPROACH_LENGTH = 7;   // 7 beeps for approach (extended)
const int STOP_LENGTH = 9;       // 9 beeps for stop (extended)

// State variables
bool isAlerting = false;
unsigned long alertStartTime = 0;
int currentPatternIndex = 0;
int currentPatternLength = 0;
const int* currentPattern = nullptr;
int currentFrequency = 0;
int currentLEDPin = 0;

void setup() {
  Serial.begin(115200);
  
  // Set pin modes
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(RED_LED_PIN, OUTPUT);
  pinMode(GREEN_LED_PIN, OUTPUT);
  pinMode(BLUE_LED_PIN, OUTPUT);
  
  // Initialize all pins to LOW
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(RED_LED_PIN, LOW);
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(BLUE_LED_PIN, LOW);
  
  // Startup sequence
  Serial.println("Transit Keychain Ready");
  startupSequence();
}

void loop() {
  // Check for serial commands
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    command.toUpperCase();
    
    Serial.print("Received: ");
    Serial.println(command);
    
    handleCommand(command);
  }
  
  // Alert patterns are now self-executing, no need to call from loop
}

void handleCommand(String command) {
  if (command == "ORIGIN_NEARBY") {
    simpleAlert(GREEN_LED_PIN, NEARBY_FREQ, 3000);  // 3 seconds
    Serial.println("Origin nearby alert - GREEN LED");
  }
  else if (command == "ORIGIN_APPROACH") {
    simpleAlert(GREEN_LED_PIN, APPROACH_FREQ, 5000);  // 5 seconds
    Serial.println("Origin approach alert - GREEN LED");
  }
  else if (command == "ORIGIN_STOP") {
    simpleAlert(RED_LED_PIN, STOP_FREQ, 8000);  // 8 seconds
    Serial.println("Origin stop alert - RED LED");
  }
  else if (command == "DEST_NEARBY") {
    simpleAlert(GREEN_LED_PIN, NEARBY_FREQ, 3000);  // 3 seconds
    Serial.println("Destination nearby alert - GREEN LED");
  }
  else if (command == "DEST_APPROACH") {
    simpleAlert(GREEN_LED_PIN, APPROACH_FREQ, 5000);  // 5 seconds
    Serial.println("Destination approach alert - GREEN LED");
  }
  else if (command == "DEST_STOP") {
    simpleAlert(RED_LED_PIN, STOP_FREQ, 8000);  // 8 seconds
    Serial.println("Destination stop alert - RED LED");
  }
  else if (command == "IDLE") {
    stopAlert();
    Serial.println("All alerts stopped");
  }
  else if (command == "URGENT") {
    urgentAlert();
    Serial.println("Urgent alert triggered");
  }
  else if (command == "STATUS_UPDATE") {
    statusUpdate();
    Serial.println("Status update alert");
  }
  else if (command == "LED_STATUS_ORIGIN") {
    ledStatusOrigin();
    Serial.println("LED Status: Origin");
  }
  else if (command == "LED_STATUS_DEST") {
    ledStatusDest();
    Serial.println("LED Status: Destination");
  }
  else if (command == "LED_STATUS_NONE") {
    ledStatusNone();
    Serial.println("LED Status: None");
  }
  else {
    Serial.println("Unknown command: " + command);
  }
}

void simpleAlert(int ledPin, int frequency, int duration) {
  // Simple method: turn on LED and buzzer for specified duration
  digitalWrite(ledPin, HIGH);
  digitalWrite(BLUE_LED_PIN, HIGH);
  tone(BUZZER_PIN, frequency, duration);
  delay(duration);
  
  // Turn off everything
  digitalWrite(ledPin, LOW);
  digitalWrite(BLUE_LED_PIN, LOW);
  noTone(BUZZER_PIN);
}

void startAlert(const int* pattern, int length, int frequency, int ledPin) {
  // Stop any current alert
  stopAlert();
  
  // Simple direct execution method
  currentLEDPin = ledPin;
  
  // Execute pattern directly with delays
  for (int i = 0; i < length; i++) {
    int stepDuration = pattern[i];
    
    if (i % 2 == 0) {
      // Beep step - turn on everything
      tone(BUZZER_PIN, frequency, stepDuration);
      digitalWrite(currentLEDPin, HIGH);
      digitalWrite(BLUE_LED_PIN, HIGH);
      delay(stepDuration);  // Wait for beep to complete
    } else {
      // Pause step - turn off buzzer, keep main LED on
      noTone(BUZZER_PIN);
      digitalWrite(currentLEDPin, HIGH);  // Keep main LED on
      digitalWrite(BLUE_LED_PIN, LOW);     // Turn off status LED
      delay(stepDuration);  // Wait for pause
    }
  }
  
  // Pattern complete - turn off everything
  stopAlert();
}

void stopAlert() {
  isAlerting = false;
  currentPattern = nullptr;
  currentPatternIndex = 0;
  noTone(BUZZER_PIN);
  digitalWrite(RED_LED_PIN, LOW);
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(BLUE_LED_PIN, LOW);
}

void urgentAlert() {
  // Very pronounced urgent alert - impossible to miss
  for (int i = 0; i < 8; i++) {  // Extended urgent alert
    // All LEDs on
    digitalWrite(RED_LED_PIN, HIGH);
    digitalWrite(GREEN_LED_PIN, HIGH);
    digitalWrite(BLUE_LED_PIN, HIGH);
    
    // Very high pitch, extended duration
    tone(BUZZER_PIN, 2500, 600);  // Higher pitch, longer duration
    delay(800);  // Extended LED on time
    
    // All LEDs off
    digitalWrite(RED_LED_PIN, LOW);
    digitalWrite(GREEN_LED_PIN, LOW);
    digitalWrite(BLUE_LED_PIN, LOW);
    noTone(BUZZER_PIN);
    delay(300);  // Shorter pause for more urgent feel
  }
}

void statusUpdate() {
  // More noticeable status update alert
  digitalWrite(BLUE_LED_PIN, HIGH);
  tone(BUZZER_PIN, 1200, 200);  // Higher pitch, longer duration
  delay(300);  // Extended LED on time
  digitalWrite(BLUE_LED_PIN, LOW);
  noTone(BUZZER_PIN);
}

void ledStatusOrigin() {
  // Show origin status - green LED for nearby, red LED for stop
  digitalWrite(GREEN_LED_PIN, HIGH);
  digitalWrite(RED_LED_PIN, LOW);
  digitalWrite(BLUE_LED_PIN, HIGH);  // Status indicator
  delay(1000);  // Show for 1 second
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(BLUE_LED_PIN, LOW);
}

void ledStatusDest() {
  // Show destination status - green LED for nearby, red LED for stop
  digitalWrite(GREEN_LED_PIN, HIGH);
  digitalWrite(RED_LED_PIN, LOW);
  digitalWrite(BLUE_LED_PIN, HIGH);  // Status indicator
  delay(1000);  // Show for 1 second
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(BLUE_LED_PIN, LOW);
}

void ledStatusNone() {
  // No trains - turn off all LEDs
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(RED_LED_PIN, LOW);
  digitalWrite(BLUE_LED_PIN, LOW);
}

void startupSequence() {
  // More pronounced startup sequence
  Serial.println("Starting Transit Keychain...");
  Serial.println("LED Configuration:");
  Serial.println("  GREEN LED (Pin 10) - Nearby threshold");
  Serial.println("  RED LED (Pin 11) - Stop threshold");
  Serial.println("  BLUE LED (Pin 12) - Status indicator");
  
  // LED configuration test - Extended and more noticeable
  Serial.println("Testing GREEN LED (Nearby)...");
  digitalWrite(GREEN_LED_PIN, HIGH);
  tone(BUZZER_PIN, 1500, 500);  // Higher pitch, longer duration
  delay(800);  // Extended LED on time
  digitalWrite(GREEN_LED_PIN, LOW);
  noTone(BUZZER_PIN);
  delay(300);
  
  Serial.println("Testing RED LED (Stop)...");
  digitalWrite(RED_LED_PIN, HIGH);
  tone(BUZZER_PIN, 1000, 500);  // Higher pitch, longer duration
  delay(800);  // Extended LED on time
  digitalWrite(RED_LED_PIN, LOW);
  noTone(BUZZER_PIN);
  delay(300);
  
  Serial.println("Testing BLUE LED (Status)...");
  digitalWrite(BLUE_LED_PIN, HIGH);
  tone(BUZZER_PIN, 1200, 500);  // Higher pitch, longer duration
  delay(800);  // Extended LED on time
  digitalWrite(BLUE_LED_PIN, LOW);
  noTone(BUZZER_PIN);
  delay(300);
  
  // Final attention beep
  tone(BUZZER_PIN, 2000, 500);  // Very high pitch, long duration
  delay(600);
  noTone(BUZZER_PIN);
  
  Serial.println("Startup complete - Transit Keychain ready");
}
