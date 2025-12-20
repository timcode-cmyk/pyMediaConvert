import requests
import json
import base64
import logging
import os

# ================= 配置区域 =================
API_KEY = "sk_faa835e10f52055038aaec1b79102df20bb8b8fd6de0604d"
VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
TEXT = "इस प्रार्थना को न छोड़िए प्रिय परमेश्वर, आपका धन्यवाद। मेरा शरीर कभी-कभी बीमार हो जाता है, परन्तु फिर भी मैं काम कर सकता हूँ। कभी-कभी मुझे रात में ठीक से नींद नहीं आती, परन्तु फिर भी मैं जाग सकता हूँ और एक नए दिन का सामना कर सकता हूँ। "
OUTPUT_AUDIO = "test_speech.mp3"
OUTPUT_SRT = "test_subtitles.srt"

# 字幕设置
MAX_CHARS_PER_LINE = 35  # 印地语建议放宽，单行约 35 字符
# ============================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("elevenlabs_run.log"), logging.StreamHandler()]
)

class ElevenLabsIntegrated:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.elevenlabs.io/v1"
        self.headers = {"xi-api-key": api_key, "Content-Type": "application/json"}

    def get_remaining_quota(self):
        """检查账户余额"""
        try:
            response = requests.get(f"{self.base_url}/user/subscription", headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                remaining = data['character_limit'] - data['character_count']
                logging.info(f"📊 剩余额度: {remaining} 字符")
                return remaining
            else:
                logging.error(f"无法获取额度: {response.status_code}")
                return None
        except Exception as e:
            logging.error(f"获取额度请求异常: {e}")
            return None

    def generate_speech_with_timestamps(self, text, voice_id):
        """请求音频及时间戳数据"""
        url = f"{self.base_url}/text-to-speech/{voice_id}/with-timestamps"
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5, 
                "similarity_boost": 0.75
            }
        }
        logging.info("🚀 正在请求 ElevenLabs API...")
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=60)
            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"生成失败! 状态码: {response.status_code}, 内容: {response.text}")
                return None
        except Exception as e:
            logging.error(f"API 请求发生异常: {e}")
            return None

    def create_srt(self, alignment, filename):
        """针对印地语优化的字幕生成逻辑"""
        chars = alignment['characters']
        starts = alignment['character_start_times_seconds']
        ends = alignment['character_end_times_seconds']

        # 印地语标点处理
        HINDI_PUNC = [" ", "।", "？", "?", "!", "！", ",", "，", '"', "“", "”"]
        SENTENCE_ENDERS = ["।", "？", "?", "!", "！"]

        sentences = []
        current_line_text = ""
        current_line_start = None
        current_word_text = ""
        current_word_start = None

        for i, char in enumerate(chars):
            # 记录当前单词/片段的起始点
            if current_word_start is None:
                current_word_start = starts[i]
            
            current_word_text += char

            # 判定条件：遇到分隔符 OR 文本末尾
            is_delimiter = char in HINDI_PUNC
            is_last_char = (i == len(chars) - 1)

            if is_delimiter or is_last_char:
                if current_line_start is None:
                    current_line_start = current_word_start
                
                current_line_text += current_word_text
                current_line_end = ends[i]

                # 判定是否触发换行切分
                is_sentence_end = char in SENTENCE_ENDERS
                is_too_long = len(current_line_text) >= MAX_CHARS_PER_LINE

                if is_sentence_end or is_too_long or is_last_char:
                    clean_text = current_line_text.strip()
                    if clean_text:
                        sentences.append({
                            "text": clean_text,
                            "start": current_line_start,
                            "end": current_line_end
                        })
                    # 重置行状态
                    current_line_text = ""
                    current_line_start = None
                
                # 重置单词状态
                current_word_text = ""
                current_word_start = None

        # 写入 SRT 文件
        with open(filename, "w", encoding="utf-8") as f:
            for idx, s in enumerate(sentences):
                f.write(f"{idx + 1}\n")
                f.write(f"{self._format_time(s['start'])} --> {self._format_time(s['end'])}\n")
                f.write(f"{s['text']}\n\n")
                
        logging.info(f"✅ 字幕文件已保存至: {filename} (共 {len(sentences)} 条记录)")

    def _format_time(self, seconds):
        """将秒数转换为 SRT 时间格式 HH:MM:SS,mmm"""
        mils = int((seconds % 1) * 1000)
        secs = int(seconds % 60)
        mins = int((seconds / 60) % 60)
        hours = int(seconds / 3600)
        return f"{hours:02d}:{mins:02d}:{secs:02d},{mils:03d}"

# ================= 运行脚本 =================
if __name__ == "__main__":
    app = ElevenLabsIntegrated(API_KEY)
    
    # 1. 检查初始额度
    app.get_remaining_quota()
    
    # 2. 生成语音和时间戳
    result = app.generate_speech_with_timestamps(TEXT, VOICE_ID)
    
    if result and 'audio_base64' in result:
        # 3. 保存音频文件
        try:
            audio_bytes = base64.b64decode(result['audio_base64'])
            with open(OUTPUT_AUDIO, "wb") as f:
                f.write(audio_bytes)
            logging.info(f"✅ 音频文件已保存至: {OUTPUT_AUDIO}")
        except Exception as e:
            logging.error(f"保存音频失败: {e}")
        
        # 4. 生成字幕文件
        if 'alignment' in result:
            app.create_srt(result['alignment'], OUTPUT_SRT)
        else:
            logging.warning("⚠️ 未能在响应中找到 alignment 数据，无法生成字幕。")
    
    # 5. 检查剩余额度
    app.get_remaining_quota()