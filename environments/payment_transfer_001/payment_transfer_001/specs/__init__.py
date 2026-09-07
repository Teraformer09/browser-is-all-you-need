from pathlib import Path
from payment_transfer_001.harness.evidence import digest

def task_path():
    return Path(__file__).with_name("task.json")

def fingerprints():
    base = Path(__file__).parents[1]
    return {str(p.relative_to(base)): digest(p.read_bytes()) for p in sorted(base.rglob("*")) if p.suffix in {".py", ".json"} and "__pycache__" not in p.parts}
