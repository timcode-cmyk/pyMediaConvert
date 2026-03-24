import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from pyMediaTools.core.vidoecut import SceneCutter, get_available_ass_files, get_available_fonts

def test_ass_scanning():
    print("Testing ASS scanning...")
    ass_files = get_available_ass_files()
    print(f"Found ASS files: {ass_files}")
    assert isinstance(ass_files, dict)
    # At least AI-Hindi.ass should be there if assets exist
    if Path("assets").exists():
        if "AI-Hindi.ass" in ass_files:
            print("✓ AI-Hindi.ass found")
        else:
            print("! AI-Hindi.ass not found (might be missing in current env)")

def test_hw_detection():
    print("\nTesting Hardware Encoder Detection...")
    cutter = SceneCutter()
    print(f"Available encoders: {cutter.available_encoders}")
    codec, args = cutter._get_video_codec_params()
    print(f"Selected codec: {codec}")
    print(f"Additional args: {args}")
    
    if sys.platform == "darwin":
        assert "videotoolbox" in codec or "libx264" == codec
    print(f"✓ Hardware detection works (Selected: {codec})")

def test_watermark_filter_ass():
    print("\nTesting Watermark Filter (ASS)...")
    cutter = SceneCutter()
    # Mock available ass files
    cutter.available_ass_files["test.ass"] = "assets/test.ass"
    
    params = {"text": "test.ass"}
    filter_str = cutter._build_watermark_filter(params)
    print(f"Filter for test.ass: {filter_str}")
    assert filter_str is not None, "Filter should not be None"
    assert "ass=" in filter_str
    print("✓ ASS filter generation works")

def test_watermark_filter_drawtext():
    print("\nTesting Watermark Filter (Drawtext)...")
    cutter = SceneCutter()
    # Mock available fonts
    if not cutter.available_fonts:
        cutter.available_fonts = {"Roboto-Bold": "assets/Roboto-Bold.ttf"}
    
    params = {
        "text": "Hello World",
        "font_name": "Roboto-Bold",
        "font_color": "white",
        "font_size": "24",
        "x": "10",
        "y": "10"
    }
    filter_str = cutter._build_watermark_filter(params)
    print(f"Filter for Hello World: {filter_str}")
    assert "drawtext=" in filter_str
    print("✓ Drawtext filter generation works")

if __name__ == "__main__":
    try:
        test_ass_scanning()
        test_hw_detection()
        test_watermark_filter_ass()
        test_watermark_filter_drawtext()
        print("\nAll core logic tests passed!")
    except Exception as e:
        print(f"\nTest failed: {e}")
        sys.exit(1)
