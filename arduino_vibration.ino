/*
 * Arduino Piezo Buzzer System for Transit ETA Alerts
 * 
 * Hardware Setup:
 * - Piezo buzzer connected to pin 9
 * - LED connected to pin 13 (built-in LED)
 * - Arduino connected to computer via USB
 * 
 * Commands received via Serial:
 * - "NEARBY" - Short beep pattern
 * - "APPROACH" - Medium beep pattern  
 * - "STOP" - Long beep pattern
 * - "IDLE" - Stop all beeps
 */

const int BUZZER_PIN = 9;
const int LED_PIN = 13;

// Beep patterns using the same tones as testArduino
const int NEARBY_PATTERN[] = {150, 50, 150};  // Short-short-short (like doorbell)
const int APPROACH_PATTERN[] = {500, 200, 500}; // Medium-pause-medium
const int STOP_PATTERN[] = {1000, 300, 1000, 300, 1000}; // Long-long-long

// Frequencies matching testArduino (doorbell sequence)
const int NEARBY_FREQ = 880;    // First note of doorbell sequence
const int APPROACH_FREQ = 988;  // Second note of doorbell sequence  
const int STOP_FREQ = 1175;     // Third note of doorbell sequence

const int NEARBY_LENGTH = 3;
const int APPROACH_LENGTH = 3;
const int STOP_LENGTH = 5;

String currentCommand = "";
bool isBeeping = false;
unsigned long beepStartTime = 0;
int currentPatternIndex = 0;
int currentPatternLength = 0;
const int* currentPattern = nullptr;
int currentFrequency = 0;

void setup() {
  Serial.begin(115200);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(LED_PIN, LOW);
  
  // Test piezo buzzer on startup
  Serial.println("Arduino Piezo Buzzer System Ready");
  Serial.println("Testing piezo buzzer...");
  
  // Quick test beep
  tone(BUZZER_PIN, 1000, 200);  // 1 second beep at 1000Hz
  delay(300);
  tone(BUZZER_PIN, 500, 200);   // 0.5 second beep at 500Hz
  delay(300);
  noTone(BUZZER_PIN);
  
  Serial.println("Piezo buzzer test complete");
  Serial.println("Commands: NEARBY, APPROACH, STOP, IDLE, TEST");
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
  
  // Handle beep pattern execution
  if (isBeeping && currentPattern != nullptr) {
    executeBeepPattern();
  }
}

void handleCommand(String command) {
  if (command == "NEARBY") {
    startBeepPattern(NEARBY_PATTERN, NEARBY_LENGTH, NEARBY_FREQ);
    Serial.println("Starting NEARBY beep pattern");
  }
  else if (command == "APPROACH") {
    startBeepPattern(APPROACH_PATTERN, APPROACH_LENGTH, APPROACH_FREQ);
    Serial.println("Starting APPROACH beep pattern");
  }
  else if (command == "STOP") {
    startBeepPattern(STOP_PATTERN, STOP_LENGTH, STOP_FREQ);
    Serial.println("Starting STOP beep pattern");
  }
  else if (command == "IDLE") {
    stopBeeping();
    Serial.println("Stopping all beeps");
  }
  else if (command == "TEST") {
    testBeeping();
  }
  else if (command.startsWith("BUZZ")) {
    // Handle BUZZ command like testArduino: "BUZZ freq duration"
    int spaceIndex = command.indexOf(' ');
    if (spaceIndex > 0) {
      int freq = command.substring(spaceIndex + 1, command.indexOf(' ', spaceIndex + 1)).toInt();
      int duration = command.substring(command.lastIndexOf(' ') + 1).toInt();
      
      if (freq > 0 && duration > 0) {
        tone(BUZZER_PIN, freq, duration);
        digitalWrite(LED_PIN, HIGH);
        delay(duration);
        digitalWrite(LED_PIN, LOW);
        Serial.println("BUZZ: " + String(freq) + "Hz for " + String(duration) + "ms");
      } else {
        noTone(BUZZER_PIN);
        digitalWrite(LED_PIN, LOW);
        Serial.println("BUZZ: Stopped");
      }
    }
  }
  else {
    Serial.println("Unknown command: " + command);
  }
}

void startBeepPattern(const int* pattern, int length, int frequency) {
  currentPattern = pattern;
  currentPatternLength = length;
  currentPatternIndex = 0;
  currentFrequency = frequency;
  isBeeping = true;
  beepStartTime = millis();
}

void executeBeepPattern() {
  unsigned long currentTime = millis();
  unsigned long elapsed = currentTime - beepStartTime;
  
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
      stopBeeping();
      return;
    }
  }
  
  // Determine if we should be beeping or not
  bool shouldBeep = (currentPatternIndex % 2 == 0);
  
  if (shouldBeep) {
    tone(BUZZER_PIN, currentFrequency);
    digitalWrite(LED_PIN, HIGH);
  } else {
    noTone(BUZZER_PIN);
    digitalWrite(LED_PIN, LOW);
  }
}

void stopBeeping() {
  isBeeping = false;
  currentPattern = nullptr;
  currentPatternIndex = 0;
  noTone(BUZZER_PIN);
  digitalWrite(LED_PIN, LOW);
}

// Test function - can be called manually
void testBeeping() {
  Serial.println("Testing beep patterns...");
  
  Serial.println("Testing NEARBY pattern");
  startBeepPattern(NEARBY_PATTERN, NEARBY_LENGTH, NEARBY_FREQ);
  delay(2000);
  
  Serial.println("Testing APPROACH pattern");
  startBeepPattern(APPROACH_PATTERN, APPROACH_LENGTH, APPROACH_FREQ);
  delay(3000);
  
  Serial.println("Testing STOP pattern");
  startBeepPattern(STOP_PATTERN, STOP_LENGTH, STOP_FREQ);
  delay(5000);
  
  stopBeeping();
  Serial.println("Test complete");
}
