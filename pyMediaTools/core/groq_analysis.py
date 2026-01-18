import requests
import json
import re
from ..logging_config import get_logger

logger = get_logger(__name__)

def extract_keywords(text, api_key, model="openai/gpt-oss-120b"):
    """
    Analyzes the text and returns a list of keywords/phrases to highlight.
    """
    if not api_key:
        logger.warning("Groq API key extraction failed: No API key provided")
        return []

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    system_prompt = (
        "You are an expert content analyzer. Your task is to identify the most important keywords or short phrases "
        "in the provided text that should be highlighted for emphasis in a video subtitle. "
        "Select only the most impactful words (nouns, verbs, key adjectives). "
        "Return the result STRICTLY as a valid JSON object with a key 'keywords' containing the list of strings. "
        "Example: {\"keywords\": [\"freedom\", \"innovation\", \"future\"]}"
    )

    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"} 
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            res_json = response.json()
            content = res_json['choices'][0]['message']['content']
            
            # Attempt to parse JSON
            try:
                # Some models might wrap it in a key, but we asked for array. 
                # Let's try to find a list pattern if direct parse fails or if it returns an object.
                parsed = json.loads(content)
                
                if isinstance(parsed, list):
                    return parsed
                elif isinstance(parsed, dict):
                    # If it returns {"keywords": [...]}, try to extract
                    for key in parsed:
                        if isinstance(parsed[key], list):
                            return parsed[key]
                    return []
                else:
                    return []
            except json.JSONDecodeError:
                # Fallback Regex extraction if JSON is malformed
                matches = re.findall(r'"([^"]+)"', content)
                return matches
        else:
            error_msg = f"Groq API Error ({response.status_code}): {response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)
    except Exception as e:
        logger.error(f"Groq Analysis Exception: {e}")
        raise e
