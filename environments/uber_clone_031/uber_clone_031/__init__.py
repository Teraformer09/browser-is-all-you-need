"""One fixed Android task with an unweighted, versioned evidence verifier."""
__all__ = ["load_environment"]


def load_environment(**kwargs):
    from uber_clone_031.integrations.prime_env import load_environment as load
    return load(**kwargs)
