import json
import os
import math
from PIL import Image, ImageDraw, ImageFont

def get_base_paths():
    base_path = r'c:\OURs\Thesis\Real-Time_Multi-Camera_People_Tracking_using_Event_Stream_Processing\Original\scene_001'
    calib_path = os.path.join(base_path, 'calibration.json')
    map_path = os.path.join(base_path, 'map.png')
    return base_path, calib_path, map_path

# Updated 9-camera topology groups
group_1 = ['Camera_02', 'Camera_17']
group_2 = ['Camera_01', 'Camera_11']
group_3 = ['Camera_19', 'Camera_27']
group_4 = ['Camera_21', 'Camera_25', 'Camera_30']
outlier_group = []

# Colors for each group
GROUP_COLORS = {
    "g1": {
        "fill": (0, 100, 255, 60),      # Blue cone
        "outline": '#0064FF',
        "text": '#002E7A',
        "label": "Group 1"
    },
    "g2": {
        "fill": (0, 200, 50, 60),       # Green cone
        "outline": '#00C832',
        "text": '#005A16',
        "label": "Group 2"
    },
    "g3": {
        "fill": (255, 140, 0, 60),      # Orange cone
        "outline": '#FF8C00',
        "text": '#A35600',
        "label": "Group 3"
    },
    "g4": {
        "fill": (160, 32, 240, 60),     # Purple cone
        "outline": '#A020F0',
        "text": '#5A0080',
        "label": "Group 4"
    },
}

def generate_variation(var_num, show_all_cams=True, draw_connections=False, style="standard"):
    base_path, calib_path, map_path = get_base_paths()
    if not os.path.exists(calib_path) or not os.path.exists(map_path):
        print(f"Missing paths in variation {var_num}")
        return

    with open(calib_path, 'r') as f:
        data = json.load(f)

    img = Image.open(map_path)
    draw = ImageDraw.Draw(img)
    width, height = img.size

    # Font setup
    try:
        font = ImageFont.truetype("arial.ttf", 40 if style == "minimal" else 30)
    except:
        font = ImageFont.load_default()

    overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
    d_overlay = ImageDraw.Draw(overlay)

    sensors = data.get('sensors', [])
    
    # Store points for connections
    group_points = { "g1": [], "g2": [], "g3": [], "g4": [] }
    
    # Pre-calculate positions
    cam_data = []

    for sensor in sensors:
        cam_id = sensor.get('id', 'Unknown')
        coords = sensor.get('coordinates', {})
        x_world = coords.get('x', 0)
        y_world = coords.get('y', 0)
        
        scale = sensor.get('scaleFactor', 25.044267506598246)
        trans = sensor.get('translationToGlobalCoordinates', {'x': 49.62725112659545, 'y': 5.333818011968089})
        trans_x = trans.get('x', 0)
        trans_y = trans.get('y', 0)

        u = (x_world + trans_x) * scale
        v = height - (y_world + trans_y) * scale

        direction = 0
        for attr in sensor.get('attributes', []):
            if attr['name'] == 'direction':
                try: direction = float(attr['value'])
                except: direction = 0
                break
                
        cam_data.append({
            'id': cam_id,
            'u': u, 'v': v,
            'direction': direction
        })

    def draw_label(draw_obj, pos, text, fill_color, bg_color=(255, 255, 255, 200)):
        try:
            bbox = draw_obj.textbbox(pos, text, font=font)
            pad = 6
            draw_obj.rectangle([bbox[0]-pad, bbox[1]-pad, bbox[2]+pad, bbox[3]+pad], fill=bg_color, outline=fill_color, width=3)
        except AttributeError:
            w, h = draw_obj.textsize(text, font=font)
            draw_obj.rectangle([pos[0]-2, pos[1]-2, pos[0]+w+2, pos[1]+h+2], fill=bg_color, outline=fill_color)
        
        draw_obj.text(pos, text, fill=fill_color, font=font)

    def get_group_info(cam_id):
        """Returns (group_key, group_colors) or (None, None) for non-grouped cameras."""
        if cam_id in group_1: return "g1", GROUP_COLORS["g1"]
        if cam_id in group_2: return "g2", GROUP_COLORS["g2"]
        if cam_id in group_3: return "g3", GROUP_COLORS["g3"]
        if cam_id in group_4: return "g4", GROUP_COLORS["g4"]
        return None, None

    for cam in cam_data:
        cam_id = cam['id']
        u, v = cam['u'], cam['v']
        direction = cam['direction']
        
        gkey, gcolors = get_group_info(cam_id)
        is_outlier = cam_id in outlier_group
        is_grouped = gkey is not None
        is_important = is_grouped or is_outlier
        
        if not show_all_cams and not is_important:
            continue
            
        if is_grouped:
            color_fill = gcolors["fill"]
            color_outline = gcolors["outline"]
            text_color = gcolors["text"]
            group_points[gkey].append((u, v))
        elif is_outlier:
            color_fill = (255, 0, 0, 150)
            color_outline = '#FF0000'
            text_color = '#990000'
        else:
            color_fill = (150, 150, 150, 30)
            color_outline = (200, 200, 200)
            text_color = '#999999'

        # Draw FOV cone
        math_angle = 90 - direction
        fov_angle = 60
        cone_length = 110 if is_important else 80
        
        angle_start = math_angle - (fov_angle / 2)
        angle_end = math_angle + (fov_angle / 2)
        
        p1 = (u + cone_length * math.cos(math.radians(angle_start)), 
              v - cone_length * math.sin(math.radians(angle_start)))
        p2 = (u + cone_length * math.cos(math.radians(angle_end)), 
              v - cone_length * math.sin(math.radians(angle_end)))
        
        d_overlay.polygon([(u, v), p1, p2], fill=color_fill, outline=(255, 255, 255, 100))

        # Camera node
        radius = 10 if is_important else 4
        outline_color = color_outline if isinstance(color_outline, str) else 'white'
        draw.ellipse([u - radius, v - radius, u + radius, v + radius], fill=color_outline, outline='white', width=2)
        
        # Only show labels for important cameras
        if is_important:
            short_name = f"Cam {cam_id[-2:]}" if "Camera_" in cam_id else cam_id
            if is_outlier: short_name += " (Outlier)"

            text_offset_x = 15
            text_offset_y = -25
            
            if u > width/2: text_offset_x = -150 if is_outlier else -100
            if v > height/2: text_offset_y = 30

            label_pos = (u + text_offset_x, v + text_offset_y)
            bg_color = (255, 230, 230, 255) if is_outlier else (255, 255, 255, 255)
            draw_label(draw, label_pos, short_name, text_color, bg_color=bg_color)

    # Composite overlay
    final_img = Image.alpha_composite(img.convert('RGBA'), overlay)
    final_draw = ImageDraw.Draw(final_img)
    
    if draw_connections:
        def draw_dashed_line(d, p1, p2, fill, width=3, dash_len=10):
            x1, y1 = p1
            x2, y2 = p2
            dist = math.hypot(x2 - x1, y2 - y1)
            dashes = int(dist / dash_len)
            for i in range(dashes):
                start = (x1 + (x2 - x1) * (i / dashes), y1 + (y2 - y1) * (i / dashes))
                end = (x1 + (x2 - x1) * ((i + 0.5) / dashes), y1 + (y2 - y1) * ((i + 0.5) / dashes))
                d.line([start, end], fill=fill, width=width)
        
        # Connect cameras within each group
        for gkey, color_info in GROUP_COLORS.items():
            pts = group_points[gkey]
            if len(pts) >= 2:
                for i in range(len(pts)):
                    for j in range(i+1, len(pts)):
                        draw_dashed_line(final_draw, pts[i], pts[j], fill=color_info["outline"], width=4, dash_len=12)

    out_path = os.path.join("c:\\OURs\\Thesis\\Real-Time_Multi-Camera_People_Tracking_using_Event_Stream_Processing\\paper", f"map_topology_var{var_num}.png")
    final_img.convert('RGB').save(out_path)
    print(f"Variation {var_num} saved to {out_path}")

if __name__ == "__main__":
    print("Generating 9-camera topology variations...")
    # Var 1: Show all cams, groups highlighted
    generate_variation(1, show_all_cams=True, draw_connections=False, style="standard")
    # Var 2: Show all cams, groups highlighted, with connecting edges
    generate_variation(2, show_all_cams=True, draw_connections=True, style="standard")
    # Var 3: ONLY show the grouped cameras for maximum clarity in paper
    generate_variation(3, show_all_cams=False, draw_connections=True, style="minimal")
    print("Done!")
