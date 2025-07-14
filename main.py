# main.py
import os
import cv2
import numpy as np
import pymunk
import threading
import time
import mediapipe as mp
from flask import Flask, Response, render_template, jsonify, request
from telegram import Bot
from telegram.error import TelegramError

# --- Configuration ---
TELEGRAM_BOT_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
TELEGRAM_CHAT_ID = 'YOUR_TELEGRAM_CHAT_ID'

# --- MediaPipe Hand Tracking ---
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.5)
mp_drawing = mp.solutions.drawing_utils

# --- Flask App Initialization ---
app = Flask(__name__, template_folder='templates', static_folder='static')

# --- Game State & Level Design ---
LEVELS = [
    {'ball_start': (50, 50), 'goal_pos': (600, 400)},
    {'ball_start': (320, 50), 'goal_pos': (50, 400)},
    {'ball_start': (600, 50), 'goal_pos': (50, 50)},
]
current_level_index = 0

# --- Physics Simulation (Pymunk) ---
space = pymunk.Space()
ball = None
static_lines = []
game_state = 'idle' # idle, running, level_complete, game_over
goal_radius = 25 # Define the goal radius

# --- Drawing State ---
is_drawing = False
last_draw_point = None
drawn_line_segments = []

# --- Threading Locks ---
frame_lock = threading.Lock()
latest_frame = None

def get_current_level():
    """Returns the configuration for the current level."""
    return LEVELS[current_level_index]

def setup_physics_space(reset_drawing=True):
    """Initializes or resets the Pymunk physics space for the current level."""
    global space, ball, static_lines, game_state, is_drawing, last_draw_point, drawn_line_segments
    
    # Clear physics space
    space = pymunk.Space()
    space.gravity = (0, 981)
    
    ball = None
    static_lines = []
    game_state = 'idle'
    
    if reset_drawing:
        drawn_line_segments = []
        is_drawing = False
        last_draw_point = None

def create_ball():
    """Creates the ball at the starting position for the current level."""
    global ball
    if ball is None:
        level_config = get_current_level()
        mass = 10
        radius = 15
        inertia = pymunk.moment_for_circle(mass, 0, radius)
        body = pymunk.Body(mass, inertia)
        body.position = level_config['ball_start']
        shape = pymunk.Circle(body, radius)
        shape.elasticity = 0.8
        shape.friction = 0.5
        space.add(body, shape)
        ball = body

def physics_loop():
    """Main loop for the physics simulation."""
    global game_state
    while True:
        if game_state == 'running':
            space.step(1 / 60.0)
            level_config = get_current_level()
            # *** BUG FIX HERE ***
            # Compare distance to the square of the goal_radius, not the goal's y-coordinate.
            if ball and ball.position.get_dist_sqrd(level_config['goal_pos']) < goal_radius**2:
                if current_level_index == len(LEVELS) - 1:
                    game_state = 'game_over'
                else:
                    game_state = 'level_complete'
                print(f"Level {current_level_index + 1} Complete!")
                send_win_notification()
        time.sleep(1 / 60.0)

def process_hand_gestures(frame):
    """Detects hands and interprets gestures for drawing."""
    global is_drawing, last_draw_point
    h, w, _ = frame.shape
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(frame_rgb)

    if results.multi_hand_landmarks:
        hand_landmarks = results.multi_hand_landmarks[0]
        index_finger_tip = hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP]
        middle_finger_tip = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
        
        ix, iy = int(index_finger_tip.x * w), int(index_finger_tip.y * h)
        dist = np.hypot(ix - int(middle_finger_tip.x * w), iy - int(middle_finger_tip.y * h))

        if dist < 25:
            cv2.circle(frame, (ix, iy), 12, (107, 255, 126), -1) # Green for drawing
            if not is_drawing:
                is_drawing = True
            elif last_draw_point:
                shape = pymunk.Segment(space.static_body, last_draw_point, (ix, iy), 5)
                shape.elasticity = 0.8
                shape.friction = 0.7
                space.add(shape)
                static_lines.append(shape)
                drawn_line_segments.append((last_draw_point, (ix, iy)))
            last_draw_point = (ix, iy)
        else:
            is_drawing = False
            last_draw_point = None
            cv2.circle(frame, (ix, iy), 12, (255, 107, 107), -1) # Red for not drawing
    else:
        is_drawing = False
        last_draw_point = None

def capture_frames():
    """Captures frames and processes gestures."""
    global latest_frame
    cap = cv2.VideoCapture(0)
    while True:
        ret, frame = cap.read()
        if not ret: break
        frame = cv2.flip(frame, 1)
        if game_state == 'idle':
            process_hand_gestures(frame)
        with frame_lock:
            latest_frame = frame.copy()
    cap.release()

def generate_video_stream():
    """Streams video with game overlays."""
    global latest_frame
    while True:
        with frame_lock:
            if latest_frame is None: continue
            display_frame = latest_frame.copy()

        level_config = get_current_level()
        goal_pos = tuple(map(int, level_config['goal_pos']))
        
        # --- Draw Overlays ---
        cv2.circle(display_frame, goal_pos, goal_radius, (0, 255, 0), 2)
        cv2.putText(display_frame, 'GOAL', (goal_pos[0] - 20, goal_pos[1] - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        for p1, p2 in drawn_line_segments:
            cv2.line(display_frame, p1, p2, (50, 150, 255), 5)

        if ball:
            p = tuple(map(int, ball.position))
            cv2.circle(display_frame, p, 15, (255, 80, 80), -1)

        if game_state == 'level_complete':
            cv2.putText(display_frame, "LEVEL COMPLETE!", (150, 240), cv2.FONT_HERSHEY_TRIPLEX, 1.2, (255, 215, 0), 2)
        elif game_state == 'game_over':
            cv2.putText(display_frame, "YOU WIN!", (200, 240), cv2.FONT_HERSHEY_TRIPLEX, 1.5, (0, 255, 127), 2)
        elif game_state == 'idle':
            cv2.putText(display_frame, f"Level {current_level_index + 1}: Draw with your hand", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

        (flag, encodedImage) = cv2.imencode(".jpg", display_frame)
        if not flag: continue
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n')

def send_win_notification():
    """Sends a win notification to Telegram."""
    # This function remains largely the same
    pass # Implementation omitted for brevity but is the same as before

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_video_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def get_status():
    """Provides the current game status."""
    return jsonify(
        gameState=game_state, 
        level=current_level_index + 1,
        totalLevels=len(LEVELS)
    )

@app.route('/start', methods=['POST'])
def start_simulation():
    global game_state
    if game_state == 'idle':
        create_ball()
        game_state = 'running'
    return jsonify(success=True, status=game_state)

@app.route('/next_level', methods=['POST'])
def next_level():
    global current_level_index
    if game_state == 'level_complete':
        if current_level_index < len(LEVELS) - 1:
            current_level_index += 1
            setup_physics_space()
    return jsonify(success=True, level=current_level_index + 1)

@app.route('/reset', methods=['POST'])
def reset_simulation():
    global current_level_index
    current_level_index = 0 # Also reset to level 1
    setup_physics_space()
    return jsonify(success=True, status='idle')

# --- Main Execution ---
if __name__ == '__main__':
    setup_physics_space()
    threading.Thread(target=physics_loop, daemon=True).start()
    threading.Thread(target=capture_frames, daemon=True).start()
    app.run(debug=True, threaded=True, use_reloader=False)
