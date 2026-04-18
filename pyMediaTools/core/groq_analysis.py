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
        请严格按照以下规范处理我接下来发给你的文本，以便用于 ElevenLabs 高质量语音合成：
        📌 1. 数字处理（数值情境自然融入朗读节奏）
        所有阿拉伯数字必须全部转换为对应语言的书写形式（例：3 → 三，37 → 三十七）。
        即使在年份、年龄、时间等情境中也要转换（如 „2023年” → „二零二三年”）。
        📌 2. 表情符号处理
        文本中如有 emoji 或任何图形符号，一律彻底删除，不保留空格或替代字符。
        禁止出现残留的符号如“⭐”、“😭”或“❤️”。
        📌 3. 文本保持完整无损
        保持原文大小写、标点与结构完全一致。
        不做任何语义改写、删减或意译。
        所有逗号、句号、引号等必须完整保留，不可丢失。
        📌 4. 情绪标签设计与添加（专用于 ElevenLabs 情感调控）
        根据文本语义与叙述情境，准确判断并添加情绪标签，标签必须放在应读出该情绪的词前。
        标签格式为方括号英文标签，如：
        [Sad]（伤感）
        [Crying]（哽咽/哭腔）
        [Hopeful]（充满希望）
        [Whispering]（低声祷告）
        [Happy]（开心）
        [Gentle]（温柔）
        标签紧贴其后单词（中间无空格），如：
        Ea[whispering]se roagă...
        标签只用于引导语音语气，不要读出。
        情绪标签可结合段落节奏灵活调整，每段落可混合多种情绪，增强表达层次。
        对于重大情绪波动（如事故、祈祷、思念、痛苦），适当加入强标签如 [Sad crying voice]、[sobs] 等，引导合成器表达人类感受。
        📌 5. 段落格式与朗读节奏控制
        所有段落必须合并为一个整体段落，确保朗读连贯、节奏自然。
        不要插入空行，句子之间仅用正常标点断句。
        避免朗读中出现不自然停顿或跳段。
        📌 6. 结尾特殊处理
        文本最后一句最后一个标点后必须添加三个英文句号 ...（即使句子已经完整结束），防止 ElevenLabs 在尾句被意外截断。输入...有时候会读出来一些语气词，也可以回车键空两行可以起延时作用。
        📌 7. 最终检查要求（务必执行）
        在输出最终文本前，请严格进行以下核查：
        ✅ 所有数字是否已正确转换为罗马尼亚语拼写
        ✅ 所有 emoji 是否已移除干净
        ✅ 文本语义是否 100% 保持无改动
        ✅ 所有情绪标签位置、格式、语境是否合适
        ✅ 文本是否合并为一整段，无中断、无断行
        ✅ 尾句是否已添加 ... 做朗读保护
        🔄 返回要求：
        请返回只包含处理后的纯净文本本体，不包含解释、不附带注释或额外说明。

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
                # 尝试解析为 JSON
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict) and 'emotion' in parsed:
                        val = parsed['emotion']
                        return str(val).strip()
                    elif isinstance(parsed, str):
                        return parsed.strip()
                except Exception:
                    pass

                # 如果不是标准 JSON，尝试查找到 "emotion": "..." 这种正则匹配
                m = re.search(r'"emotion"\s*:\s*"([^"]+)"', content)
                if m:
                    return m.group(1).strip()
                
                # ⭐ 最终回退：直接返回全文。
                # 之前的代码会尝试通过正则提取 happy/sad 等裸词，
                # 这会导致在“优化情绪”时，如果文案中包含这些词，整段活文案会被截断只剩一个词。
                # 现在我们默认返回 AI 返回的所有内容，因为它遵循 system_prompt 的“返回全文”指令。
                return content.strip()
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
