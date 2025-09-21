# Transit Keychain Setup Guide

## 🔧 **Hardware Components**

### **Arduino Components:**
- Arduino Uno (or compatible)
- Piezo buzzer (3V-5V)
- Red LED (origin alerts)
- Green LED (destination alerts)  
- Blue LED (status indicator)
- Resistors (220Ω for LEDs)
- Jumper wires
- Small breadboard or PCB

### **Wiring Diagram:**
```
Arduino Uno
    Pin 9  ────► Piezo Buzzer (+)
    GND    ────► Piezo Buzzer (-)
    
    Pin 10 ────► 220Ω Resistor ────► Green LED (+) ────► Green LED (-) ────► GND
    Pin 11 ────► 220Ω Resistor ────► Red LED (+) ────► Red LED (-) ────► GND  
    Pin 12 ────► 220Ω Resistor ────► Blue LED (+) ────► Blue LED (-) ────► GND
```

## 🚀 **Setup Instructions**

### **1. Hardware Assembly:**
1. Connect piezo buzzer to Pin 9 and GND
2. Connect green LED to Pin 10 (with 220Ω resistor) - Nearby threshold
3. Connect red LED to Pin 11 (with 220Ω resistor) - Stop threshold
4. Connect blue LED to Pin 12 (with 220Ω resistor) - Status indicator
5. Connect Arduino to computer via USB

### **2. Software Setup:**
1. Upload `transit_keychain.ino` to Arduino
2. Install Python dependencies:
   ```bash
   pip install pyserial requests
   ```

### **3. Test the System:**
```bash
python transit_keychain.py
```

## 🎵 **Alert System**

### **LED Alert System:**
- **GREEN LED (Pin 10)**: Nearby threshold alerts
  - **ORIGIN_NEARBY**: Train within 5 minutes (green LED + high pitch)
  - **ORIGIN_APPROACH**: Train within 2 minutes (green LED + medium pitch)
  - **DEST_NEARBY**: Train within 10 minutes (green LED + high pitch)
  - **DEST_APPROACH**: Train within 5 minutes (green LED + medium pitch)

- **RED LED (Pin 11)**: Stop threshold alerts
  - **ORIGIN_STOP**: Train within 1 minute (red LED + low pitch)
  - **DEST_STOP**: Train within 2 minutes (red LED + low pitch)

### **Status Indicator (Blue LED):**
- Flashes with all alerts to show system is active
- Off when system is idle

## 🔔 **Alert Patterns**

### **NEARBY Pattern:**
- Short-short-short beeps (200ms on, 100ms off, 200ms on)
- High pitch (800Hz)

### **APPROACH Pattern:**
- Medium-pause-medium beeps (500ms on, 200ms off, 500ms on)
- Medium pitch (600Hz)

### **STOP Pattern:**
- Long-long beeps (1000ms on, 300ms off, 1000ms on)
- Low pitch (400Hz)

## 🧪 **Testing**

### **Manual Test (Arduino IDE):**
1. Open Serial Monitor (115200 baud)
2. Send commands:
   - `ORIGIN_NEARBY` - Red LED + high pitch
   - `DEST_APPROACH` - Green LED + medium pitch
   - `IDLE` - Stop all alerts

### **Python Test:**
```bash
python transit_keychain.py
```

## 📱 **Usage**

### **At Origin Stop:**
- Red LED alerts when train is approaching
- Different patterns for nearby/approach/stop
- Audio feedback with piezo buzzer

### **On Train:**
- Green LED alerts when approaching destination
- Same pattern system for destination alerts
- Visual and audio feedback

## 🔧 **Troubleshooting**

### **No Sound:**
- Check piezo buzzer wiring (Pin 9 → Buzzer+ → Buzzer- → GND)
- Test buzzer with 3V battery
- Check if code uploaded correctly

### **No LEDs:**
- Check LED wiring and resistors
- Test LEDs with 3V battery
- Verify pin connections

### **Arduino Not Detected:**
- Check USB connection
- Try different USB port
- Install Arduino drivers
- Check Device Manager for COM ports

### **Python Connection Issues:**
- Check baud rate (115200)
- Restart Arduino and Python
- Check if another program is using the serial port

## 🎯 **Expected Behavior**

### **Startup:**
- All LEDs flash 3 times
- Buzzer beeps 3 times
- Serial message: "Transit Keychain Ready"

### **During Operation:**
- Red LED + buzzer for origin alerts
- Green LED + buzzer for destination alerts
- Blue LED flashes with all alerts
- Serial output shows alert commands

### **Idle State:**
- All LEDs off
- No buzzer sound
- System waits for next alert
