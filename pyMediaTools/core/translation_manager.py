"""
TranslationManager：翻译服务管理器

职责：
- 管理 Groq API 翻译调用
- 支持批量翻译分段
- 处理 API 错误和降级策略
- 记录翻译日志和缓存
"""

import os
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
        self.timeout = 30  # 单次请求超时（秒）

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

        # logger.info(f"正在使用 Groq ({self.model}) 翻译 {len(segments)} 个片段...")

        translated_segments = []
        for idx, segment in enumerate(segments):
            try:
                original_text = segment.get("text", "")
                translated_text = self._translate_single(original_text)

                if translated_text:
                    # 复制分段，更新文本
                    updated_segment = segment.copy()
                    updated_segment["text"] = translated_text
                    translated_segments.append(updated_segment)
                    logger.debug(f"[{idx + 1}/{len(segments)}] {original_text[:20]}... -> {translated_text[:20]}...")
                else:
                    # 翻译失败，保持原文本
                    translated_segments.append(segment)
                    logger.warning(f"[{idx + 1}/{len(segments)}] 翻译失败，保持原文本")
            except Exception as e:
                # 重新抛出异常，以便上层捕获并提示用户
                raise e

        return translated_segments

    def _translate_single(self, text):
        """
        翻译单个文本片段（内部方法）

        Args:
            text (str): 要翻译的文本

        Returns:
            str: 翻译后的文本；如果翻译失败返回 None

        Raises:
            Exception: 网络或 API 错误（调用者应捕获）
        """
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a professional translator. Translate the following text into Simplified Chinese. Output ONLY the translated text, no explanations.",
                },
                {"role": "user", "content": text},
            ],
            "model": self.model,
            "temperature": 0.3,
        }

        try:
            response = requests.post(self.base_url, json=payload, headers=headers, timeout=self.timeout)

            if response.status_code == 200:
                res_json = response.json()
                if "choices" in res_json and len(res_json["choices"]) > 0:
                    return res_json["choices"][0]["message"]["content"].strip()
                else:
                    error_msg = f"Groq 响应格式不符：{res_json}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
            else:
                error_msg = f"Groq API Error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)

        except requests.Timeout:
            error_msg = f"Groq 请求超时 ({self.timeout}s)"
            logger.error(error_msg)
            raise Exception(error_msg)
        except requests.RequestException as e:
            error_msg = f"Groq 请求异常：{e}"
            logger.error(error_msg)
            raise Exception(error_msg)

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
