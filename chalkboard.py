import cv2
import numpy as np
import mediapipe as mp
import os
from datetime import datetime
from fpdf import FPDF
import time

class VirtualChalkboard:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        
        # display dims
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Create board 
        self.board = np.ones((self.height, self.width, 3), dtype=np.uint8) * np.array([40, 140, 40], dtype=np.uint8)
        
        self.drawing = False
        self.prev_point = None
        self.current_color = (255, 255, 255) 
        self.eraser_mode = False
        self.eraser_size = 20
        self.chalk_size = 4
        
        # HandTracking
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.5, min_tracking_confidence=0.5)
        self.mp_draw = mp.solutions.drawing_utils
        
        self.toolbar_height = 60
        
        offset = self.width - 550  # toolbar starting pos (right side)
        self.buttons = [
            {"name": "White", "color": (255, 255, 255), "position": (offset + 100, 30)},
            {"name": "Blue", "color": (255, 191, 0), "position": (offset + 200, 30)}, 
            {"name": "Yellow", "color": (0, 255, 255), "position": (offset + 300, 30)},
            {"name": "Eraser", "color": (100, 100, 100), "position": (offset + 400, 30)},
            {"name": "Clear", "color": (70, 70, 180), "position": (offset + 500, 30)}
        ]
        
        self.last_gesture_time = time.time()
        self.gesture_cooldown = 0.5  # sec
        
        print("Virtual Chalkboard initialized")
        print("Controls:")
        print("- Index finger: Draw")
        print("- Two fingers: Select tool")
        print("- Open palm: Clear board")
        print("- Press 's' to save board as PDF")
        print("- Press 'q' to quit")

    def create_toolbar(self, frame):
        cv2.rectangle(frame, (0, 0), (self.width, self.toolbar_height), (30, 120, 30), -1)
        
        for button in self.buttons:
            center = button["position"]
            color = button["color"]
            name = button["name"]
            
            cv2.circle(frame, center, 20, color, -1)
            cv2.circle(frame, center, 20, (200, 200, 200), 2)  
            
            cv2.putText(frame, name, (center[0] - 30, center[1] + 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)
            
            if (name == "Eraser" and self.eraser_mode) or (not self.eraser_mode and tuple(color) == self.current_color):
                cv2.circle(frame, center, 23, (0, 255, 0), 2)
    
    def draw_line(self, start_point, end_point):
        if self.eraser_mode:
            # bg color for eraser
            cv2.line(self.board, start_point, end_point, (40, 140, 40), self.eraser_size)
        else:
            cv2.line(self.board, start_point, end_point, self.current_color, self.chalk_size)
    
    def clear_board(self):
        self.board = np.ones((self.height, self.width, 3), dtype=np.uint8) * np.array([40, 140, 40], dtype=np.uint8)
    
    def export_to_pdf(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        img_path = f"chalkboard_{timestamp}.png"
        
        clean_board = self.board.copy()
        cv2.imwrite(img_path, clean_board)
        
        pdf = FPDF(orientation='L')  
        pdf.add_page()
        
        pdf.set_margins(0, 0, 0)
        
        pdf_w = pdf.w
        pdf_h = pdf.h
        
        pdf.image(img_path, x=0, y=0, w=pdf_w, h=pdf_h)
        
        pdf_path = f"chalkboard_{timestamp}.pdf"
        pdf.output(pdf_path)
        
        os.remove(img_path)
        
        print(f"PDF saved as {pdf_path}")
        return pdf_path
    
    def process_hand_gesture(self, results, display):
        if results.multi_hand_landmarks:
            hand_landmarks = results.multi_hand_landmarks[0]
            
            # Get fingertip positions
            index_fingertip = (int(hand_landmarks.landmark[8].x * self.width),
                              int(hand_landmarks.landmark[8].y * self.height))
            
            # Count how many fingers are up
            finger_tips = [8, 12, 16, 20]  # Indices for fingertips (without thumb)
            fingers_up = 0
            
            # Check thumb
            if hand_landmarks.landmark[4].x < hand_landmarks.landmark[3].x:
                fingers_up += 1
                
            # Check other fingers
            for tip in finger_tips:
                if hand_landmarks.landmark[tip].y < hand_landmarks.landmark[tip-2].y:
                    fingers_up += 1
            
            # Check if index finger is above toolbar
            is_above_toolbar = (index_fingertip[1] > self.toolbar_height)
            
            # Handle different gestures
            current_time = time.time()
            if current_time - self.last_gesture_time > self.gesture_cooldown:
                # One finger up (index) - Drawing mode
                if fingers_up == 1 and hand_landmarks.landmark[8].y < hand_landmarks.landmark[6].y:
                    if is_above_toolbar:
                        if not self.drawing:
                            self.drawing = True
                            self.prev_point = index_fingertip
                        else:
                            self.draw_line(self.prev_point, index_fingertip)
                            self.prev_point = index_fingertip
                    else:
                        self.drawing = False
                        self.prev_point = None
                
                # Two fingers up - Selection mode
                elif fingers_up == 2:
                    self.drawing = False
                    self.prev_point = None
                    
                    # Check if selecting from toolbar
                    if not is_above_toolbar:
                        for button in self.buttons:
                            center = button["position"]
                            # Calculate distance between finger and button center
                            distance = np.sqrt((index_fingertip[0] - center[0])**2 + 
                                             (index_fingertip[1] - center[1])**2)
                            
                            if distance < 25:  # If finger is within button radius
                                if button["name"] == "Eraser":
                                    self.eraser_mode = True
                                    self.last_gesture_time = current_time
                                elif button["name"] == "Clear":
                                    self.clear_board()
                                    self.last_gesture_time = current_time
                                else:  # Color selection
                                    self.current_color = button["color"]
                                    self.eraser_mode = False
                                    self.last_gesture_time = current_time
                
                # all fingers up then clear
                elif fingers_up >= 4:
                    self.drawing = False
                    self.prev_point = None
                    self.clear_board()
                    self.last_gesture_time = current_time
                
                else:
                    self.drawing = False
                    self.prev_point = None
    
    def run(self):
        while True:
            ret, frame = self.cap.read()
            if not ret:
                print("Failed to grab frame from webcam")
                break
                
            frame = cv2.flip(frame, 1)
            
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands.process(rgb_frame)
            
            webcam_small = cv2.resize(frame, (320, 240))
            
            display = self.board.copy()
            
            h, w = display.shape[:2]
            display[h-240:h, w-320:w] = webcam_small
            
            self.create_toolbar(display)
            
            if results.multi_hand_landmarks:
                hand_landmarks = results.multi_hand_landmarks[0]
                self.mp_draw.draw_landmarks(display, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                self.process_hand_gesture(results, display)
            
            cv2.imshow("Virtual Chalkboard", display)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                self.export_to_pdf()
            elif key == ord('c'):
                self.clear_board()
        
        self.cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    chalkboard = VirtualChalkboard()
    chalkboard.run()