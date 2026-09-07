VERSION = "0.3.0"
"""Single-task simulated payment environment; loading never launches Android."""
__version__ = VERSION

def load_environment(**kwargs):
    from payment_transfer_001.integrations.prime_env import load_environment as load
    return load(**kwargs)
