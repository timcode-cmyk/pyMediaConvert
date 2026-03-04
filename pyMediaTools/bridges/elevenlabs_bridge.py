import os
import uuid
import datetime
from PySide6.QtCore import QObject, Signal, Slot, Property, QSettings, QTimer
from ..core.elevenlabs import (
    ModelListWorker, VoiceListWorker, QuotaWorker, TTSWorker, SFXWorker,
    ELEVENLABS_MODELS, LANGUAGE_CODES, EMOTION_DISPLAY_MAP
)
from ..utils import load_project_config
from ..logging_config import get_logger

logger = get_logger(__name__)

class ElevenLabsBridge(QObject):
    # API Load Signals
    modelsLoaded = Signal(list)
    voicesLoaded = Signal(list)
    quotaLoaded = Signal(int, int)  # usage, limit
    
    # Status Signals
    statusChanged = Signal()
    isBusyChanged = Signal()
    
    # Generation Signals
    generationSuccess = Signal(str, str) # file_path, type ('tts' or 'sfx')
    generationError = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_busy = False
        self._status_text = "就绪"
        
        # Load local settings
        self.eleven_settings = QSettings("pyMediaTools", "ElevenLabs")
        self.groq_settings = QSettings("pyMediaTools", "Groq")
        
        self.workers = []  # Keep references to prevent GC

    # --- Properties ---
    @Property(bool, notify=isBusyChanged)
    def isBusy(self):
        return self._is_busy

    def set_busy(self, busy, text=""):
        self._is_busy = busy
        self._status_text = text
        self.isBusyChanged.emit()
        self.statusChanged.emit()

    @Property(str, notify=statusChanged)
    def statusText(self):
        return self._status_text

    # --- Slots ---
    
    @Slot(result=dict)
    def getInitialSettings(self):
        """Returns previously saved settings, API keys, default values, etc."""
        cfg = load_project_config()
        env_key = os.getenv("ELEVENLABS_API_KEY", "")
        saved_key = self.eleven_settings.value("api_key", "")
        initial_key = env_key or saved_key or cfg.get("elevenlabs", {}).get("api_key", "")
        
        default_dir = self.eleven_settings.value("default_save_path", "")
        
        # Default styles matching the origin UI
        xml_styles = {
            'source': {
                'alignment': 'center', 'fontColor': (1.0, 1.0, 1.0, 1.0), 'font': 'Arial',
                'fontSize': 50, 'bold': False, 'italic': False, 'strokeColor': (0.0, 0.0, 0.0, 1.0),
                'strokeWidth': 2.0, 'useStroke': False, 'lineSpacing': 0, 'pos': -45,
                'shadowColor': (0.0, 0.0, 0.0, 0.5), 'shadowOffset': (2, 2), 'useShadow': True,
                'backgroundColor': (0.0, 0.0, 0.0, 0.0), 'useBackground': False, 'backgroundPadding': 0,
            },
            'translate': {
                'alignment': 'center', 'fontColor': (1.0, 1.0, 1.0, 1.0), 'font': 'Arial',
                'fontSize': 40, 'bold': False, 'italic': False, 'strokeColor': (0.0, 0.0, 0.0, 1.0),
                'strokeWidth': 2.0, 'useStroke': True, 'lineSpacing': 0, 'pos': -38,
                'shadowColor': (0.0, 0.0, 0.0, 0.5), 'shadowOffset': (2, 2), 'useShadow': True,
                'backgroundColor': (0.0, 0.0, 0.0, 0.0), 'useBackground': True, 'backgroundPadding': 0,
            },
            'highlight': {
                'alignment': 'center', 'fontColor': (1.0, 1.0, 0.0, 1.0), 'font': 'Arial',
                'fontSize': 50, 'bold': True, 'italic': False, 'strokeColor': (0.0, 0.0, 0.0, 1.0),
                'strokeWidth': 2.0, 'useStroke': False, 'lineSpacing': 0, 'pos': -45,
                'shadowColor': (0.0, 0.0, 0.0, 0.5), 'shadowOffset': (2, 2), 'useShadow': True,
                'backgroundColor': (0.0, 0.0, 0.0, 0.0), 'useBackground': False, 'backgroundPadding': 0,
            }
        }
        
        if 'xml_styles' in cfg and isinstance(cfg['xml_styles'], dict):
            for key, val in cfg['xml_styles'].items():
                if key in xml_styles and isinstance(val, dict):
                    xml_styles[key].update(val)

        return {
            "apiKey": initial_key,
            "groqApiKey": self.groq_settings.value("api_key", ""),
            "groqModel": self.groq_settings.value("model", "openai/gpt-oss-120b"),
            "defaultSavePath": default_dir,
            "ttsFileName": self._generate_filename("tts"),
            "sfxFileName": self._generate_filename("sfx"),
            "xmlStyles": xml_styles,
            "languageCodes": LANGUAGE_CODES,
            "emotionMap": EMOTION_DISPLAY_MAP,
            "videoSettings": {
                'fps': 30, 'width': 1080, 'height': 1920,
                'srt_pause_threshold': 0.2, 'srt_max_chars': 40
            },
            "voiceSettings": {
                'stability': 0.5, 'similarity_boost': 0.75, 'style': 0.0,
                'use_speaker_boost': True, 'speed': 1.0, 'language_code': ''
            }
        }

    @Slot(str)
    def saveApiKey(self, key):
        self.eleven_settings.setValue("api_key", key.strip())
        logger.info("ElevenLabs API key saved.")

    @Slot(str, str)
    def saveGroqSettings(self, key, model):
        self.groq_settings.setValue("api_key", key.strip())
        self.groq_settings.setValue("model", model.strip())
        logger.info("Groq settings saved.")

    @Slot(str)
    def setDefaultSavePath(self, path):
        self.eleven_settings.setValue("default_save_path", path)
        logger.info(f"Default save path set to: {path}")

    @Slot(str, result=str)
    def generateFilename(self, prefix):
        return self._generate_filename(prefix)

    def _generate_filename(self, prefix):
        return f"{prefix}_{datetime.date.today()}_{str(uuid.uuid4())[:4]}.mp3"

    @Slot(str)
    def loadApiData(self, api_key):
        """Loads Models, Voices, and Quota from ElevenLabs API."""
        if not api_key:
            self.generationError.emit("未提供 API Key")
            return
            
        self.set_busy(True, "正在加载模型、声音和额度...")
        
        # Track completion
        self._models_loaded = False
        self._voices_loaded = False
        
        self.model_worker = ModelListWorker(api_key)
        self.model_worker.finished.connect(self._on_models_finished)
        self.model_worker.error.connect(self._on_worker_error)
        
        self.voice_worker = VoiceListWorker(api_key)
        self.voice_worker.finished.connect(self._on_voices_finished)
        self.voice_worker.error.connect(self._on_worker_error)
        
        self.quota_worker = QuotaWorker(api_key)
        self.quota_worker.quota_info.connect(self.quotaLoaded.emit)
        self.quota_worker.error.connect(self._on_worker_error)
        
        self.workers.extend([self.model_worker, self.voice_worker, self.quota_worker])
        
        self.model_worker.start()
        self.voice_worker.start()
        self.quota_worker.start()

    def _on_models_finished(self, models):
        self._models_loaded = True
        tts_models = [m for m in models if m.get('can_do_text_to_speech', False)]
        self.modelsLoaded.emit(tts_models)
        self._check_api_data_loaded()

    def _on_voices_finished(self, voices):
        self._voices_loaded = True
        formatted_voices = []
        for item in voices:
            if len(item) >= 3:
                name, vid, preview_url = item[:3]
            else:
                name, vid = item
                preview_url = None
            formatted_voices.append({"name": name, "voice_id": vid, "preview_url": preview_url})
        
        self.voicesLoaded.emit(formatted_voices)
        self._check_api_data_loaded()

    def _check_api_data_loaded(self):
        if self._models_loaded and self._voices_loaded:
            self.set_busy(False, "加载完成")
            self._cleanup_workers()

    def _on_worker_error(self, err_msg):
        self.set_busy(False, "错误")
        self.generationError.emit(err_msg)
        self._cleanup_workers()

    def _cleanup_workers(self):
        self.workers = [w for w in self.workers if w.isRunning()]

    @Slot(str)
    def refreshQuotaOnly(self, api_key):
        if not api_key:
             return
        worker = QuotaWorker(api_key)
        worker.quota_info.connect(self.quotaLoaded.emit)
        worker.error.connect(lambda msg: logger.warning(f"Quota fetch error: {msg}"))
        worker.finished.connect(lambda: self.workers.remove(worker) if worker in self.workers else None)
        self.workers.append(worker)
        worker.start()

    @Slot(dict)
    def generateTTS(self, params):
        """
        params = {
            'api_key': str,
            'voice_id': str,
            'text': str,
            'save_path': str,
            'translate': bool,
            'word_level': bool,
            'export_xml': bool,
            'words_per_line': int,
            'keyword_highlight': bool,
            'model_id': str,
            'language_code': str,
            'groq_api_key': str,
            'groq_model': str,
            'xml_styles': dict,
            'video_settings': dict,
            'voice_settings': dict
        }
        """
        cfg = load_project_config().get('elevenlabs', {})
        output_format = cfg.get('default_output_format')
        
        if not params.get("text"):
            self.generationError.emit("请输入要转换的文本。")
            return
            
        self.set_busy(True, "正在生成语音...")
        
        worker = TTSWorker(
            api_key=params.get("api_key", ""),
            voice_id=params.get("voice_id", ""),
            text=params.get("text", ""),
            save_path=params.get("save_path", ""),
            output_format=output_format,
            translate=params.get("translate", False),
            word_level=params.get("word_level", False),
            export_xml=params.get("export_xml", False),
            words_per_line=params.get("words_per_line", 1),
            groq_api_key=params.get("groq_api_key", ""),
            groq_model=params.get("groq_model", ""),
            xml_style_settings=params.get("xml_styles", {}),
            video_settings=params.get("video_settings", {}),
            keyword_highlight=params.get("keyword_highlight", False),
            voice_settings=params.get("voice_settings", {}),
            model_id=params.get("model_id"),
            language_code=params.get("language_code"),
            emotion=None # Emotion is embedded in text
        )
        worker.finished.connect(lambda path: self._on_generation_success(path, 'tts'))
        worker.error.connect(self._on_worker_error)
        worker.finished.connect(lambda: self.workers.remove(worker) if worker in self.workers else None)
        self.workers.append(worker)
        worker.start()

    @Slot(dict)
    def generateSFX(self, params):
        """
        params = {
            'api_key': str,
            'prompt': str,
            'duration': int,
            'save_path': str
        }
        """
        cfg = load_project_config().get('elevenlabs', {})
        output_format = cfg.get('default_output_format')
        
        prompt = params.get("prompt", "")
        if not prompt:
            self.generationError.emit("请输入音效描述。")
            return
            
        self.set_busy(True, "正在生成音效...")
        worker = SFXWorker(
            api_key=params.get("api_key", ""),
            prompt=prompt,
            duration=params.get("duration", 5),
            save_path=params.get("save_path", ""),
            output_format=output_format
        )
        worker.finished.connect(lambda path: self._on_generation_success(path, 'sfx'))
        worker.error.connect(self._on_worker_error)
        worker.finished.connect(lambda: self.workers.remove(worker) if worker in self.workers else None)
        self.workers.append(worker)
        worker.start()

    def _on_generation_success(self, file_path, gen_type):
        self.set_busy(False, "已保存")
        self.generationSuccess.emit(file_path, gen_type)
        # Refresh quota quietly since we just used some
        api_key = self.eleven_settings.value("api_key", "")
        if not api_key:
            api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.refreshQuotaOnly(api_key)

