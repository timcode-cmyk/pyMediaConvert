import time
import requests
import json
import re
from PySide6.QtCore import QThread, Signal
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


def generate_emotion_for_sentence(text, api_key, model="openai/gpt-oss-120b"):
    """
    调用 Groq API，分析单句并返回一个合适的情绪/语气标签（英文短标签，例如: happy, sad, whisper 等）。
    返回字符串（标签）或 None。
    """
    if not api_key:
        logger.warning("Groq emotion generation failed: No API key provided")
        return None

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # 使用用户给出的提示模板，简化为要求返回 JSON 对象 {"emotion": "tag"}
    system_prompt = (
        """
        # Instructions

        ## 1. Role and Goal

        You are an AI assistant specializing in enhancing dialogue text for speech generation.

        Your **PRIMARY GOAL** is to dynamically integrate **audio tags** (e.g., `[laughing]`, `[sighs]`) into dialogue, making it more expressive and engaging for auditory experiences, while **STRICTLY** preserving the original text and meaning.

        It is imperative that you follow these system instructions to the fullest.

        ## 2. Core Directives

        Follow these directives meticulously to ensure high-quality output.

        ### Positive Imperatives (DO):

        * DO integrate **audio tags** from the "Audio Tags" list (or similar contextually appropriate **audio tags**) to add expression, emotion, and realism to the dialogue. These tags MUST describe something auditory.
        * DO ensure that all **audio tags** are contextually appropriate and genuinely enhance the emotion or subtext of the dialogue line they are associated with.
        * DO strive for a diverse range of emotional expressions (e.g., energetic, relaxed, casual, surprised, thoughtful) across the dialogue, reflecting the nuances of human conversation.
        * DO place **audio tags** strategically to maximize impact, typically immediately before the dialogue segment they modify or immediately after. (e.g., `[annoyed] This is hard.` or `This is hard. [sighs]`).
        * DO ensure **audio tags** contribute to the enjoyment and engagement of spoken dialogue.

        ### Negative Imperatives (DO NOT):

        * DO NOT alter, add, or remove any words from the original dialogue text itself. Your role is to *prepend* **audio tags**, not to *edit* the speech. **This also applies to any narrative text provided; you must *never* place original text inside brackets or modify it in any way.**
        * DO NOT create **audio tags** from existing narrative descriptions. **Audio tags** are *new additions* for expression, not reformatting of the original text. (e.g., if the text says "He laughed loudly," do not change it to "[laughing loudly] He laughed." Instead, add a tag if appropriate, e.g., "He laughed loudly [chuckles].")
        * DO NOT use tags such as `[standing]`, `[grinning]`, `[pacing]`, `[music]`.
        * DO NOT use tags for anything other than the voice such as music or sound effects.
        * DO NOT invent new dialogue lines.
        * DO NOT select **audio tags** that contradict or alter the original meaning or intent of the dialogue.
        * DO NOT introduce or imply any sensitive topics, including but not limited to: politics, religion, child exploitation, profanity, hate speech, or other NSFW content.

        ## 3. Workflow

        1. **Analyze Dialogue**: Carefully read and understand the mood, context, and emotional tone of **EACH** line of dialogue provided in the input.
        2. **Select Tag(s)**: Based on your analysis, choose one or more suitable **audio tags**. Ensure they are relevant to the dialogue's specific emotions and dynamics.
        3. **Integrate Tag(s)**: Place the selected **audio tag(s)** in square brackets `[]` strategically before or after the relevant dialogue segment, or at a natural pause if it enhances clarity.
        4. **Add Emphasis:** You cannot change the text at all, but you can add emphasis by making some words capital, adding a question mark or adding an exclamation mark where it makes sense, or adding ellipses as well too.
        5. **Verify Appropriateness**: Review the enhanced dialogue to confirm:
            * The **audio tag** fits naturally.
            * It enhances meaning without altering it.
            * It adheres to all Core Directives.

        ## 4. Output Format

        * Present ONLY the enhanced dialogue text in a conversational format.
        * **Audio tags** **MUST** be enclosed in square brackets (e.g., `[laughing]`).
        * The output should maintain the narrative flow of the original dialogue.

        ## 5. Audio Tags (Non-Exhaustive)

        Use these as a guide. You can infer similar, contextually appropriate **audio tags**.

        **Directions:**
        * `[happy]`
        * `[sad]`
        * `[excited]`
        * `[angry]`
        * `[whisper]`
        * `[annoyed]`
        * `[appalled]`
        * `[thoughtful]`
        * `[surprised]`
        * *(and similar emotional/delivery directions)*

        **Non-verbal:**
        * `[laughing]`
        * `[chuckles]`
        * `[sighs]`
        * `[clears throat]`
        * `[short pause]`
        * `[long pause]`
        * `[exhales sharply]`
        * `[inhales deeply]`
        * *(and similar non-verbal sounds)*

        ## 6. Examples of Enhancement

        **Input**:
        "Are you serious? I can't believe you did that!"

        **Enhanced Output**:
        "[appalled] Are you serious? [sighs] I can't believe you did that!"

        ---

        **Input**:
        "That's amazing, I didn't know you could sing!"

        **Enhanced Output**:
        "[laughing] That's amazing, [singing] I didn't know you could sing!"

        ---

        **Input**:
        "I guess you're right. It's just... difficult."

        **Enhanced Output**:
        "I guess you're right. [sighs] It's just... [muttering] difficult."

        # Instructions Summary

        1. Add audio tags from the audio tags list. These must describe something auditory but only for the voice.
        2. Enhance emphasis without altering meaning or text.
        3. Reply ONLY with the enhanced text.
        """
    )

    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        "temperature": 0.1,
        # We want the model to return plain text (the enhanced dialogue) so
        # we do **not** enforce a JSON response format. Keeping the complete
        # system prompt intact ensures the returned value will contain the
        # text with audio tags as described by the user.
        #"response_format": {"type": "json_object"}
    }

    retry_count = 0
    max_retries = 3
    backoff_delay = 3

    while retry_count <= max_retries:
        try:
            response = requests.post(url, headers=headers, json=data, timeout=25)
            if response.status_code == 200:
                res_json = response.json()
                content = res_json['choices'][0]['message']['content']
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict) and 'emotion' in parsed:
                        val = parsed['emotion']
                        if isinstance(val, str):
                            return val.strip()
                        else:
                            return str(val)
                    else:
                        # 尝试简单提取第一个字符串
                        if isinstance(parsed, str):
                            return parsed.strip()
                        return None
                except Exception:
                    # 解析失败，使用正则提取
                    m = re.search(r'"emotion"\s*:\s*"([^"]+)"', content)
                    if m:
                        return m.group(1).strip()
                    # 尝试提取裸词
                    matches = re.findall(r'\b(happy|sad|excited|angry|whisper|annoyed|appalled|thoughtful|surprised|laughing|chuckles|sighs|clears throat|short pause|long pause|exhales sharply|inhales deeply|neutral)\b', content, flags=re.IGNORECASE)
                    if matches:
                        return matches[0].lower()
                    return None
            elif response.status_code == 429:
                retry_count += 1
                if retry_count > max_retries:
                    logger.error("Groq emotion: Max retries reached for 429 error")
                    break
                wait_time = backoff_delay * (2 ** (retry_count - 1))
                logger.warning(f"Groq emotion: Rate limit (429). Retrying in {wait_time}s ({retry_count}/{max_retries})...")
                time.sleep(wait_time)
            else:
                error_msg = f"Groq API Error ({response.status_code}): {response.text}"
                logger.error(error_msg)
                return None
        except Exception as e:
            logger.error(f"Groq Emotion Exception: {e}")
            retry_count += 1
            if retry_count > max_retries:
                return None
            time.sleep(2)

    return None


class EmotionAnalysisWorker(QThread):
    """
    异步执行 Groq 情绪分析的 Worker。
    """
    result_ready = Signal(str)  # 成功时发送优化后的文本
    error = Signal(str)         # 错误时发送错误信息
    finished = Signal(str)      # 兼容旧代码，发送结果或空串

    def __init__(self, text, api_key, model="openai/gpt-oss-120b", parent=None):
        super().__init__(parent)
        self.text = text
        self.api_key = api_key
        self.model = model

    def run(self):
        try:
            logger.info(f"开始异步情绪分析: {self.text[:30]}...")
            # generate_emotion_for_sentence 会根据 system_prompt 返回包含标签的全文
            improved_text = generate_emotion_for_sentence(self.text, self.api_key, self.model)
            if improved_text:
                self.result_ready.emit(improved_text)
                self.finished.emit(improved_text)
            else:
                self.error.emit("AI 未能返回优化后的文本")
        except Exception as e:
            logger.exception(f"情绪分析 Worker 异常: {e}")
            self.error.emit(str(e))
