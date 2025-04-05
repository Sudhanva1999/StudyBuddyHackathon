from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging
from google_speech import transcribe_audio
from video_to_audio import convert_video_to_audio
from summarize import generate_summary
from gemini_integration import generate_notes, generate_flashcards
import threading
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Define Upload & Output Folders
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Set the default port
PORT = int(os.environ.get("PORT", 5001))

# Get GCS bucket name from environment variable
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "your-bucket-name")

# Store processing status and results
processing_tasks = {}

def process_video(task_id, video_path, audio_output):
    """Process video in background thread"""
    try:
        processing_tasks[task_id]["status"] = "converting"
        # Convert video to audio
        convert_video_to_audio(video_path, audio_output)
        
        processing_tasks[task_id]["status"] = "transcribing"
        # Transcribe audio
        transcript = transcribe_audio(audio_output, bucket_name=GCS_BUCKET_NAME)
        
        if not transcript["text"]:
            processing_tasks[task_id]["status"] = "error"
            processing_tasks[task_id]["error"] = "Transcription failed"
            return
        
        # Generate title
        title = audio_output.split('/')[-1].split('.')[0]
        
        processing_tasks[task_id]["status"] = "summarizing"
        # Generate summary
        summary = generate_summary(title, transcript["text"])
        
        processing_tasks[task_id]["status"] = "generating_notes"
        # Generate notes
        try:
            notes = generate_notes(f'Summary: {summary} \n\n\nNotes:\n{transcript["text"]}')
        except Exception as notes_error:
            logger.error(f"Error generating notes: {str(notes_error)}", exc_info=True)
            notes = f"Error generating notes: {str(notes_error)}"
            
        # Generate flashcards
        try:
            flashcards = generate_flashcards(transcript["text"])
        except Exception as flashcard_error:
            logger.error(f"Error generating flashcards: {str(flashcard_error)}", exc_info=True)
            flashcards = []
        
        # Store results
        processing_tasks[task_id]["status"] = "completed"
        processing_tasks[task_id]["results"] = {
            "transcript": transcript,
            "summary": summary,
            "notes": notes,
            "flashcards": flashcards
        }
        
        # Clean up temporary files
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(audio_output):
            os.remove(audio_output)
            
    except Exception as e:
        logger.error(f"Error during processing: {str(e)}", exc_info=True)
        processing_tasks[task_id]["status"] = "error"
        processing_tasks[task_id]["error"] = str(e)
        # Clean up temporary files in case of error
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(audio_output):
            os.remove(audio_output)

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint to verify server status."""
    return jsonify({"status": "running"}), 200

@app.route("/upload", methods=["POST"])
def upload_video():
    """Handles video upload and initiates processing."""
    try:
        logger.info("Starting video upload process")
        
        if "video" not in request.files:
            logger.error("No video file in request")
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files["video"]
        if file.filename == "":
            logger.error("Empty filename received")
            return jsonify({"error": "No file selected"}), 400

        # Generate unique task ID
        task_id = str(uuid.uuid4())
        print("task_id", task_id)
        
        logger.info(f"Processing file: {file.filename}")
        video_path = os.path.join(UPLOAD_FOLDER, f"{task_id}_{file.filename}")
        audio_output = os.path.join(OUTPUT_FOLDER, f"{task_id}_{os.path.splitext(file.filename)[0]}.mp3")

        # Save video file
        logger.info("Saving video file")
        file.save(video_path)
        
        # Initialize task status
        processing_tasks[task_id] = {
            "status": "uploaded",
            "filename": file.filename
        }
        
        # Start processing in background thread
        thread = threading.Thread(
            target=process_video,
            args=(task_id, video_path, audio_output)
        )
        thread.start()
        
        return jsonify({
            "message": "File uploaded successfully",
            "task_id": task_id,
            "status": "uploaded"
        }), 200

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

@app.route("/status/<task_id>", methods=["GET"])
def get_status(task_id):
    """Get the status and results of a processing task."""
    logger.info(f"Status check requested for task_id: {task_id}")
    
    if task_id not in processing_tasks:
        logger.error(f"Task not found: {task_id}")
        return jsonify({"error": "Task not found"}), 404
        
    task = processing_tasks[task_id]
    logger.info(f"Current task status: {task['status']}")
    
    response = {
        "status": task["status"],
        "filename": task["filename"]
    }
    
    if task["status"] == "completed":
        logger.info("Task completed, including results in response")
        response["results"] = task["results"]
    elif task["status"] == "error":
        logger.error(f"Task error: {task.get('error', 'Unknown error')}")
        response["error"] = task["error"]
    
    logger.info(f"Sending response: {response}")
    return jsonify(response), 200

if __name__ == "__main__":
    logger.info(f"🚀 Server running on http://127.0.0.1:{PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=True)
