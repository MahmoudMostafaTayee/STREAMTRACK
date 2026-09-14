import json
import os
import math
from PIL import Image, ImageDraw, ImageFont

def generate_transition_map():
    base_path = r'c:\OURs\Thesis\Real-Time_Multi-Camera_People_Tracking_using_Event_Stream_Processing\Original\scene_001'
    calib_path = os.path.join(base_path, 'calibration.json')
    map_path = os.path.join(base_path, 'map.png')
    
    # Save the output directly into the paper's Evidence directory
    output_path = r'c:\OURs\Thesis\Real-Time_Multi-Camera_People_Tracking_using_Event_Stream_Processing\paper\Evidence\map_transition_flow.png'

    if not os.path.exists(calib_path) or not os.path.exists(map_path):
        print("Error: Required calibration or map files not found.")
        return

    with open(calib_path, 'r') as f:
        data = json.load(f)

    img = Image.open(map_path)
    width, height = img.size

    # Font setup
    try:
        font = ImageFont.truetype("arial.ttf", 26)
        large_font = ImageFont.truetype("arial.ttf", 30)
    except:
        font = ImageFont.load_default()
        large_font = ImageFont.load_default()

    # Overlay for transparent FOV cones
    overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
    d_overlay = ImageDraw.Draw(overlay)
    draw_base = ImageDraw.Draw(img)

    sensors = data.get('sensors', [])
    cam_data = []

    # Map the sensors to pixel positions
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
                try:
                    direction = float(attr['value'])
                except:
                    direction = 0
                break
                
        cam_data.append({
            'id': cam_id,
            'u': u, 'v': v,
            'direction': direction
        })

    # Cameras involved in the transition case study
    source_cam = 'Camera_12'
    target_cams = ['Camera_02', 'Camera_13', 'Camera_17']
    all_cams = [source_cam] + target_cams

    # Colors for highlighting
    colors = {
        "source": {
            "fill": (255, 69, 0, 75),       # OrangeRed cone
            "outline": '#FF4500',
            "text": '#B22222',
            "label": "Cam 12 (Isolated)"
        },
        "target": {
            "fill": (0, 150, 255, 75),      # Light blue cone
            "outline": '#0096FF',
            "text": '#004080',
        },
        "gray": {
            "fill": (150, 150, 150, 15),     # Grayed out cone
            "outline": (220, 220, 220),
            "text": '#CCCCCC'
        }
    }

    # Draw helper for text label with white background
    def draw_label(draw_obj, pos, text, fill_color, bg_color=(255, 255, 255, 240), outline_color=None):
        try:
            bbox = draw_obj.textbbox(pos, text, font=font)
            pad = 6
            rect = [bbox[0]-pad, bbox[1]-pad, bbox[2]+pad, bbox[3]+pad]
            draw_obj.rectangle(rect, fill=bg_color, outline=outline_color or fill_color, width=2)
        except AttributeError:
            pass
        draw_obj.text(pos, text, fill=fill_color, font=font)

    # Dictionary to keep pixel coordinates for connection arrows
    positions = {}

    # Compute display positions: nudge Camera_13 left, Camera_17 right
    # so their circle markers don't overlap on the map.
    NUDGE_PX = 16  # horizontal offset for overlapping cameras
    display_pos = {}  # cam_id -> (u, v) displayed marker position
    for cam in cam_data:
        cam_id = cam['id']
        u, v = cam['u'], cam['v']
        is_highlighted = (cam_id == source_cam or cam_id in target_cams)
        if is_highlighted:
            if cam_id == 'Camera_13':
                display_pos[cam_id] = (u - NUDGE_PX, v)
            elif cam_id == 'Camera_17':
                display_pos[cam_id] = (u + NUDGE_PX, v)
            else:
                display_pos[cam_id] = (u, v)
        # Always store the *actual* world position for arrow endpoints
        positions[cam_id] = (u, v)

    # 1. Draw FOV cones and nodes
    for cam in cam_data:
        cam_id = cam['id']
        u, v = cam['u'], cam['v']
        direction = cam['direction']
        
        is_source = cam_id == source_cam
        is_target = cam_id in target_cams
        is_highlighted = is_source or is_target
        
        # Display position (may be nudged for overlap)
        du, dv = display_pos.get(cam_id, (u, v))

        if is_source:
            info = colors["source"]
        elif is_target:
            info = colors["target"]
        else:
            info = colors["gray"]

        # Draw FOV cone (from the display position, which may be nudged apart)
        cone_origin_u, cone_origin_v = du, dv
        math_angle = 90 - direction
        fov_angle = 60
        cone_length = 130 if is_highlighted else 60
        
        angle_start = math_angle - (fov_angle / 2)
        angle_end = math_angle + (fov_angle / 2)
        
        p1 = (cone_origin_u + cone_length * math.cos(math.radians(angle_start)), 
              cone_origin_v - cone_length * math.sin(math.radians(angle_start)))
        p2 = (cone_origin_u + cone_length * math.cos(math.radians(angle_end)), 
              cone_origin_v - cone_length * math.sin(math.radians(angle_end)))
        
        d_overlay.polygon([(cone_origin_u, cone_origin_v), p1, p2], fill=info["fill"], outline=(255, 255, 255, 120))

        # --- Draw camera node (circle) at display position ---
        radius = 12 if is_highlighted else 4
        draw_base.ellipse([
            du - radius, dv - radius, du + radius, dv + radius
        ], fill=info["outline"], outline='white', width=2)

        # Draw label if highlighted
        if is_highlighted:
            label_text = f"Cam {cam_id[-2:]}"
            if is_source:
                label_text += " [Isolated Source]"
            else:
                label_text += " [Re-ID Target]"
                
            # Manual offsets: each camera's label goes to a different quadrant
            # so they don't overlap each other or the camera markers.
            if cam_id == 'Camera_17':
                text_offset_x = 20     # right of point
                text_offset_y = 50     # below point
            elif cam_id == 'Camera_13':
                text_offset_x = -220   # left of point
                text_offset_y = -50    # above point
            elif cam_id == 'Camera_02':
                text_offset_x = 20
                text_offset_y = -35
            else:
                text_offset_x = 20
                text_offset_y = -35
                
            label_pos = (du + text_offset_x, dv + text_offset_y)
            draw_label(draw_base, label_pos, label_text, info["text"], bg_color=(255, 255, 255, 255), outline_color=info["outline"])

    # Composite overlay
    final_img = Image.alpha_composite(img.convert('RGBA'), overlay)
    final_draw = ImageDraw.Draw(final_img)

    # 2. Draw Transition Directed Arrows
    # Helper to draw directed arrow between points
    def draw_arrow(d_obj, p_from, p_to, fill_color='#FF4500', width=5, arrow_len=20):
        x1, y1 = p_from
        x2, y2 = p_to
        
        angle = math.atan2(y2 - y1, x2 - x1)
        
        # Start and end offsets to avoid overlapping with camera circles (radius=12)
        offset_start = 18
        offset_end = 22
        
        x1_s = x1 + offset_start * math.cos(angle)
        y1_s = y1 + offset_start * math.sin(angle)
        x2_s = x2 - offset_end * math.cos(angle)
        y2_s = y2 - offset_end * math.sin(angle)
        
        # Draw the main line
        d_obj.line([(x1_s, y1_s), (x2_s, y2_s)], fill=fill_color, width=width)
        
        # Draw arrowhead (triangle) pointing to (x2_s, y2_s)
        arrow_angle = 25 # degrees
        p_left = (x2_s - arrow_len * math.cos(angle - math.radians(arrow_angle)),
                  y2_s - arrow_len * math.sin(angle - math.radians(arrow_angle)))
        p_right = (x2_s - arrow_len * math.cos(angle + math.radians(arrow_angle)),
                   y2_s - arrow_len * math.sin(angle + math.radians(arrow_angle)))
        
        d_obj.polygon([(x2_s, y2_s), p_left, p_right], fill=fill_color)

    # Draw transition arrows from Camera_12 to the targets
    if source_cam in positions:
        p_src = positions[source_cam]
        for target in target_cams:
            if target in positions:
                # Arrow target: use nudged display position if the camera was moved,
                # so the arrow points to the visible circle marker.
                p_tgt = display_pos.get(target, positions[target])
                # Draw thick, dark red arrow representing transition paths
                draw_arrow(final_draw, p_src, p_tgt, fill_color='#FF4500', width=6, arrow_len=22)

    # # Add a legend
    # legend_pos = (1000, 50)
    # legend_bg = (255, 255, 255, 240)
    # final_draw.rectangle([legend_pos[0], legend_pos[1], legend_pos[0]+420, legend_pos[1]+220], fill=legend_bg, outline='#333333', width=3)
    
    # # Legend text
    # final_draw.text((legend_pos[0]+20, legend_pos[1]+15), "Case Study: Transition Topology", fill='#111111', font=large_font)
    
    # # Legend icons
    # # Source
    # final_draw.ellipse([legend_pos[0]+25, legend_pos[1]+75, legend_pos[0]+45, legend_pos[1]+95], fill='#FF4500')
    # final_draw.text((legend_pos[0]+65, legend_pos[1]+70), "Isolated Source (Cam 12)", fill='#B22222', font=font)
    
    # # Target
    # final_draw.ellipse([legend_pos[0]+25, legend_pos[1]+125, legend_pos[0]+45, legend_pos[1]+145], fill='#0096FF')
    # final_draw.text((legend_pos[0]+65, legend_pos[1]+120), "Allowed Re-ID Targets (Cam 02, 13, 17)", fill='#004080', font=font)
    
    # # Transition path (arrow)
    # final_draw.line([(legend_pos[0]+20, legend_pos[1]+175), (legend_pos[0]+50, legend_pos[1]+175)], fill='#FF4500', width=5)
    # final_draw.polygon([(legend_pos[0]+50, legend_pos[1]+175), (legend_pos[0]+43, legend_pos[1]+169), (legend_pos[0]+43, legend_pos[1]+181)], fill='#FF4500')
    # final_draw.text((legend_pos[0]+65, legend_pos[1]+165), "Transitional Re-ID Path", fill='#FF4500', font=font)

    # Save final image
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    final_img.convert('RGB').save(output_path)
    print(f"Transition topology map successfully generated and saved to {output_path}")

if __name__ == "__main__":
    generate_transition_map()
