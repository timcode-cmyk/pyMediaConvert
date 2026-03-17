import os
import sys
import platform
import shutil
import zipfile
import tarfile
import requests
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import stat

def get_platform_info():
    os_name = platform.system().lower()
    arch = platform.machine().lower()
    
    # Normalize architecture names
    if arch in ['arm64', 'aarch64']:
        arch = 'arm64'
    elif arch in ['x86_64', 'amd64']:
        arch = 'x86_64'
    
    return os_name, arch

def download_file(url, dest_path):
    print(f"Downloading {url}...")

    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            # Set timeout for connect (10s) and read (60s)
            response = session.get(url, stream=True, timeout=(10, 60))
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = downloaded / total_size * 100
                            sys.stdout.write(f"\rProgress: {percent:.1f}% ({downloaded/1024/1024:.1f} MB)")
                            sys.stdout.flush()
            print(f"\nDownloaded to {dest_path}")
            return
        except Exception as e:
            print(f"\nDownload failed (attempt {attempt + 1}/{max_attempts}): {e}")
            if attempt == max_attempts - 1:
                raise
            time.sleep(2)

def extract_archive(archive_path, extract_to):
    print(f"Extracting {archive_path}...")
    if archive_path.endswith('.zip'):
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
    elif archive_path.endswith(('.tar.gz', '.tgz', '.tar.xz')):
        with tarfile.open(archive_path, 'r:*') as tar_ref:
            tar_ref.extractall(extract_to)
    print(f"Extracted to {extract_to}")

def make_executable(path):
    if platform.system() != 'Windows':
        st = os.stat(path)
        os.chmod(path, st.st_mode | stat.S_IEXEC)

def setup_binaries():
    os_name, arch = get_platform_info()
    print(f"Detected Platform: {os_name}, Architecture: {arch}")
    
    root_dir = os.path.dirname(os.path.abspath(__file__))
    bin_dir = os.path.join(root_dir, 'bin')
    os.makedirs(bin_dir, exist_ok=True)
    
    # URLs
    urls = {
        'ffmpeg': {
            'darwin': {
                'arm64': 'https://evermeet.cx/ffmpeg/ffmpeg-8.1.zip', # Direct link to 8.1 stable
            },
            'windows': {
                'x86_64': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'
            }
        },
        'ffprobe': {
            'darwin': {
                'arm64': 'https://evermeet.cx/ffmpeg/ffprobe-8.1.zip',
            }
        },
        # 'aria2': {
        #     'darwin': {
        #         'arm64': 'https://github.com/q3aql/aria2-static-builds/releases/download/v1.37.0/aria2-1.37.0-macos-arm64.tar.xz' # Removed the extra -1
        #     },
        #     'windows': {
        #         'x86_64': 'https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip'
        #     }
        # },
        'yt-dlp': 'https://github.com/yt-dlp/yt-dlp/archive/refs/heads/release.zip' # Use a specific version for stability
    }

    temp_dir = os.path.join(root_dir, 'temp_downloads')
    os.makedirs(temp_dir, exist_ok=True)

    try:
        # 1. Download and Setup ffmpeg/ffprobe
        if os_name == 'darwin' and arch == 'arm64':
            for tool in ['ffmpeg', 'ffprobe']:
                target_path = os.path.join(bin_dir, tool)
                if os.path.exists(target_path):
                    print(f"{tool} already exists, skipping download.")
                    continue
                zip_path = os.path.join(temp_dir, f"{tool}.zip")
                download_file(urls[tool]['darwin']['arm64'], zip_path)
                extract_archive(zip_path, bin_dir)
                make_executable(target_path)
        
        elif os_name == 'windows' and arch == 'x86_64':
            zip_path = os.path.join(temp_dir, "ffmpeg.zip")
            if not os.path.exists(os.path.join(bin_dir, 'ffmpeg.exe')):
                download_file(urls['ffmpeg']['windows']['x86_64'], zip_path)
                extract_archive(zip_path, temp_dir)
                extracted_dir = next(d for d in os.listdir(temp_dir) if d.startswith('ffmpeg-master'))
                ffmpeg_bin_dir = os.path.join(temp_dir, extracted_dir, 'bin')
                for exe in ['ffmpeg.exe', 'ffprobe.exe']:
                    shutil.move(os.path.join(ffmpeg_bin_dir, exe), os.path.join(bin_dir, exe))

        # 2. Download and Setup aria2
        # if os_name == 'darwin' and arch == 'arm64':
        #     target_aria2 = os.path.join(bin_dir, 'aria2c')
        #     if not os.path.exists(target_aria2):
        #         tar_path = os.path.join(temp_dir, "aria2.tar.xz")
        #         download_file(urls['aria2']['darwin']['arm64'], tar_path)
        #         extract_archive(tar_path, temp_dir)
        #         extracted_dir = next(d for d in os.listdir(temp_dir) if d.startswith('aria2-1.37.0-macos-arm64'))
        #         shutil.move(os.path.join(temp_dir, extracted_dir, 'aria2c'), target_aria2)
        #         make_executable(target_aria2)
        #     else:
        #         print("aria2c already exists, skipping.")
            
        # elif os_name == 'windows' and arch == 'x86_64':
        #     target_aria2 = os.path.join(bin_dir, 'aria2c.exe')
        #     if not os.path.exists(target_aria2):
        #         zip_path = os.path.join(temp_dir, "aria2.zip")
        #         download_file(urls['aria2']['windows']['x86_64'], zip_path)
        #         extract_archive(zip_path, temp_dir)
        #         extracted_dir = next(d for d in os.listdir(temp_dir) if d.startswith('aria2-1.37.0-win-64bit'))
        #         shutil.move(os.path.join(temp_dir, extracted_dir, 'aria2c.exe'), target_aria2)

        # 3. Download and Setup yt-dlp source
        target_yt_dlp = os.path.join(root_dir, "yt_dlp")
        if not os.path.exists(target_yt_dlp):
            yt_zip = os.path.join(temp_dir, "yt-dlp.zip")
            download_file(urls['yt-dlp'], yt_zip)
            extract_archive(yt_zip, temp_dir)
            yt_dir_name = next(d for d in os.listdir(temp_dir) if d.startswith('yt-dlp'))
            yt_extracted = os.path.join(temp_dir, yt_dir_name, "yt_dlp")
            
            shutil.move(yt_extracted, target_yt_dlp)
        else:
            print("yt_dlp folder already exists, skipping.")

    except Exception as e:
        print(f"Error during setup: {e}")
        raise
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        print("Build setup complete.")

if __name__ == "__main__":
    setup_binaries()
