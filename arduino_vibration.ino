/*
 * Arduino Vibration System for Transit ETA Alerts
 * 
 * Hardware Setup:
 * - Vibration motor connected to pin 9
 * - LED connected to pin 13 (built-in LED)
 * - Arduino connected to computer via USB
 * 
 * Commands received via Serial:
 * - "NEARBY" - Short vibration pattern
 * - "APPROACH" - Medium vibration pattern  
 * - "STOP" - Long vibration pattern
 * - "IDLE" - Stop all vibrations
 */

const int VIBRATION_PIN = 9;
const int LED_PIN = 13;

// Vibration patterns (in milliseconds)
const int NEARBY_PATTERN[] = {200, 100, 200};  // Short-short-short
const int APPROACH_PATTERN[] = {500, 200, 500}; // Medium-pause-medium
const int STOP_PATTERN[] = {1000, 300, 1000, 300, 1000}; // Long-long-long

const int NEARBY_LENGTH = 3;
const int APPROACH_LENGTH = 3;
const int STOP_LENGTH = 5;

String currentCommand = "";
bool isVibrating = false;
unsigned long vibrationStartTime = 0;
int currentPatternIndex = 0;
int currentPatternLength = 0;
const int* currentPattern = nullptr;

void setup() {
  Serial.begin(9600);
  pinMode(VIBRATION_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  
  digitalWrite(VIBRATION_PIN, LOW);
  digitalWrite(LED_PIN, LOW);
  
  Serial.println("Arduino Vibration System Ready");
  Serial.println("Commands: NEARBY, APPROACH, STOP, IDLE");
}

void loop() {
  // Check for incoming serial commands
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    command.toUpperCase();
    
    Serial.print("Received: ");
    Serial.println(command);
    
    handleCommand(command);
  }
  
  // Handle vibration pattern execution
  if (isVibrating && currentPattern != nullptr) {
    executeVibrationPattern();
  }
}

void handleCommand(String command) {
  if (command == "NEARBY") {
    startVibrationPattern(NEARBY_PATTERN, NEARBY_LENGTH);
    Serial.println("Starting NEARBY vibration pattern");
  }
  else if (command == "APPROACH") {
    startVibrationPattern(APPROACH_PATTERN, APPROACH_LENGTH);
    Serial.println("Starting APPROACH vibration pattern");
  }
  else if (command == "STOP") {
    startVibrationPattern(STOP_PATTERN, STOP_LENGTH);
    Serial.println("Starting STOP vibration pattern");
  }
  else if (command == "IDLE") {
    stopVibration();
    Serial.println("Stopping all vibrations");
  }
  else {
    Serial.println("Unknown command: " + command);
  }
}

void startVibrationPattern(const int* pattern, int length) {
  currentPattern = pattern;
  currentPatternLength = length;
  currentPatternIndex = 0;
  isVibrating = true;
  vibrationStartTime = millis();
}

void executeVibrationPattern() {
  unsigned long currentTime = millis();
  unsigned long elapsed = currentTime - vibrationStartTime;
  
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
      stopVibration();
      return;
    }
  }
  
  // Determine if we should be vibrating or not
  bool shouldVibrate = (currentPatternIndex % 2 == 0);
  
  if (shouldVibrate) {
    digitalWrite(VIBRATION_PIN, HIGH);
    digitalWrite(LED_PIN, HIGH);
  } else {
    digitalWrite(VIBRATION_PIN, LOW);
    digitalWrite(LED_PIN, LOW);
  }
}

void stopVibration() {
  isVibrating = false;
  currentPattern = nullptr;
  currentPatternIndex = 0;
  digitalWrite(VIBRATION_PIN, LOW);
  digitalWrite(LED_PIN, LOW);
}

// Test function - can be called manually
void testVibration() {
  Serial.println("Testing vibration patterns...");
  
  Serial.println("Testing NEARBY pattern");
  startVibrationPattern(NEARBY_PATTERN, NEARBY_LENGTH);
  delay(2000);
  
  Serial.println("Testing APPROACH pattern");
  startVibrationPattern(APPROACH_PATTERN, APPROACH_LENGTH);
  delay(3000);
  
  Serial.println("Testing STOP pattern");
  startVibrationPattern(STOP_PATTERN, STOP_LENGTH);
  delay(5000);
  
  stopVibration();
  Serial.println("Test complete");
}
