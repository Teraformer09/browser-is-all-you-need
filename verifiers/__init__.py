"""Offline DemoCart task; loading does not launch an emulator or evaluation."""
VERSION = "0.6.2"
__version__ = VERSION

def load_environment(**kwargs):
    from amazon_cart_001.integrations.prime_env import load_environment as load
    return load(**kwargs)

