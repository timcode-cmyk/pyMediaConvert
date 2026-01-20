import time
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

    retry_count = 0
    max_retries = 3
    backoff_delay = 5

    while retry_count <= max_retries:
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                res_json = response.json()
                content = res_json['choices'][0]['message']['content']
                
                # Attempt to parse JSON
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, list):
                        return parsed
                    elif isinstance(parsed, dict):
                        for key in parsed:
                            if isinstance(parsed[key], list):
                                return parsed[key]
                        return []
                    else:
                        return []
                except json.JSONDecodeError:
                    matches = re.findall(r'"([^"]+)"', content)
                    return matches
            elif response.status_code == 429:
                retry_count += 1
                if retry_count > max_retries:
                    logger.error("Groq Analysis: Max retries reached for 429 error")
                    break
                wait_time = backoff_delay * (2 ** (retry_count - 1))
                logger.warning(f"Groq Analysis: Rate limit (429). Retrying in {wait_time}s ({retry_count}/{max_retries})...")
                time.sleep(wait_time)
            else:
                error_msg = f"Groq API Error ({response.status_code}): {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
        except Exception as e:
            logger.error(f"Groq Analysis Exception: {e}")
            retry_count += 1
            if retry_count > max_retries:
                raise e
            time.sleep(2)
    
    return []
