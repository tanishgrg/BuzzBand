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
const int RED_LED_PIN = 10;    // Origin alerts
const int GREEN_LED_PIN = 11;  // Destination alerts
const int BLUE_LED_PIN = 12;    // Status indicator

// Alert patterns - More pronounced and attention-grabbing
const int NEARBY_PATTERN[] = {300, 150, 300, 150, 300};      // Short-short-short-short-short
const int APPROACH_PATTERN[] = {600, 200, 600, 200, 600};     // Medium-pause-medium-pause-medium
const int STOP_PATTERN[] = {1000, 300, 1000, 300, 1000, 300, 1000};  // Long-long-long-long

// Frequencies for different alert levels - More pronounced
const int NEARBY_FREQ = 1200;   // Higher pitch for attention
const int APPROACH_FREQ = 1000; // Medium-high pitch
const int STOP_FREQ = 800;      // Medium pitch (not too low)

// Pattern lengths
const int NEARBY_LENGTH = 5;     // 5 beeps for nearby
const int APPROACH_LENGTH = 5;   // 5 beeps for approach
const int STOP_LENGTH = 7;       // 7 beeps for stop

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
  
  // Handle alert pattern execution
  if (isAlerting && currentPattern != nullptr) {
    executeAlertPattern();
  }
}

void handleCommand(String command) {
  if (command == "ORIGIN_NEARBY") {
    startAlert(NEARBY_PATTERN, NEARBY_LENGTH, NEARBY_FREQ, RED_LED_PIN);
    Serial.println("Origin nearby alert");
  }
  else if (command == "ORIGIN_APPROACH") {
    startAlert(APPROACH_PATTERN, APPROACH_LENGTH, APPROACH_FREQ, RED_LED_PIN);
    Serial.println("Origin approach alert");
  }
  else if (command == "ORIGIN_STOP") {
    startAlert(STOP_PATTERN, STOP_LENGTH, STOP_FREQ, RED_LED_PIN);
    Serial.println("Origin stop alert");
  }
  else if (command == "DEST_NEARBY") {
    startAlert(NEARBY_PATTERN, NEARBY_LENGTH, NEARBY_FREQ, GREEN_LED_PIN);
    Serial.println("Destination nearby alert");
  }
  else if (command == "DEST_APPROACH") {
    startAlert(APPROACH_PATTERN, APPROACH_LENGTH, APPROACH_FREQ, GREEN_LED_PIN);
    Serial.println("Destination approach alert");
  }
  else if (command == "DEST_STOP") {
    startAlert(STOP_PATTERN, STOP_LENGTH, STOP_FREQ, GREEN_LED_PIN);
    Serial.println("Destination stop alert");
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
  else {
    Serial.println("Unknown command: " + command);
  }
}

void startAlert(const int* pattern, int length, int frequency, int ledPin) {
  currentPattern = pattern;
  currentPatternLength = length;
  currentPatternIndex = 0;
  currentFrequency = frequency;
  currentLEDPin = ledPin;
  isAlerting = true;
  alertStartTime = millis();
}

void executeAlertPattern() {
  unsigned long currentTime = millis();
  unsigned long elapsed = currentTime - alertStartTime;
  
  // Calculate cumulative time for current pattern step
  unsigned long cumulativeTime = 0;
  for (int i = 0; i <= currentPatternIndex; i++) {
    cumulativeTime += currentPattern[i];
  }
  
  if (elapsed >= cumulativeTime) {
    // Move to next step in pattern
    currentPatternIndex++;
    
    if (currentPatternIndex >= currentPatternLength) {
      // Pattern complete
      stopAlert();
      return;
    }
  }
  
  // Determine if we should be alerting or not
  bool shouldAlert = (currentPatternIndex % 2 == 0);
  
  if (shouldAlert) {
    tone(BUZZER_PIN, currentFrequency);
    digitalWrite(currentLEDPin, HIGH);
    digitalWrite(BLUE_LED_PIN, HIGH);  // Status indicator
  } else {
    noTone(BUZZER_PIN);
    digitalWrite(currentLEDPin, LOW);
    digitalWrite(BLUE_LED_PIN, LOW);
  }
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
  for (int i = 0; i < 5; i++) {
    // All LEDs on
    digitalWrite(RED_LED_PIN, HIGH);
    digitalWrite(GREEN_LED_PIN, HIGH);
    digitalWrite(BLUE_LED_PIN, HIGH);
    
    // Very high pitch, long duration
    tone(BUZZER_PIN, 2000, 400);
    delay(500);
    
    // All LEDs off
    digitalWrite(RED_LED_PIN, LOW);
    digitalWrite(GREEN_LED_PIN, LOW);
    digitalWrite(BLUE_LED_PIN, LOW);
    noTone(BUZZER_PIN);
    delay(200);
  }
}

void statusUpdate() {
  // Quick status update alert - short and informative
  digitalWrite(BLUE_LED_PIN, HIGH);
  tone(BUZZER_PIN, 800, 100);  // Short beep
  delay(150);
  digitalWrite(BLUE_LED_PIN, LOW);
  noTone(BUZZER_PIN);
}

void startupSequence() {
  // More pronounced startup sequence
  Serial.println("Starting Transit Keychain...");
  
  // Attention-grabbing startup sequence
  for (int i = 0; i < 3; i++) {
    // All LEDs on
    digitalWrite(RED_LED_PIN, HIGH);
    digitalWrite(GREEN_LED_PIN, HIGH);
    digitalWrite(BLUE_LED_PIN, HIGH);
    
    // Pronounced buzzer sequence
    tone(BUZZER_PIN, 1500, 200);  // High pitch
    delay(300);
    tone(BUZZER_PIN, 1000, 200);  // Medium pitch
    delay(300);
    tone(BUZZER_PIN, 800, 200);   // Lower pitch
    delay(300);
    
    // All LEDs off
    digitalWrite(RED_LED_PIN, LOW);
    digitalWrite(GREEN_LED_PIN, LOW);
    digitalWrite(BLUE_LED_PIN, LOW);
    noTone(BUZZER_PIN);
    delay(200);
  }
  
  // Final attention beep
  tone(BUZZER_PIN, 2000, 500);  // Very high pitch, long duration
  delay(600);
  noTone(BUZZER_PIN);
  
  Serial.println("Startup complete - Transit Keychain ready");
}
