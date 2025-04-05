import openai


client = openai.OpenAI(api_key="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")


def generate_notes(transcript_text):

    # TO AVOID API CALLS
    # with open("outputs/llm_output.txt", "r") as file:
    #     text = file.read()
    #     print(text)
    #     file.close()
    #     return text


    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an AI that generates detailed, structured, and accurate lecture notes from transcriptions. Minimum 2-3 page response is required. The format must be markdown that can be embedded into a website. Add proper line breaks and bullet points for lists, subtopics, and lines to look it good. You may add information that is not present in the transcription, but ensure it is relevant and accurate."},
            {"role": "user", "content": f"Generate detailed and structured lecture notes from the following transcription:\n{transcript_text}\n\nPlease follow these guidelines:\n- Organize the notes into clear sections (e.g., Introduction, Key Concepts, Examples, Summary).\n- Include definitions, explanations, and key points made by the lecturer.\n- Ensure the notes are comprehensive, accurate, and coherent.\n- Break down complex ideas into simpler terms.\n- Use bullet points for lists and subtopics.\n- If possible, highlight any key takeaways or important conclusions.\n- Maintain the authenticity of the information provided in the transcription."}
        ]
    )
    # save into file
    with open("outputs/llm_output.txt", "w") as file:
        file.write(response.choices[0].message.content)
        file.close()
    
    return response.choices[0].message.content