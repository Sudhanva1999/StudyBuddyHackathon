# Cache Directory

This directory stores cached results for processed videos. Each video's results are stored in a JSON file named with the MD5 hash of the video filename.

## Structure

Each cache file contains:
- Transcript
- Summary
- Notes
- Flashcards (if generated)

## Usage

The cache is automatically checked when a video is uploaded. If the video has already been processed, the cached results are returned immediately without any processing or LLM calls.

## How It Works

1. When a video is uploaded, the system first checks if it exists in the cache
2. If found, the cached results are returned immediately
3. If not found, the video is processed and the results are saved to the cache for future use

## Cache Management

The cache is automatically managed by the application. No manual intervention is required. 