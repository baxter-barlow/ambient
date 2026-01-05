#!/usr/bin/env python3
"""
Example: Basic radar data acquisition

This script demonstrates how to:
1. Connect to the radar
2. Send a configuration
3. Read and display detected objects
"""

import time
import argparse
from radar import RadarInterface


def main():
    parser = argparse.ArgumentParser(description='IWR6843AOP Radar Example')
    parser.add_argument('--cli-port', help='CLI serial port (e.g., /dev/ttyACM0)')
    parser.add_argument('--data-port', help='Data serial port (e.g., /dev/ttyACM1)')
    parser.add_argument('--config', default='configs/basic.cfg', help='Path to config file')
    parser.add_argument('--duration', type=float, default=10.0, help='Run duration in seconds')
    args = parser.parse_args()
    
    radar = RadarInterface(cli_port=args.cli_port, data_port=args.data_port)
    
    try:
        # Connect to radar
        print("Connecting to radar...")
        radar.connect()
        print("Connected!\n")
        
        # Send configuration
        print(f"Sending configuration: {args.config}")
        print("-" * 40)
        radar.send_config(args.config)
        print("-" * 40)
        print("Configuration sent!\n")
        
        # Read frames
        print("Reading data... (Ctrl+C to stop)\n")
        
        start_time = time.time()
        frame_count = 0
        
        while time.time() - start_time < args.duration:
            frame = radar.read_frame()
            
            if frame:
                frame_count += 1
                header = frame['header']
                objects = frame['objects']
                
                print(f"Frame {header['frame_number']:4d} | "
                      f"Objects: {len(objects):2d}", end='')
                
                if objects:
                    # Show nearest object
                    nearest = min(objects, key=lambda o: (o.x**2 + o.y**2)**0.5)
                    distance = (nearest.x**2 + nearest.y**2 + nearest.z**2)**0.5
                    print(f" | Nearest: {distance:.2f}m @ ({nearest.x:.2f}, {nearest.y:.2f}, {nearest.z:.2f})")
                else:
                    print()
            
            time.sleep(0.01)
        
        print(f"\nReceived {frame_count} frames in {args.duration:.1f} seconds")
        print(f"Average frame rate: {frame_count / args.duration:.1f} fps")
        
    except KeyboardInterrupt:
        print("\nStopped by user")
    
    finally:
        print("Stopping sensor...")
        radar.stop()
        radar.disconnect()
        print("Done.")


if __name__ == '__main__':
    main()
