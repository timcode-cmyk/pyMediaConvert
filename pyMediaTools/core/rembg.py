"""
图片/视频去背与处理工具

功能：
- 图片去背、绿幕/蓝幕合成
- 视频抠像 + 绿幕合成
- 支持单文件或文件夹输入
"""
import os
import io
import shutil
from pathlib import Path
import numpy as np
from PIL import Image
import cv2
import subprocess

from ..utils import get_ffmpeg_exe
from ..logging_config import get_logger

logger = get_logger(__name__)

# Try importing rembg, handle if not installed
try:
    from rembg import remove, new_session
    HAS_REMBG = True
except ImportError:
    HAS_REMBG = False
    logger.warning("rembg module not found. Background removal features will not work.")

class RembgProcessor:
    def __init__(self, model_name="u2net", bgcolor=(0, 255, 0, 255), monitor=None):
        if not HAS_REMBG:
            raise ImportError("Please install rembg first: pip install rembg[gpu] or pip install rembg")
        
        # Initialize session once
        try:
            self.session = new_session(model_name)
        except Exception as e:
            logger.error(f"Failed to initialize rembg session: {e}")
            raise e
            
        self.bgcolor = bgcolor # RGBA tuple
        self.monitor = monitor

    def process_file(self, input_path: Path, output_path: Path):
        """Dispatch processing based on file type"""
        suffix = input_path.suffix.lower()
        if suffix in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
            self.process_video(input_path, output_path)
        elif suffix in ['.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tiff']:
            self.process_image(input_path, output_path)
        else:
            logger.warning(f"Unsupported file type for background removal: {suffix}")

    def process_image(self, input_path: Path, output_path: Path):
        """Process a single image"""
        try:
            with open(input_path, 'rb') as f:
                img_data = f.read()
            
            # 1. Remove background
            # rembg returns bytes if input is bytes
            output_data = remove(img_data, session=self.session)
            
            # 2. Post-process (composite)
            img = Image.open(io.BytesIO(output_data)).convert("RGBA")
            
            if self.bgcolor:
                # Create solid background
                bg = Image.new("RGBA", img.size, self.bgcolor)
                # Composite
                result = Image.alpha_composite(bg, img)
                # If output format doesn't support alpha (like jpg), convert to RGB
                if output_path.suffix.lower() in ['.jpg', '.jpeg', '.bmp']:
                     result = result.convert("RGB")
            else:
                result = img
                # If output is jpg but we have transparency, we must fill it or error
                if output_path.suffix.lower() in ['.jpg', '.jpeg', '.bmp']:
                    # Fallback to white or black if user asked for transparent but saving as jpg
                    bg = Image.new("RGBA", result.size, (255, 255, 255, 255))
                    result = Image.alpha_composite(bg, result).convert("RGB")

            result.save(output_path)
            
            # Update monitor (images are atomic tasks)
            if self.monitor:
                self.monitor.update_file_progress(100, 100, input_path.name)
                
        except Exception as e:
            logger.error(f"Error processing image {input_path}: {e}")
            raise e

    def process_video(self, input_path: Path, output_path: Path):
        """Process video frame by frame"""
        cap = cv2.VideoCapture(str(input_path))
        if not cap.isOpened():
             raise RuntimeError(f"Could not open video: {input_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Temp file for video stream (no audio)
        temp_video = output_path.with_name(f"temp_rembg_{output_path.stem}.mp4")
        
        # Setup Video Writer
        # We use mp4v for generic mp4 compatibility. 
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(temp_video), fourcc, fps, (width, height))
        
        frame_idx = 0
        try:
            while True:
                if self.monitor and self.monitor.check_stop_flag():
                    break
                    
                ret, frame = cap.read()
                if not ret:
                    break
                
                # OpenCV uses BGR, PIL uses RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img_pil = Image.fromarray(frame_rgb)
                
                # 1. Remove background
                cutout = remove(img_pil, session=self.session)
                
                # 2. Composite
                if self.bgcolor:
                    bg = Image.new("RGBA", cutout.size, self.bgcolor)
                    comp = Image.alpha_composite(bg, cutout)
                    final_pil = comp.convert("RGB")
                else:
                    # Video transparency is tricky. Default to Black background if transparent requested for MP4.
                    # To support real transparency in video, we'd need ProRes 4444 or similar.
                    # Here we fallback to black to avoid crash.
                    bg = Image.new("RGBA", cutout.size, (0,0,0,0))
                    comp = Image.alpha_composite(bg, cutout)
                    final_pil = comp.convert("RGB") 

                # Convert back to BGR for OpenCV
                frame_bgr = cv2.cvtColor(np.array(final_pil), cv2.COLOR_RGB2BGR)
                out.write(frame_bgr)
                
                frame_idx += 1
                if self.monitor:
                     self.monitor.update_file_progress(frame_idx, total_frames, input_path.name)
                     
        except Exception as e:
            logger.error(f"Video processing error: {e}")
            raise e
        finally:
            cap.release()
            out.release()
            
        if self.monitor and self.monitor.check_stop_flag():
             if temp_video.exists():
                 os.remove(temp_video)
             return

        # 3. Merge Audio from source using FFmpeg
        logger.info("Merging audio...")
        try:
            self._merge_audio(input_path, temp_video, output_path)
        except Exception as e:
            logger.error(f"Audio merge failed: {e}")
            # If ffmpeg fails, fallback to just moving the video
            if temp_video.exists():
                if output_path.exists():
                    os.remove(output_path)
                shutil.move(temp_video, output_path)
        
        # Cleanup
        if temp_video.exists():
            os.remove(temp_video)

    def _merge_audio(self, src, video_no_audio, output):
        ffmpeg = get_ffmpeg_exe()
        # map 0:v (video from processed), map 1:a? (audio from src if exists)
        # -c:v copy (copy video stream), -c:a aac (re-encode audio to aac)
        cmd = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(video_no_audio),
            "-i", str(src),
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0?",
            "-shortest",
            str(output)
        ]
        
        # Using subprocess to avoid QProcess dependency in core logic if possible, 
        # or we could use the existing MediaConverter utils. Here we use subprocess for simplicity.
        # Windows requires creationflags to hide window.
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW
            
        subprocess.run(cmd, check=True, creationflags=creationflags)
