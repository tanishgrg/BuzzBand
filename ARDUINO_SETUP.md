# Arduino Piezo Buzzer System Setup Guide

## Hardware Requirements

### Arduino Components:
- Arduino Uno (or compatible)
- Piezo buzzer (3V-5V)
- Jumper wires
- Breadboard (optional)

### Wiring:
```
Arduino Pin 9 → Piezo Buzzer (+) → Piezo Buzzer (-) → GND
Arduino Pin 13 → Built-in LED (for visual feedback)
```

## Software Setup

### 1. Install Arduino IDE
- Download from https://www.arduino.cc/en/software
- Install the Arduino IDE

### 2. Upload the Code
1. Open `arduino_vibration.ino` in Arduino IDE
2. Select your Arduino board (Tools → Board → Arduino Uno)
3. Select the correct port (Tools → Port → COM3 or similar)
4. Click Upload

### 3. Install Python Dependencies
```bash
pip install pyserial requests
```

## Testing

### Test Arduino Directly:
1. Open Arduino IDE Serial Monitor (Tools → Serial Monitor)
2. Set baud rate to 9600
3. Send commands: `NEARBY`, `APPROACH`, `STOP`, `IDLE`
4. Watch the LED and listen to the beep patterns

### Test with Python:
1. Connect Arduino via USB
2. Run the Python script: `python app.py`
3. The system will automatically detect the Arduino
4. Monitor the console for ETA updates and vibration commands

## Beep Patterns

- **NEARBY**: Short-short-short (200ms on, 100ms off, 200ms on) at 800Hz
- **APPROACH**: Medium-pause-medium (500ms on, 200ms off, 500ms on) at 600Hz
- **STOP**: Long-long-long (1000ms on, 300ms off, 1000ms on, 300ms off, 1000ms on) at 400Hz
- **IDLE**: Stops all beeps

## Troubleshooting

### Arduino Not Detected:
- Check USB connection
- Try different USB port
- Install Arduino drivers if needed
- Check Device Manager for COM port

### No Sound:
- Check wiring (Pin 9 → Piezo Buzzer (+) → Piezo Buzzer (-) → GND)
- Test buzzer with 3V battery
- Check if buzzer is working
- Verify code uploaded successfully
- Try different frequencies in the code

### Python Connection Issues:
- Check COM port in Arduino IDE
- Try different baud rates
- Restart both Arduino and Python script
- Check if another program is using the serial port

## Customization

### Change Beep Patterns:
Edit the pattern arrays and frequencies in `arduino_vibration.ino`:
```cpp
const int NEARBY_PATTERN[] = {200, 100, 200};  // milliseconds
const int NEARBY_FREQ = 800;    // frequency in Hz
```

### Adjust Thresholds:
Edit the timing constants in `app.py`:
```python
NEARBY_THRESHOLD_SEC = 180   # 3 minutes
APPROACH_THRESHOLD_SEC = 300 # 5 minutes  
STOP_THRESHOLD_SEC = 60     # 1 minute
```

### Add More Commands:
1. Add new pattern in Arduino code
2. Add new command handler
3. Send command from Python when needed
