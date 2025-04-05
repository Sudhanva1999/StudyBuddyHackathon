from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging
from google_speech import transcribe_audio
from video_to_audio import convert_video_to_audio
from gemini_integration import generate_notes, generate_flashcards, generate_mindmap
import threading
import uuid
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from datetime import datetime, UTC
from dotenv import load_dotenv
from bson import ObjectId
from bson.json_util import dumps
from datetime import timezone
import json
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Define Upload & Output Folders
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
CACHE_FOLDER = "cache"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(CACHE_FOLDER, exist_ok=True)

# Set the default port
PORT = int(os.environ.get("PORT", 5001))

# Get GCS bucket name from environment variable
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "your-bucket-name")

# Store processing status and results
processing_tasks = {}

# app/__init__.py
load_dotenv()

app.config["MONGO_URI"] = os.getenv("MONGODB_URI")
mongo = PyMongo(app)

# Create indexes for email uniqueness
with app.app_context():
    try:
        mongo.db.users.create_index("email", unique=True)
        print("MongoDB connected successfully")
    except Exception as e:
        print(f"Error connecting to MongoDB: {str(e)}")

bcrypt = Bcrypt(app)

# app/models.py
class User:
    @staticmethod
    def create_user(firstname, lastname, email, password, role="student", profilepic="default-profile.png"):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            raise ValueError("Invalid email format")
        
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        
        # Check if email already exists
        if mongo.db.users.find_one({"email": email}):
            raise ValueError("Email already exists")
        
        user = {
            "firstname": firstname,
            "lastname": lastname,
            "email": email.lower(),
            "password": bcrypt.generate_password_hash(password).decode('utf-8'),
            "profilepic": profilepic,
            "role": role if role in ["student", "professor"] else "student",
            "timestamp": datetime.now(UTC),
            "history": []
        }
        
        result = mongo.db.users.insert_one(user)
        user["_id"] = result.inserted_id
        return user

    @staticmethod
    def get_user_by_email(email):
        return mongo.db.users.find_one({"email": email.lower()})

    @staticmethod
    def verify_password(stored_password_hash, provided_password):
        return bcrypt.check_password_hash(stored_password_hash, provided_password)

# MongoDB operators
PUSH = "$push"

class Metadata:
    @staticmethod
    def create_metadata(url_path, transcript="", notes=""):
        metadata = {
            "url_path": url_path,
            "transcript": transcript,
            "notes": notes,
            "chatJSON": [],
            "flashcardsJSON": []
        }
        
        result = mongo.db.metadata.insert_one(metadata)
        metadata["_id"] = result.inserted_id
        return metadata

    @staticmethod
    def add_chat_message(metadata_id, question, answer):
        chat_entry = {
            "question": question,
            "answer": answer,
            "timestamp": datetime.now(UTC)
        }
        
        mongo.db.metadata.update_one(
            {"_id": ObjectId(metadata_id)},
            {PUSH: {"chatJSON": chat_entry}}
        )

    @staticmethod
    def add_flashcard(metadata_id, question, answer):
        flashcard = {
            "question": question,
            "answer": answer,
            "lastReviewed": datetime.now(UTC)
        }
        
        mongo.db.metadata.update_one(
            {"_id": ObjectId(metadata_id)},
            {PUSH: {"flashcardsJSON": flashcard}}
        )

class History:
    @staticmethod
    def create_history(user_id, metadata_id):
        history = {
            "user": ObjectId(user_id),
            "metadata": ObjectId(metadata_id),
            "timestamp": datetime.now(UTC)
        }
        
        result = mongo.db.history.insert_one(history)
        
        # Add history reference to user
        mongo.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {PUSH: {"history": result.inserted_id}}
        )
        
        return history


def get_video_hash(video_name):
    """Generate a hash for the video name to use as a cache key"""
    return hashlib.md5(video_name.encode()).hexdigest()

def get_cached_results(video_name):
    """Check if results for this video are already cached"""
    video_hash = get_video_hash(video_name)
    cache_file = os.path.join(CACHE_FOLDER, f"{video_hash}.json")
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                logger.info(f"Retrieved cached results for video: {video_name}")
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading cache file: {str(e)}")
    
    return None

def save_to_cache(video_name, results):
    """Save results to cache for future use"""
    video_hash = get_video_hash(video_name)
    cache_file = os.path.join(CACHE_FOLDER, f"{video_hash}.json")
    
    try:
        with open(cache_file, 'w') as f:
            json.dump(results, f)
        logger.info(f"Saved results to cache for video: {video_name}")
    except Exception as e:
        logger.error(f"Error saving to cache: {str(e)}")

def process_video(task_id, video_path, audio_output):
    """Process video in background thread"""
    try:
        # Extract video name from the path
        video_name = os.path.basename(video_path).split('_', 1)[1] if '_' in os.path.basename(video_path) else os.path.basename(video_path)
        
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
        # summary = generate_summary(title, transcript["text"])
        
        processing_tasks[task_id]["status"] = "generating_notes"
        # Generate notes
        try:
            notes = generate_notes(f'Summary: {summary} \n\n\nNotes:\n{transcript["text"]}')
        except Exception as notes_error:
            logger.error(f"Error generating notes: {str(notes_error)}", exc_info=True)
            notes = f"Error generating notes: {str(notes_error)}"
            
        # Store results without generating flashcards
        results = {
            "transcript": transcript,
            "summary": summary,
            "notes": notes,
            "flashcards": []  # Initialize with empty flashcards array
        }
        
        # Save results to cache
        save_to_cache(video_name, results)
        
        processing_tasks[task_id]["status"] = "completed"
        processing_tasks[task_id]["results"] = results
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
    try:
        # Test MongoDB connection
        mongo.db.command("ping")
        return jsonify({"status": "running", "database": "connected"}), 200
    except Exception as e:
        logger.error(f"Health check error: {str(e)}", exc_info=True)
        return jsonify({
            "status": "running",
            "database": "disconnected",
            "error": str(e)
        }), 500

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
        
        # Check if this video is already in the cache
        cached_results = get_cached_results(file.filename)
        if cached_results:
            logger.info(f"Video {file.filename} found in cache, returning cached results")
            
            # Initialize task status with cached results
            processing_tasks[task_id] = {
                "status": "completed",
                "filename": file.filename,
                "results": cached_results,
                "cached": True
            }
            
            return jsonify({
                "message": "File found in cache",
                "task_id": task_id,
                "status": "completed",
                "cached": True
            }), 200

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
    
    # Add cache information if available
    if "cached" in task:
        response["cached"] = task["cached"]
    
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
            "flashcards_count": len(task.get("results", {}).get("flashcards", [])) if "results" in task and "flashcards" in task["results"] else 0,
            "cached": task.get("cached", False)
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
            
            # If this was a cached result, update the cache file
            if task.get("cached", False):
                video_name = task["filename"]
                save_to_cache(video_name, task["results"])
                logger.info(f"Updated cache for video: {video_name}")
        
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
            
            # If this was a cached result, update the cache file
            if task.get("cached", False):
                video_name = task["filename"]
                save_to_cache(video_name, task["results"])
                logger.info(f"Updated cache for video: {video_name}")
        
        return jsonify({
            "status": "success",
            "mindmap": mindmap
        }), 200
        
    except Exception as e:
        logger.error(f"Error generating mind map: {str(e)}", exc_info=True)
        return jsonify({"error": f"Error generating mind map: {str(e)}"}), 500
@app.route("/api/users", methods=["POST"])
def create_user():
    try:
        data = request.get_json()
        user = User.create_user(
            firstname=data["firstname"],
            lastname=data["lastname"],
            email=data["email"],
            password=data["password"],
            role=data.get("role", "student")
        )
        # Remove password from response
        user.pop("password", None)
        return jsonify({"message": "User created successfully", "user": dumps(user)}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        logger.info(f"Login attempt for email: {data.get('email', 'not provided')}")
        
        if not data or "email" not in data or "password" not in data:
            logger.error("Missing email or password in login request")
            return jsonify({"error": "Email and password are required"}), 400
            
        user = User.get_user_by_email(data["email"])
        logger.info(f"User found: {bool(user)}")
        
        if not user:
            logger.info("User not found")
            return jsonify({"error": "Invalid email or password"}), 401
            
        if not User.verify_password(user["password"], data["password"]):
            logger.info("Invalid password")
            return jsonify({"error": "Invalid email or password"}), 401
        
        # Remove password from response and serialize ObjectId
        user.pop("password", None)
        # Convert ObjectId to string
        user["_id"] = str(user["_id"])
        # Convert history ObjectIds to strings
        user["history"] = [str(h) for h in user["history"]]
        
        logger.info("Login successful")
        return jsonify({
            "message": "Login successful",
            "user": user
        }), 200
    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/metadata", methods=["POST"])
def create_metadata():
    try:
        data = request.get_json()
        metadata = Metadata.create_metadata(
            url_path=data["url_path"],
            transcript=data.get("transcript", ""),
            notes=data.get("notes", "")
        )
        # Convert ObjectId to string
        metadata["_id"] = str(metadata["_id"])
        return jsonify({
            "message": "Metadata created successfully",
            "metadata": metadata
        }), 201
    except Exception as e:
        logger.error(f"Metadata creation error: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/history", methods=["POST"])
def create_history():
    try:
        data = request.get_json()
        history = History.create_history(
            user_id=data["user_id"],
            metadata_id=data["metadata_id"]
        )
        return jsonify({"message": "History created successfully", "history": dumps(history)}), 201
    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500

# Example usage of adding chat messages and flashcards
@app.route("/api/metadata/<metadata_id>/chat", methods=["POST"])
def add_chat_message(metadata_id):
    try:
        data = request.get_json()
        Metadata.add_chat_message(
            metadata_id=metadata_id,
            question=data["question"],
            answer=data["answer"]
        )
        return jsonify({"message": "Chat message added successfully"}), 200
    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/metadata/<metadata_id>/flashcards", methods=["POST"])
def add_flashcard(metadata_id):
    try:
        data = request.get_json()
        Metadata.add_flashcard(
            metadata_id=metadata_id,
            question=data["question"],
            answer=data["answer"]
        )
        return jsonify({"message": "Flashcard added successfully"}), 200
    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    logger.info(f"🚀 Server running on http://127.0.0.1:{PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=True)
