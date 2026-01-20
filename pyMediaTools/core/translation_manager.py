"""
TranslationManager：翻译服务管理器

职责：
- 管理 Groq API 翻译调用
- 支持批量翻译分段
- 处理 API 错误和降级策略
- 记录翻译日志和缓存
"""

import os
import time
import requests
from ..logging_config import get_logger

logger = get_logger(__name__)


class TranslationManager:
    """
    翻译管理器，负责与 Groq API 交互并执行分段翻译
    """

    def __init__(self, api_key=None, model="openai/gpt-oss-120b"):
        """
        初始化翻译管理器

        Args:
            api_key (str, optional): Groq API Key。如果为 None，尝试从环境变量 GROQ_API_KEY 读取
            model (str): 使用的模型名称，默认 "openai/gpt-oss-120b"

        Examples:
            >>> tm = TranslationManager(api_key="xxx")
            >>> tm = TranslationManager()  # 从环境变量读取 API Key
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.timeout = 45  # Increased timeout for batches
        self.batch_size = 20  # Number of segments per request
        self.max_retries = 3  # Max retries for rate limits

    def is_available(self):
        """
        检查翻译服务是否可用

        Returns:
            bool: 如果 API Key 已配置返回 True
        """
        return bool(self.api_key)

    def translate_segments(self, segments):
        """
        批量翻译分段列表

        Args:
            segments (list): 分段列表，每个分段为 dict:
                           {
                               "text": "原文本",
                               "start": 1.5,
                               "end": 3.2,
                               ...  # 其他字段保持不变
                           }

        Returns:
            list: 翻译后的分段列表，文本字段已更新为中文翻译
                 如果翻译失败，则返回原始分段列表（不修改文本）

        Examples:
            >>> segments = [{"text": "hello", "start": 0, "end": 1}]
            >>> translated = tm.translate_segments(segments)
            >>> translated[0]["text"]
            '你好'
        """
        if not self.is_available():
            logger.warning("未找到 Groq API Key，跳过翻译。请在 config.toml 中配置 [groq] api_key。")
            return segments

        if not segments:
            return segments

        logger.info(f"正在进行智能分批处理: {len(segments)} 个片段 (模型: {self.model})")

        translated_segments = []
        for i in range(0, len(segments), self.batch_size):
            batch = segments[i : i + self.batch_size]
            batch_texts = [s.get("text", "") for s in batch]
            
            try:
                translated_texts = self._translate_batch(batch_texts)
                
                for idx, (original_seg, trans_text) in enumerate(zip(batch, translated_texts)):
                    updated_segment = original_seg.copy()
                    if trans_text:
                        updated_segment["text"] = trans_text
                    translated_segments.append(updated_segment)
                
                logger.debug(f"已处理批次: {i // self.batch_size + 1}, 集成 {len(batch)} 个片段")
            except Exception as e:
                logger.error(f"批次翻译失败: {e}")
                # Fallback to original segments if entire batch fails
                translated_segments.extend(batch)

        return translated_segments

    def _translate_batch(self, texts):
        """
        批量翻译文本列表
        """
        separator = "###SEG_SEP###"
        combined_text = f"\n{separator}\n".join(texts)
        
        system_prompt = (
            "You are a professional translator specializing in video subtitles. "
            f"Translate the following segments separated by '{separator}' into Simplified Chinese. "
            "Maintain the exact number of segments. "
            f"Output the translation for each segment separated by the same separator '{separator}'. "
            "Output ONLY the translated segments, no preamble or extra text."
        )

        try:
            result_raw = self._request_with_retry(system_prompt, combined_text)
            if not result_raw:
                return [None] * len(texts)
            
            # Split by separator and clean up
            translated_lines = [line.strip() for line in result_raw.split(separator)]
            
            # If the model added a trailing separator, the last element might be empty.
            # We only remove it if we have more lines than expected.
            if len(translated_lines) > len(texts) and not translated_lines[-1]:
                translated_lines.pop()
            
            # If we still have a mismatch, log it
            if len(translated_lines) != len(texts):
                logger.warning(f"翻译数量不匹配: 期望 {len(texts)}, 实际 {len(translated_lines)}")
                if len(translated_lines) > len(texts):
                    translated_lines = translated_lines[:len(texts)]
                else:
                    translated_lines.extend([None] * (len(texts) - len(translated_lines)))
            
            return translated_lines
        except Exception as e:
            logger.error(f"批量请求异常: {e}")
            return [None] * len(texts)

    def _request_with_retry(self, system_content, user_content):
        """
        带重试逻辑的 API 请求
        """
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            "model": self.model,
            "temperature": 0.3,
        }

        retry_count = 0
        backoff_delay = 5  # Initial backoff in seconds

        while retry_count <= self.max_retries:
            try:
                response = requests.post(self.base_url, json=payload, headers=headers, timeout=self.timeout)

                if response.status_code == 200:
                    res_json = response.json()
                    if "choices" in res_json and len(res_json["choices"]) > 0:
                        return res_json["choices"][0]["message"]["content"].strip()
                    return None
                elif response.status_code == 429:
                    retry_count += 1
                    if retry_count > self.max_retries:
                        logger.error("已达最大重试次数，仍产生 429 错误")
                        raise Exception("Rate limit exceeded and max retries reached")
                    
                    wait_time = backoff_delay * (2 ** (retry_count - 1))
                    logger.warning(f"触发 Groq 速率限制 (429)，将在 {wait_time} 秒后重试 ({retry_count}/{self.max_retries})...")
                    time.sleep(wait_time)
                else:
                    error_msg = f"Groq API Error: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)

            except (requests.Timeout, requests.RequestException) as e:
                logger.error(f"请求网络异常: {e}")
                retry_count += 1
                if retry_count > self.max_retries:
                    raise e
                time.sleep(2)
        
        return None

    def _translate_single(self, text):
        """
        翻译单个文本片段
        """
        system_content = "You are a professional translator. Translate the following text into Simplified Chinese. Output ONLY the translated text, no explanations."
        return self._request_with_retry(system_content, text)

    def set_model(self, model):
        """
        更改翻译模型

        Args:
            model (str): 新的模型名称

        Examples:
            >>> tm.set_model("mixtral-8x7b-32768")
        """
        self.model = model

    def set_timeout(self, timeout):
        """
        设置单次请求超时

        Args:
            timeout (float): 超时时间（秒）
        """
        self.timeout = timeout
