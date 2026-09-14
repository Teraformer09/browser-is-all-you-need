"""Offline DemoCart task; loading does not launch an emulator or evaluation."""
VERSION = "0.1.2"
__version__ = VERSION
__all__ = ["VERSION", "load_environment"]

def load_environment(**kwargs):
    from amazon_improved_task_001.integrations.prime_env import load_environment as load
    return load(**kwargs)
