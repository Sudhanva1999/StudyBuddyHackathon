import google.generativeai as genai
import os
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure the Gemini API
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

def generate_notes(transcript_text):
    """
    Generate detailed lecture notes using Google's Gemini model.
    
    Args:
        transcript_text (str): The transcript text to generate notes from
        
    Returns:
        str: Generated notes in markdown format
    """
    try:
        # Initialize the model - using gemini-1.5-pro which is the latest supported model
        logger.info("Initializing Gemini model")
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        # Create the prompt
        prompt = f"""You are an AI that generates detailed, structured, and accurate lecture notes from transcriptions. 
        Minimum 2-3 page response is required. The format must be markdown that can be embedded into a website. 
        Add proper line breaks and bullet points for lists, subtopics, and lines to look it good. 
        You may add information that is not present in the transcription, but ensure it is relevant and accurate.

        Generate detailed and structured lecture notes from the following transcription:
        {transcript_text}

        Please follow these guidelines:
        - Organize the notes into clear sections (e.g., Introduction, Key Concepts, Examples, Summary)
        - Include definitions, explanations, and key points made by the lecturer
        - Ensure the notes are comprehensive, accurate, and coherent
        - Break down complex ideas into simpler terms
        - Use bullet points for lists and subtopics
        - If possible, highlight any key takeaways or important conclusions
        - Maintain the authenticity of the information provided in the transcription
        """
        
        # Generate the response
        logger.info("Generating content with Gemini")
        response = model.generate_content(prompt)
        logger.info("Content generation successful")
        
        # Save to file for caching
        with open("outputs/llm_output.txt", "w") as file:
            file.write(response.text)
            file.close()
        
        return response.text
    except Exception as e:
        logger.error(f"Error generating notes with Gemini: {str(e)}", exc_info=True)
        # Return a fallback response in case of error
        return f"Error generating notes: {str(e)}"

def generate_flashcards(transcript_text):
    """
    Generate flashcards from the transcript using Google's Gemini model.
    
    Args:
        transcript_text (str): The transcript text to generate flashcards from
        
    Returns:
        list: List of dictionaries containing question and answer pairs
    """
    try:
        # Initialize the model
        logger.info("Initializing Gemini model for flashcard generation")
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        # Create the prompt
        prompt = f"""Generate 10 meaningful flashcards from the following transcript. 
        Each flashcard should have a question on the front and the answer on the back.
        The questions should test understanding of key concepts, definitions, and important points.
        Format the response as a JSON array of objects with 'question' and 'answer' fields.

        Transcript:
        {transcript_text}

        Example format:
        [
            {{"question": "What is...?", "answer": "The answer is..."}},
            {{"question": "How does...?", "answer": "It works by..."}}
        ]

        Guidelines:
        - Create questions that test understanding, not just recall
        - Include a mix of definition, concept, and application questions
        - Keep answers concise but complete
        - Ensure questions are clear and unambiguous
        - Focus on the most important concepts from the transcript
        """
        
        # Generate the response
        logger.info("Generating flashcards with Gemini")
        response = model.generate_content(prompt)
        logger.info("Flashcard generation successful")
        
        # Parse the JSON response
        try:
            flashcards = json.loads(response.text)
            return flashcards
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing flashcard JSON: {str(e)}", exc_info=True)
            return []
            
    except Exception as e:
        logger.error(f"Error generating flashcards with Gemini: {str(e)}", exc_info=True)
        return [] 