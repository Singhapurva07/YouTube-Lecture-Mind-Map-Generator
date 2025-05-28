from flask import Flask, request, render_template, jsonify
import google.generativeai as genai
import os
from dotenv import load_dotenv
import json
import subprocess
import tempfile
import shutil

app = Flask(__name__)

# Load environment variables from .env file
load_dotenv()
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in .env file")

# Configure the Gemini API with the API key
genai.configure(api_key=api_key)

# Function to extract transcript from a YouTube video using yt-dlp
def get_transcript(video_url):
    try:
        # Create a temporary directory to store the subtitle file
        temp_dir = tempfile.mkdtemp()
        subtitle_path = os.path.join(temp_dir, "subtitle")

        # Use yt-dlp to download the subtitle in English (auto-generated or manual)
        command = [
            "yt-dlp",
            "--write-auto-sub",
            "--write-sub",
            "--sub-lang", "en",
            "--skip-download",
            "--output", subtitle_path,
            video_url
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        print("yt-dlp output:", result.stdout)
        print("yt-dlp errors (if any):", result.stderr)

        # Look for the subtitle file (usually in .vtt or .srt format)
        for ext in [".en.vtt", ".en.srt"]:
            subtitle_file = f"{subtitle_path}{ext}"
            if os.path.exists(subtitle_file):
                with open(subtitle_file, 'r', encoding='utf-8') as f:
                    transcript = f.read()
                # Clean up the transcript (remove timestamps, formatting, etc.)
                lines = transcript.splitlines()
                cleaned_lines = []
                for line in lines:
                    # Skip timestamps, WEBVTT headers, and empty lines
                    if line.strip() and not line.startswith("WEBVTT") and not line.startswith("NOTE") and not "-->" in line:
                        cleaned_lines.append(line.strip())
                cleaned_transcript = " ".join(cleaned_lines)
                if cleaned_transcript:
                    print("Transcript extracted successfully:", cleaned_transcript[:100], "...")
                    return cleaned_transcript
                else:
                    print("Transcript file is empty after cleaning.")
                    return None

        print("No subtitle file found.")
        return None

    except Exception as e:
        print(f"Error fetching transcript with yt-dlp: {str(e)}")
        return None
    finally:
        # Clean up the temporary directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

# Route to serve the main page
@app.route('/')
def index():
    print("Serving index.html")
    return render_template('index.html')

# Route to generate mind map, explanation, and flowchart
@app.route('/generate', methods=['POST'])
def generate():
    youtube_link = request.form.get('youtube_link')
    user_summary = request.form.get('user_summary', '')
    print(f"Received request to /generate with youtube_link={youtube_link}, user_summary={user_summary}")

    if not youtube_link:
        print("No YouTube link provided")
        return jsonify({'error': 'No YouTube link provided'}), 400

    try:
        # Try to get the transcript using yt-dlp
        transcript = get_transcript(youtube_link)
        if not transcript:
            if user_summary:
                print("Using user-provided summary as transcript")
                transcript = user_summary
            else:
                print("Transcript retrieval failed, requesting user summary")
                return jsonify({
                    'error': 'Could not retrieve transcript for the video. Please provide a summary.',
                    'needs_summary': True
                }), 500

        print("Transcript or summary ready for processing:", transcript[:1000] or "Empty")

        # Prompt for generating the data
        prompt = f"""
Analyze the following content from a YouTube video: {transcript[:2000]}...
Generate:
1. A mind map in JSON format with a central topic, 3 main topics, and 2-3 subtopics each (notes up to 15 words).
2. A detailed explanation in Markdown using pointers (-), subtopics (*), and clear sections.
3. A flowchart in Mermaid syntax visualizing the key concepts and their relationships.
The mind map JSON structure:
{{
    "central_topic": "Main topic",
    "main_topics": [
        {{
            "title": "Main topic 1",
            "subtopics": [
                {{
                    "title": "Subtopic 1.1",
                    "notes": "Brief note"
                }}
            ]
        }}
    ]
}}
The explanation should be structured, e.g.:
    # Main Topic
    - Subtopic
      * 1. Description
The flowchart should use Mermaid syntax, e.g.:
    graph TD
        A[Central Topic] --> B[Main Topic 1.1]
        B --> C[Subtopic 1.1]
Return the response as JSON with 'mind_map', 'explanation', and 'flowchart' keys, wrapped in ```json:
```json
{{ ... }}
```
"""

        # Call the Gemini API
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        print("Raw API response from Gemini:", response.text)

        # Parse the API response
        result = response.text
        if result.startswith('```json') and result.endswith('```'):
            result = result[7:-3].strip()

        # Validate and parse JSON
        try:
            result_json = json.loads(result)
            required_fields = ['mind_map', 'explanation', 'flowchart']
            if not all(key in result_json for key in required_fields):
                raise ValueError(f"Missing required fields in API response: {required_fields}")
            print("Parsed API response:", result_json)
        except (json.JSONDecodeError, ValueError) as e:
            print("Parsing error:", str(e))
            # Fallback response
            result_json = {
                "mind_map": {
                    "central_topic": "Video Topic",
                    "main_topics": [
                        {
                            "title": "Concept Overview",
                            "subtopics": [
                                {"title": "Definition", "notes": "Basic concept explanation"},
                                {"title": "Importance", "notes": "Why it matters"}
                            ]
                        },
                        {
                            "title": "Key Elements",
                            "subtopics": [
                                {"title": "Element 1", "notes": "First main component"},
                                {"title": "Element 2", "notes": "Second main component"},
                                {"title": "Element 3", "notes": "Third main component"}
                            ]
                        },
                        {
                            "title": "Applications",
                            "subtopics": [
                                {"title": "Use Case 1", "notes": "Practical application 1"},
                                {"title": "Use Case 2", "notes": "Practical application 2"}
                            ]
                        }
                    ]
                },
                "explanation": """
# Video Topic Explanation

- **Concept Overview**
  * **Definition**: Explanation of the main concept from the video.
  * **Importance**: Why this concept is significant in its field.

- **Key Elements**
  * **Element 1**: First major component of the concept.
  * **Element 2**: Second major component of the concept.
  * **Element 3**: Third major component of the concept.

- **Applications**
  * **Use Case 1**: First practical application of the concept.
  * **Use Case 2**: Second practical application of the concept.
                """,
                "flowchart": """
graph TD
    A[Video Topic] --> B[Concept Overview]
    A --> C[Key Elements]
    A --> D[Applications]
    B --> B1[Definition]
    B --> B2[Importance]
    C --> C1[Element 1]
    C --> C2[Element 2]
    C --> C3[Element 3]
    D --> D1[Use Case 1]
    D --> D2[Use Case 2]
                """
            }
            print("Using fallback response due to parsing error")

        print("Returning result to frontend:", result_json)
        return jsonify(result_json)

    except Exception as e:
        print(f"API error in /generate: {str(e)}")
        return jsonify({'error': f'Failed to process video: {str(e)}'}), 500

# Route to generate quiz with 10 questions
@app.route('/generate_quiz', methods=['POST'])
def generate_quiz():
    youtube_link = request.form.get('youtube_link')
    user_summary = request.form.get('user_summary', '')
    print(f"Received request to /generate_quiz with youtube_link={youtube_link}, user_summary={user_summary}")

    if not youtube_link:
        print("No YouTube link provided")
        return jsonify({'error': 'No YouTube link provided'}), 400

    try:
        # Get the transcript
        transcript = get_transcript(youtube_link)
        if not transcript:
            if user_summary:
                print("Using user-provided summary as transcript")
                transcript = user_summary
            else:
                print("Transcript retrieval failed, requesting user summary")
                return jsonify({
                    'error': 'Could not retrieve transcript for the video. Please provide a summary.',
                    'needs_summary': True
                }), 500

        print("Transcript or summary ready for processing:", transcript[:1000] or "Empty")

        # Prompt for generating the quiz
        prompt = f"""
Based on the content of a YouTube video: {transcript[:2000]}...
Generate a quiz with exactly 10 multiple-choice questions, each with 4 options and a correct answer.
The quiz should be in JSON format:
{{
    "questions": [
        {{
            "question": "Question text?",
            "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
            "correct_answer": "Option 1"
        }}
    ]
}}
Return the response as JSON wrapped in ```json:
```json
{{ ... }}
```
"""

        # Call the Gemini API
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        print("Quiz API response from Gemini:", response.text)

        # Parse the API response
        result = response.text
        if result.startswith('```json') and result.endswith('```'):
            result = result[7:-3].strip()

        # Check for empty response
        if not result:
            print("Empty response from API")
            return jsonify({'error': 'Empty response from API'}), 500

        # Validate and parse JSON
        try:
            result_json = json.loads(result)
            if len(result_json.get("questions", [])) != 10:
                raise ValueError("Quiz does not contain exactly 10 questions")
            print("Parsed quiz response:", result_json)
        except (json.JSONDecodeError, ValueError) as err:
            print("Quiz parsing error:", str(err))
            # Fallback quiz (generic)
            result_json = {
                "questions": [
                    {
                        "question": "What is the main topic of the video?",
                        "options": ["Topic A", "Topic B", "Topic C", "Topic D"],
                        "correct_answer": "Topic A"
                    },
                    {
                        "question": "What is a key element discussed?",
                        "options": ["Element 1", "Element 2", "Element 3", "Element 4"],
                        "correct_answer": "Element 1"
                    },
                    {
                        "question": "What is one application mentioned?",
                        "options": ["Use Case 1", "Use Case 2", "Use Case 3", "Use Case 4"],
                        "correct_answer": "Use Case 1"
                    },
                    {
                        "question": "What does the main concept involve?",
                        "options": ["Concept A", "Concept B", "Concept C", "Concept D"],
                        "correct_answer": "Concept A"
                    },
                    {
                        "question": "What is the first subtopic covered?",
                        "options": ["Subtopic 1", "Subtopic 2", "Subtopic 3", "Subtopic 4"],
                        "correct_answer": "Subtopic 1"
                    },
                    {
                        "question": "What is the second subtopic covered?",
                        "options": ["Subtopic 1", "Subtopic 2", "Subtopic 3", "Subtopic 4"],
                        "correct_answer": "Subtopic 2"
                    },
                    {
                        "question": "What is a benefit of the concept?",
                        "options": ["Benefit A", "Benefit B", "Benefit C", "Benefit D"],
                        "correct_answer": "Benefit A"
                    },
                    {
                        "question": "What is a challenge mentioned?",
                        "options": ["Challenge A", "Challenge B", "Challenge C", "Challenge D"],
                        "correct_answer": "Challenge A"
                    },
                    {
                        "question": "What tool is related to the topic?",
                        "options": ["Tool A", "Tool B", "Tool C", "Tool D"],
                        "correct_answer": "Tool A"
                    },
                    {
                        "question": "What is the final takeaway?",
                        "options": ["Takeaway A", "Takeaway B", "Takeaway C", "Takeaway D"],
                        "correct_answer": "Takeaway A"
                    }
                ]
            }
            print("Using fallback quiz response due to parsing error")

        print("Returning quiz result to frontend:", result_json)
        return jsonify(result_json)

    except Exception as e:
        print(f"Quiz API error in /generate_quiz: {str(e)}")
        return jsonify({'error': f'Failed to generate quiz: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))