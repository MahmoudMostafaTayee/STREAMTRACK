import json
import os
from PIL import Image, ImageDraw, ImageFont

def draw_cameras():
    base_path = r'c:\OURs\Thesis\Real-Time_Multi-Camera_People_Tracking_using_Event_Stream_Processing\Original\scene_001'

    calib_path = os.path.join(base_path, 'calibration.json')
    map_path = os.path.join(base_path, 'map.png')
    output_path = os.path.join(base_path, 'map_with_cameras.png')

    if not os.path.exists(calib_path):
        print(f"Error: {calib_path} not found")
        return

    if not os.path.exists(map_path):
        print(f"Error: {map_path} not found")
        return

    with open(calib_path, 'r') as f:
        data = json.load(f)

    img = Image.open(map_path)
    draw = ImageDraw.Draw(img)
    width, height = img.size
    print(f"Map size: {width}x{height}")

    # Use default font or try to load one
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()

    # Create an overlay for transparency
    overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
    d_overlay = ImageDraw.Draw(overlay)

    sensors = data.get('sensors', [])
    print(f"Found {len(sensors)} sensors")

    for sensor in sensors:
        cam_id = sensor.get('id', 'Unknown')
        coords = sensor.get('coordinates', {})
        x_world = coords.get('x', 0)
        y_world = coords.get('y', 0)
        
        # Mapping parameters from calibration.json
        scale = sensor.get('scaleFactor', 25.044267506598246)
        trans = sensor.get('translationToGlobalCoordinates', {'x': 49.62725112659545, 'y': 5.333818011968089})
        trans_x = trans.get('x', 0)
        trans_y = trans.get('y', 0)

        # Refined Hypothesis:
        # u = (x_world + trans_x) * scale
        # v = height - (y_world + trans_y) * scale
        
        u = (x_world + trans_x) * scale
        v = height - (y_world + trans_y) * scale

        # Get direction (heading)
        direction = 0
        for attr in sensor.get('attributes', []):
            if attr['name'] == 'direction':
                try:
                    direction = float(attr['value'])
                except:
                    direction = 0
                break
        
        # Draw FOV cone
        # Assuming direction is in degrees, 0 is North (+Y), 90 is East (+X)
        # Math_angle = 90 - direction
        import math
        math_angle = 90 - direction
        
        fov_angle = 60 # degrees
        cone_length = 80 # pixels
        
        angle_start = math_angle - (fov_angle / 2)
        angle_end = math_angle + (fov_angle / 2)
        
        # Calculate cone points
        p1 = (u + cone_length * math.cos(math.radians(angle_start)), 
              v - cone_length * math.sin(math.radians(angle_start)))
        p2 = (u + cone_length * math.cos(math.radians(angle_end)), 
              v - cone_length * math.sin(math.radians(angle_end)))
        
        # Draw semi-transparent cone on overlay
        d_overlay.polygon([(u, v), p1, p2], fill=(255, 0, 0, 80), outline=(255, 255, 255, 150))

        # Draw a small circle for the camera on main image
        radius = 5
        draw.ellipse([u - radius, v - radius, u + radius, v + radius], fill='red', outline='white')
        
        # Draw camera ID
        draw.text((u + radius + 2, v - radius), cam_id, fill='blue', font=font)

        print(f"Camera {cam_id}: World({x_world:.2f}, {y_world:.2f}) -> Pixel({u:.2f}, {v:.2f}), Heading: {direction:.1f}")

    # Composite overlay
    img = Image.alpha_composite(img.convert('RGBA'), overlay)
    img.convert('RGB').save(output_path)
    print(f"Saved visualization to {output_path}")


if __name__ == "__main__":
    draw_cameras()
