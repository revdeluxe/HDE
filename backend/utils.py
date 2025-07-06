from pysx127x import SX127x
import peft

def is_lora_available():
    try:
        return hasattr(SX127x, 'BOARD') and SX127x.BOARD is not None
    except ImportError:
        try:
            return True
        except ImportError:
            return False
