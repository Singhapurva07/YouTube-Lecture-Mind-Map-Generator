# YouTube-Lecture-Mind-Map-Generator
A Flask app that generates mind maps, explanations, flowcharts, and quizzes from YouTube video transcripts or user summaries.

Generate mind maps, explanations, flowcharts, and quizzes from YouTube videos using transcripts or summaries.

Setup

Clone the repo: git clone <repo-url>
Install dependencies: pip install flask google-generativeai python-dotenv yt-dlp
Add your Gemini API key in .env: GOOGLE_API_KEY=your_api_key
Run the app: python app.py
Access at http://localhost:8080
Usage

Enter a YouTube URL to generate content.
If transcript fails, provide a summary manually.
Requirements

Python 3.8+
yt-dlp for transcript extraction
Gemini API key
Note

Ensure videos have English captions for transcript retrieval.
