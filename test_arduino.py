#!/usr/bin/env python3
"""
Test script for Arduino vibration system
Run this to test the Arduino connection and vibration patterns
"""

import serial
import serial.tools.list_ports
import time

def find_arduino_port():
    """Find the Arduino port automatically"""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if 'Arduino' in port.description or 'USB' in port.description:
            return port.device
    return None

def test_arduino_connection():
    """Test Arduino connection and vibration patterns"""
    
    # Find Arduino port
    port = find_arduino_port()
    if port is None:
        print("❌ Arduino not found. Please check connection.")
        return False
    
    print(f"✅ Found Arduino on {port}")
    
    try:
        # Connect to Arduino
        arduino = serial.Serial(port, 9600, timeout=1)
        time.sleep(2)  # Wait for Arduino to initialize
        
        print("✅ Connected to Arduino")
        print("Testing vibration patterns...")
        
        # Test each vibration pattern
        patterns = [
            ("NEARBY", "Short vibration pattern"),
            ("APPROACH", "Medium vibration pattern"), 
            ("STOP", "Long vibration pattern"),
            ("IDLE", "Stop all vibrations")
        ]
        
        for command, description in patterns:
            print(f"\n🧪 Testing {command}: {description}")
            arduino.write(f"{command}\n".encode())
            
            # Wait for pattern to complete
            if command == "NEARBY":
                time.sleep(1)
            elif command == "APPROACH":
                time.sleep(2)
            elif command == "STOP":
                time.sleep(4)
            else:
                time.sleep(0.5)
            
            print(f"✅ {command} test completed")
        
        arduino.close()
        print("\n🎉 All tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing Arduino: {e}")
        return False

def interactive_test():
    """Interactive test mode"""
    port = find_arduino_port()
    if port is None:
        print("❌ Arduino not found.")
        return
    
    try:
        arduino = serial.Serial(port, 9600, timeout=1)
        time.sleep(2)
        
        print("🎮 Interactive test mode")
        print("Commands: NEARBY, APPROACH, STOP, IDLE, quit")
        
        while True:
            command = input("\nEnter command: ").strip().upper()
            
            if command == "QUIT":
                break
            elif command in ["NEARBY", "APPROACH", "STOP", "IDLE"]:
                arduino.write(f"{command}\n".encode())
                print(f"Sent: {command}")
            else:
                print("Invalid command")
        
        arduino.close()
        print("Test session ended")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("Arduino Vibration System Test")
    print("=" * 40)
    
    # Run automatic tests
    if test_arduino_connection():
        print("\n" + "=" * 40)
        choice = input("Run interactive test? (y/n): ").lower()
        if choice == 'y':
            interactive_test()
    else:
        print("\n❌ Automatic tests failed. Please check your setup.")
