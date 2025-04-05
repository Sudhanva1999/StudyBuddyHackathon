from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging
from google_speech import transcribe_audio
from video_to_audio import convert_video_to_audio
from summarize import generate_summary
from gemini_integration import generate_notes, generate_flashcards, generate_mindmap
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
            
        # Store results without generating flashcards
        processing_tasks[task_id]["status"] = "completed"
        processing_tasks[task_id]["results"] = {
            "transcript": transcript,
            "summary": summary,
            "notes": notes,
            "flashcards": []  # Initialize with empty flashcards array
        }
        logger.info(f"Task {task_id} completed. Transcript saved but flashcards not generated yet.")
        
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
        if "results" not in task:
            logger.error("Task marked as completed but no results found")
            response["error"] = "Results not found for completed task"
        else:
            logger.info(f"Results keys: {list(task['results'].keys())}")
            if "flashcards" in task["results"]:
                logger.info(f"Number of flashcards: {len(task['results']['flashcards'])}")
                if len(task["results"]["flashcards"]) == 0:
                    logger.warning("Flashcards array is empty")
            else:
                logger.warning("No flashcards key in results")
            response["results"] = task["results"]
    elif task["status"] == "error":
        logger.error(f"Task error: {task.get('error', 'Unknown error')}")
        response["error"] = task["error"]
    
    logger.info(f"Sending response: {response}")
    return jsonify(response), 200

@app.route("/debug/tasks", methods=["GET"])
def debug_tasks():
    """Debug endpoint to check the current state of processing tasks."""
    logger.info("Debug tasks endpoint accessed")
    
    # Create a simplified version of the tasks for debugging
    debug_tasks = {}
    for task_id, task in processing_tasks.items():
        debug_tasks[task_id] = {
            "status": task["status"],
            "filename": task.get("filename", "unknown"),
            "has_results": "results" in task,
            "results_keys": list(task.get("results", {}).keys()) if "results" in task else [],
            "flashcards_count": len(task.get("results", {}).get("flashcards", [])) if "results" in task and "flashcards" in task["results"] else 0
        }
    
    logger.info(f"Debug tasks response: {debug_tasks}")
    return jsonify(debug_tasks), 200

@app.route("/generate_flashcards/<task_id>", methods=["POST"])
def generate_flashcards_endpoint(task_id):
    """Generate flashcards for a specific task on demand."""
    logger.info(f"Flashcard generation requested for task_id: {task_id}")
    
    if task_id not in processing_tasks:
        logger.error(f"Task not found: {task_id}")
        return jsonify({"error": "Task not found"}), 404
    
    task = processing_tasks[task_id]
    
    # Check if the task is completed
    if task["status"] != "completed":
        logger.error(f"Cannot generate flashcards for task in status: {task['status']}")
        return jsonify({"error": f"Cannot generate flashcards for task in status: {task['status']}"}), 400
    
    # Check if we have the transcript
    if "results" not in task or "transcript" not in task["results"]:
        logger.error(f"No transcript found for task: {task_id}")
        return jsonify({"error": "No transcript found for this task"}), 400
    
    try:
        # Get the transcript text
        transcript_text = task["results"]["transcript"]["text"]
        
        # Generate flashcards
        logger.info(f"Generating flashcards for task {task_id}")
        flashcards = generate_flashcards(transcript_text)
        
        # Update the task results with the new flashcards
        if "results" in task:
            task["results"]["flashcards"] = flashcards
            logger.info(f"Updated task {task_id} with {len(flashcards)} flashcards")
        
        return jsonify({
            "status": "success",
            "flashcards": flashcards
        }), 200
        
    except Exception as e:
        logger.error(f"Error generating flashcards: {str(e)}", exc_info=True)
        return jsonify({"error": f"Error generating flashcards: {str(e)}"}), 500

@app.route("/generate_mindmap/<task_id>", methods=["POST"])
def generate_mindmap_endpoint(task_id):
    """Generate a mind map for a specific task on demand."""
    logger.info(f"Mind map generation requested for task_id: {task_id}")
    
    if task_id not in processing_tasks:
        logger.error(f"Task not found: {task_id}")
        return jsonify({"error": "Task not found"}), 404
    
    task = processing_tasks[task_id]
    
    # Check if the task is completed
    if task["status"] != "completed":
        logger.error(f"Cannot generate mind map for task in status: {task['status']}")
        return jsonify({"error": f"Cannot generate mind map for task in status: {task['status']}"}), 400
    
    # Check if we have the transcript
    if "results" not in task or "transcript" not in task["results"]:
        logger.error(f"No transcript found for task: {task_id}")
        return jsonify({"error": "No transcript found for this task"}), 400
    
    try:
        # Get the transcript text
        transcript_text = task["results"]["transcript"]["text"]
        
        # Generate mind map
        logger.info(f"Generating mind map for task {task_id}")
        mindmap = generate_mindmap(transcript_text)
        
        # Update the task results with the new mind map
        if "results" in task:
            task["results"]["mindmap"] = mindmap
            logger.info(f"Updated task {task_id} with mind map")
        
        return jsonify({
            "status": "success",
            "mindmap": mindmap
        }), 200
        
    except Exception as e:
        logger.error(f"Error generating mind map: {str(e)}", exc_info=True)
        return jsonify({"error": f"Error generating mind map: {str(e)}"}), 500

if __name__ == "__main__":
    logger.info(f"🚀 Server running on http://127.0.0.1:{PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=True)
