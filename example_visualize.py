#!/usr/bin/env python3
"""
Example: Real-time radar visualization

Shows detected points in a 2D plot (top-down view).
Requires matplotlib: pip install matplotlib
"""

import argparse
import numpy as np
from radar import RadarInterface

try:
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
except ImportError:
    print("This example requires matplotlib: pip install matplotlib")
    exit(1)


class RadarVisualizer:
    def __init__(self, radar: RadarInterface, max_range: float = 5.0):
        self.radar = radar
        self.max_range = max_range
        
        # Set up the plot
        plt.style.use('dark_background')
        self.fig, self.ax = plt.subplots(figsize=(8, 8))
        
        # Scatter plot for detected points
        self.scatter = self.ax.scatter([], [], c='lime', s=50, alpha=0.8)
        
        # Configure axes
        self.ax.set_xlim(-max_range, max_range)
        self.ax.set_ylim(0, max_range)
        self.ax.set_xlabel('X (m)')
        self.ax.set_ylabel('Y (m)')
        self.ax.set_title('IWR6843AOP Radar - Top View')
        self.ax.set_aspect('equal')
        self.ax.grid(True, alpha=0.3)
        
        # Draw range arcs
        for r in range(1, int(max_range) + 1):
            arc = plt.Circle((0, 0), r, fill=False, color='gray', alpha=0.3, linestyle='--')
            self.ax.add_patch(arc)
        
        # Draw sensor position
        self.ax.plot(0, 0, 'r^', markersize=10, label='Sensor')
        
        # Frame counter text
        self.frame_text = self.ax.text(
            0.02, 0.98, '', transform=self.ax.transAxes,
            verticalalignment='top', fontsize=10, color='white'
        )
    
    def update(self, frame_num):
        """Animation update function."""
        frame = self.radar.read_frame()
        
        if frame and frame['objects']:
            objects = frame['objects']
            
            # Extract x, y coordinates
            x = [obj.x for obj in objects]
            y = [obj.y for obj in objects]
            
            # Color by velocity
            velocities = [obj.velocity for obj in objects]
            
            self.scatter.set_offsets(np.c_[x, y])
            
            # Update frame info
            self.frame_text.set_text(
                f"Frame: {frame['header']['frame_number']}\n"
                f"Objects: {len(objects)}"
            )
        else:
            self.scatter.set_offsets(np.empty((0, 2)))
        
        return self.scatter, self.frame_text
    
    def run(self):
        """Start the visualization."""
        ani = FuncAnimation(
            self.fig, self.update,
            interval=50,  # 20 fps update
            blit=True,
            cache_frame_data=False
        )
        plt.show()


def main():
    parser = argparse.ArgumentParser(description='IWR6843AOP Radar Visualizer')
    parser.add_argument('--cli-port', help='CLI serial port')
    parser.add_argument('--data-port', help='Data serial port')
    parser.add_argument('--config', default='configs/basic.cfg', help='Config file')
    parser.add_argument('--range', type=float, default=5.0, help='Max display range (m)')
    args = parser.parse_args()
    
    radar = RadarInterface(cli_port=args.cli_port, data_port=args.data_port)
    
    try:
        print("Connecting to radar...")
        radar.connect()
        
        print(f"Sending configuration: {args.config}")
        radar.send_config(args.config)
        
        print("Starting visualization... (close window to stop)")
        viz = RadarVisualizer(radar, max_range=args.range)
        viz.run()
        
    except KeyboardInterrupt:
        print("\nStopped")
    
    finally:
        radar.stop()
        radar.disconnect()


if __name__ == '__main__':
    main()
