import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load API Key
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Configure Gemini
if api_key:
    genai.configure(api_key=api_key)

def generate_wellbeing_report(duration_minutes, total_blinks, avg_ear, dominant_emotion, emotion_breakdown, total_keys=0, total_mouse=0):
    """
    Sends session stats + interaction data to Gemini and returns a HTML-formatted report.
    """
    if not api_key:
        return "<h3>Error: Gemini API Key missing.</h3><p>Please check your .env file.</p>"

    # --- FIX: Sanitize Inputs (Handle NoneType error) ---
    # If database returns None, force it to be 0
    if total_keys is None: 
        total_keys = 0
    if total_mouse is None: 
        total_mouse = 0
    # ----------------------------------------------------

    # 1. Calculate Metrics
    blink_rate = round(total_blinks / (duration_minutes if duration_minutes > 0 else 1), 1)

    # 2. Determine Activity Level (Simple Heuristic)
    activity_level = "Low (Passive/Reading)"
    if total_keys > 50 or total_mouse > 5000:
        activity_level = "Moderate"
    if total_keys > 200 or total_mouse > 20000:
        activity_level = "High (Intense Focus)"

    # 3. Construct the Prompt
    prompt = f"""
    You are an AI Wellbeing Coach named 'FaceTheFacts'. 
    Analyze the following user data from a webcam monitoring session:
    
    - Session Duration: {duration_minutes} minutes
    - Total Blinks: {total_blinks} (Rate: {blink_rate} blinks/min)
    - Average Eye Openness (EAR): {avg_ear} (Low < 0.25 indicates fatigue)
    - Dominant Emotion: {dominant_emotion}
    - Emotion History: {emotion_breakdown}
    - **Work Activity:** {activity_level} 
      (Key Strokes: {total_keys}, Mouse Movement: {total_mouse}px)

    **Task:** Write a helpful, empathetic wellbeing report for this user.
    
    **Insight Logic:**
    - If 'Activity' is High but 'Blinks' are Low: Warn about "Computer Vision Syndrome" (staring while working).
    - If 'Activity' is Low and 'Emotion' is Neutral: They might be reading or passively watching.
    - If 'Activity' is High and 'Emotion' is Stressed: Suggest a break immediately.
    
    **Format Requirements:**
    - Use HTML tags (<h3>, <p>, <ul>, <li>, <strong>) for formatting.
    - DO NOT use Markdown (no # or *).
    - Keep it under 200 words.
    
    **Structure:**
    1. <h3>Session Summary</h3>: A quick observation of their focus, work intensity, and blinking.
    2. <h3>Emotional State</h3>: Analyze their mood based on the dominant emotion.
    3. <h3>Actionable Tips</h3>: Give 2 specific tips based on the data.
    """

    try:
        # Use the latest Flash model for speed
        model = genai.GenerativeModel('gemini-2.5-flash') 
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini Error: {e}")
        return f"<h3>AI Connection Error</h3><p>Could not generate report. Error details: {str(e)}</p>"