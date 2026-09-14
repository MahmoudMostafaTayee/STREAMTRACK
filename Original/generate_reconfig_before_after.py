"""
Generate Before/After reconfiguration topology maps for the paper.
Produces:
  1. map_reconfig_before.png  - Pre-reconfiguration (4 groups, Windows 0-1)
  2. map_reconfig_after.png   - Post-reconfiguration (Camera 30 outage, Windows 2-3)
  3. map_reconfig_combined.png - Side-by-side with arrow and annotations

Scenario: Camera 30 network outage at frame 180.
  BEFORE: 4 groups: [02,17], [01,11], [19,27], [21,25,30]
  AFTER:  Camera 30 isolated as standalone; links 21-30, 25-30 disabled.
          Groups: [02,17], [01,11], [19,27], [21,25], [30] (5 groups)
Measured reconfiguration latency: 337 ms (outage), 190 ms (recovery).
"""
import json
import os
import math
from PIL import Image, ImageDraw, ImageFont

def get_base_paths():
    base_path = r'c:\OURs\Thesis\Real-Time_Multi-Camera_People_Tracking_using_Event_Stream_Processing\Original\scene_001'
    calib_path = os.path.join(base_path, 'calibration.json')
    map_path = os.path.join(base_path, 'map.png')
    return base_path, calib_path, map_path

# Colors for groups
GROUP_COLORS = {
    "g1": {
        "fill": (0, 100, 255, 60),      # Blue cone
        "outline": '#0064FF',
        "text": '#002E7A',
    },
    "g2": {
        "fill": (0, 200, 50, 60),       # Green cone
        "outline": '#00C832',
        "text": '#005A16',
    },
    "g3": {
        "fill": (255, 140, 0, 60),      # Orange cone
        "outline": '#FF8C00',
        "text": '#A35600',
    },
    "g4": {
        "fill": (160, 32, 240, 60),     # Purple cone
        "outline": '#A020F0',
        "text": '#5A0080',
    },
    # Additional colors for post-reconfig states
    "g5": {  # Standalone cam 30 after outage (red/coral - isolated)
        "fill": (220, 60, 60, 55),
        "outline": '#DC3C3C',
        "text": '#8A1A1A',
    },
    "g6": {  # Standalone cam 11 after split (teal)
        "fill": (0, 180, 180, 40),
        "outline": '#00B4B4',
        "text": '#006666',
    },
    "g_merged": {  # Merged group (blue-orange gradient look -> use blue)
        "fill": (0, 100, 255, 50),
        "outline": '#0064FF',
        "text": '#002E7A',
    },
    "gray": {
        "fill": (150, 150, 150, 30),
        "outline": (200, 200, 200),
        "text": '#999999'
    }
}

def generate_topology_map(filename, groups, outlier_group=[], inactive_cameras=[], draw_connections=True, title_text=None):
    base_path, calib_path, map_path = get_base_paths()
    if not os.path.exists(calib_path) or not os.path.exists(map_path):
        print(f"Missing paths: {calib_path} or {map_path}")
        return None

    with open(calib_path, 'r') as f:
        data = json.load(f)

    img = Image.open(map_path)
    draw = ImageDraw.Draw(img)
    width, height = img.size

    try:
        font = ImageFont.truetype("arial.ttf", 26)
        title_font = ImageFont.truetype("arialbd.ttf", 32)
    except:
        font = ImageFont.load_default()
        title_font = font

    overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
    d_overlay = ImageDraw.Draw(overlay)

    sensors = data.get('sensors', [])
    group_points = {gkey: [] for gkey in groups.keys()}
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

    def draw_label(draw_obj, pos, text, fill_color, bg_color=(255, 255, 255, 220)):
        try:
            bbox = draw_obj.textbbox(pos, text, font=font)
            pad = 6
            draw_obj.rectangle([bbox[0]-pad, bbox[1]-pad, bbox[2]+pad, bbox[3]+pad], fill=bg_color, outline=fill_color, width=2)
        except AttributeError:
            w, h = draw_obj.textsize(text, font=font)
            draw_obj.rectangle([pos[0]-2, pos[1]-2, pos[0]+w+2, pos[1]+h+2], fill=bg_color, outline=fill_color)
        draw_obj.text(pos, text, fill=fill_color, font=font)

    def get_group_info(cam_id):
        if cam_id in inactive_cameras:
            return None, None
        for gkey, cam_list in groups.items():
            if cam_id in cam_list:
                return gkey, GROUP_COLORS.get(gkey, GROUP_COLORS["gray"])
        return None, None

    for cam in cam_data:
        cam_id = cam['id']
        u, v = cam['u'], cam['v']
        direction = cam['direction']
        
        is_inactive = cam_id in inactive_cameras
        gkey, gcolors = get_group_info(cam_id)
        is_outlier = cam_id in outlier_group
        is_grouped = gkey is not None
        is_important = is_grouped or is_outlier or is_inactive
        
        if is_inactive:
            color_fill = (150, 150, 150, 20)
            color_outline = '#777777'
            text_color = '#777777'
        elif is_grouped:
            color_fill = gcolors["fill"]
            color_outline = gcolors["outline"]
            text_color = gcolors["text"]
            group_points[gkey].append((u, v))
        elif is_outlier:
            color_fill = (255, 0, 0, 150)
            color_outline = '#FF0000'
            text_color = '#990000'
        else:
            color_fill = (150, 150, 150, 20)
            color_outline = (220, 220, 220)
            text_color = '#CCCCCC'

        # Draw FOV cone
        math_angle = 90 - direction
        fov_angle = 60
        cone_length = 110 if is_important else 60
        
        angle_start = math_angle - (fov_angle / 2)
        angle_end = math_angle + (fov_angle / 2)
        
        p1 = (u + cone_length * math.cos(math.radians(angle_start)), 
              v - cone_length * math.sin(math.radians(angle_start)))
        p2 = (u + cone_length * math.cos(math.radians(angle_end)), 
              v - cone_length * math.sin(math.radians(angle_end)))
        
        d_overlay.polygon([(u, v), p1, p2], fill=color_fill, outline=(255, 255, 255, 100))

        # Camera node
        radius = 11 if is_important else 4
        node_outline = 'white'
        if is_inactive:
            node_outline = '#CCCCCC'
        draw.ellipse([u - radius, v - radius, u + radius, v + radius], fill=color_outline, outline=node_outline, width=2)
        
        # Draw text labels
        if is_important:
            short_name = f"Cam {cam_id[-2:]}" if "Camera_" in cam_id else cam_id
            if is_inactive:
                short_name += " (Offline)"
            
            text_offset_x = 15
            text_offset_y = -25
            
            if u > width/2: text_offset_x = -130 if is_inactive else -100
            if v > height/2: text_offset_y = 30

            label_pos = (u + text_offset_x, v + text_offset_y)
            bg_color = (240, 240, 240, 240) if is_inactive else (255, 255, 255, 240)
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
        
        for gkey, cam_list in groups.items():
            color_info = GROUP_COLORS.get(gkey, GROUP_COLORS["gray"])
            pts = group_points[gkey]
            if len(pts) >= 2:
                for i in range(len(pts)):
                    for j in range(i+1, len(pts)):
                        draw_dashed_line(final_draw, pts[i], pts[j], fill=color_info["outline"], width=4, dash_len=12)

    evidence_dir = r"c:\OURs\Thesis\Real-Time_Multi-Camera_People_Tracking_using_Event_Stream_Processing\paper\Evidence"
    if not os.path.exists(evidence_dir):
        os.makedirs(evidence_dir)
        
    out_path = os.path.join(evidence_dir, filename)
    final_img.convert('RGB').save(out_path)
    print(f"Saved {filename} to {out_path}")
    return out_path


def create_combined_figure(before_path, after_path, output_filename):
    """Create a side-by-side Before → After figure with title bar and arrow."""
    evidence_dir = r"c:\OURs\Thesis\Real-Time_Multi-Camera_People_Tracking_using_Event_Stream_Processing\paper\Evidence"
    
    before_img = Image.open(before_path)
    after_img = Image.open(after_path)
    
    # Scale both images to same size
    target_w = 720
    scale_b = target_w / before_img.width
    target_h = int(before_img.height * scale_b)
    before_img = before_img.resize((target_w, target_h), Image.LANCZOS)
    after_img = after_img.resize((target_w, target_h), Image.LANCZOS)
    
    # Layout parameters
    title_bar_h = 60
    subtitle_h = 40
    arrow_w = 80
    padding = 20
    border = 3
    
    total_w = padding + border*2 + target_w + padding + arrow_w + padding + border*2 + target_w + padding
    total_h = title_bar_h + padding + subtitle_h + border*2 + target_h + padding
    
    canvas = Image.new('RGB', (total_w, total_h), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    
    try:
        title_font = ImageFont.truetype("arialbd.ttf", 28)
        subtitle_font = ImageFont.truetype("arialbd.ttf", 20)
        arrow_font = ImageFont.truetype("arialbd.ttf", 18)
        detail_font = ImageFont.truetype("arial.ttf", 16)
    except:
        title_font = ImageFont.load_default()
        subtitle_font = title_font
        arrow_font = title_font
        detail_font = title_font
    
    # Title bar
    draw.rectangle([0, 0, total_w, title_bar_h], fill=(40, 40, 60))
    title_text = "Runtime Topology Reconfiguration (Zero-Downtime)"
    bbox = draw.textbbox((0, 0), title_text, font=title_font)
    tw = bbox[2] - bbox[0]
    draw.text(((total_w - tw) // 2, 15), title_text, fill=(255, 255, 255), font=title_font)
    
    # Left subtitle: "BEFORE"
    left_x = padding + border
    sub_y = title_bar_h + padding // 2
    draw.rectangle([left_x, sub_y, left_x + target_w, sub_y + subtitle_h], fill=(220, 235, 255))
    bbox_b = draw.textbbox((0, 0), "BEFORE — 4 Groups (Windows 0–1)", font=subtitle_font)
    stw = bbox_b[2] - bbox_b[0]
    draw.text((left_x + (target_w - stw) // 2, sub_y + 8), "BEFORE — 4 Groups (Windows 0–1)", fill=(0, 60, 140), font=subtitle_font)
    
    # Right subtitle: "AFTER"
    right_x = padding + border*2 + target_w + padding + arrow_w + padding
    draw.rectangle([right_x, sub_y, right_x + target_w, sub_y + subtitle_h], fill=(255, 235, 220))
    bbox_a = draw.textbbox((0, 0), "AFTER — Camera 30 Outage (Windows 2–3)", font=subtitle_font)
    stw_a = bbox_a[2] - bbox_a[0]
    draw.text((right_x + (target_w - stw_a) // 2, sub_y + 8), "AFTER — Camera 30 Outage (Windows 2–3)", fill=(180, 60, 0), font=subtitle_font)
    
    # Images with borders
    img_y = sub_y + subtitle_h
    
    # Left border
    draw.rectangle([left_x - border, img_y, left_x + target_w + border, img_y + target_h + border*2], outline=(0, 80, 180), width=border)
    canvas.paste(before_img, (left_x, img_y + border))
    
    # Right border  
    draw.rectangle([right_x - border, img_y, right_x + target_w + border, img_y + target_h + border*2], outline=(200, 80, 0), width=border)
    canvas.paste(after_img, (right_x, img_y + border))
    
    # Arrow in the middle
    arrow_cx = padding + border*2 + target_w + padding + arrow_w // 2
    arrow_cy = img_y + target_h // 2
    
    # Draw arrow body
    arrow_len = 40
    draw.line([(arrow_cx - arrow_len//2, arrow_cy), (arrow_cx + arrow_len//2, arrow_cy)], fill=(60, 60, 60), width=4)
    # Arrow head
    draw.polygon([
        (arrow_cx + arrow_len//2 + 15, arrow_cy),
        (arrow_cx + arrow_len//2 - 5, arrow_cy - 12),
        (arrow_cx + arrow_len//2 - 5, arrow_cy + 12)
    ], fill=(60, 60, 60))
    
    # Arrow label
    reconfig_text = "Reconfig"
    bbox_r = draw.textbbox((0, 0), reconfig_text, font=arrow_font)
    rtw = bbox_r[2] - bbox_r[0]
    draw.text((arrow_cx - rtw // 2, arrow_cy - 30), reconfig_text, fill=(60, 60, 60), font=arrow_font)
    
    latency_text = "337 ms"
    bbox_l = draw.textbbox((0, 0), latency_text, font=detail_font)
    ltw = bbox_l[2] - bbox_l[0]
    draw.text((arrow_cx - ltw // 2, arrow_cy + 18), latency_text, fill=(120, 120, 120), font=detail_font)
    
    zero_text = "0 downtime"
    bbox_z = draw.textbbox((0, 0), zero_text, font=detail_font)
    ztw = bbox_z[2] - bbox_z[0]
    draw.text((arrow_cx - ztw // 2, arrow_cy + 38), zero_text, fill=(0, 140, 0), font=detail_font)
    
    recovery_text = "Recovery: 190 ms"
    bbox_rec = draw.textbbox((0, 0), recovery_text, font=detail_font)
    rtw = bbox_rec[2] - bbox_rec[0]
    draw.text((arrow_cx - rtw // 2, arrow_cy + 58), recovery_text, fill=(100, 100, 180), font=detail_font)
    
    out_path = os.path.join(evidence_dir, output_filename)
    canvas.save(out_path)
    print(f"Saved combined figure to {out_path}")
    return out_path


if __name__ == "__main__":
    print("Generating Before/After Reconfiguration Maps...")
    
    # === BEFORE: Original 4-group topology ===
    before_groups = {
        "g1": ['Camera_02', 'Camera_17'],        # Blue: Group C
        "g2": ['Camera_01', 'Camera_11'],         # Green: Group A
        "g3": ['Camera_19', 'Camera_27'],         # Orange: Group D
        "g4": ['Camera_21', 'Camera_25', 'Camera_30']  # Purple: Group E
    }
    before_path = generate_topology_map(
        "map_reconfig_before.png", before_groups, [], 
        inactive_cameras=[], draw_connections=True
    )
    
    # === AFTER: Camera 30 outage (frame 180) ===
    # Camera 30 is isolated into its own standalone group.
    # Links 21-30 and 25-30 are disabled. All other groups unchanged.
    after_groups = {
        "g1": ['Camera_02', 'Camera_17'],              # Blue: unchanged
        "g2": ['Camera_01', 'Camera_11'],               # Green: unchanged
        "g3": ['Camera_19', 'Camera_27'],               # Orange: unchanged
        "g4": ['Camera_21', 'Camera_25'],               # Purple: split from Camera_30
        "g5": ['Camera_30'],                            # Orange-red: standalone
    }
    after_path = generate_topology_map(
        "map_reconfig_after.png", after_groups, [],
        inactive_cameras=[], draw_connections=True
    )
    
    # === COMBINED side-by-side figure ===
    if before_path and after_path:
        create_combined_figure(before_path, after_path, "map_reconfig_combined.png")
    
    print("Done!")
