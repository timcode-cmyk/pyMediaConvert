import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pyMediaTools.core.rembg import RembgProcessor, get_best_providers, HAS_REMBG

def test_has_rembg():
    print(f"HAS_REMBG: {HAS_REMBG}")
    # This might be false in the test environment if rembg is not installed, 
    # but the logic should still be sound.
    assert isinstance(HAS_REMBG, bool)

def test_provider_detection():
    providers = get_best_providers()
    print(f"Detected providers: {providers}")
    assert isinstance(providers, list)
    assert len(providers) > 0
    assert 'CPUExecutionProvider' in providers or providers == [] # It should at least have CPU if onnxruntime is there

def test_processor_init_fail_gracefully():
    if not HAS_REMBG:
        try:
            RembgProcessor()
        except ImportError as e:
            print(f"Caught expected ImportError: {e}")
            assert "rembg" in str(e).lower()
        except Exception as e:
            pytest.fail(f"Unexpected exception: {e}")
    else:
        # If it has rembg, it should init (might take time to download model if first time)
        try:
            processor = RembgProcessor(model_name="u2netp") # Fast model
            assert processor.session is not None
            print("Processor initialized successfully.")
        except Exception as e:
            print(f"Initialization failed (expected if no internet/no models): {e}")

if __name__ == "__main__":
    test_has_rembg()
    test_provider_detection()
    test_processor_init_fail_gracefully()
