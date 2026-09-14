"""Offline safety contract; never creates a tunnel, sandbox or Android process."""
import os
import tempfile
import unittest
from pathlib import Path

from amazon_improved_task_001.harness.public_readiness import validate_hold, validate_proxy

CONFIG = '''serverAddr = "relay.example.invalid"
serverPort = 7000
user = "test"
auth.method = "token"
auth.token = "ephemeral-fixture-not-a-real-secret"
metadatas.binding_secret = "fixture"
log.to = "console"
log.level = "error"
transport.tcpMux = true
[[proxies]]
name = "test"
type = "http"
localIP = "127.0.0.1"
localPort = 8765
subdomain = "test"
'''


class PublicReadinessTests(unittest.TestCase):
    def binding(self, text=CONFIG):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "frpc.toml"
        path.write_text(text)
        path.chmod(0o600)
        return path

    def test_only_bounded_holds(self):
        for value in (60, 600):
            validate_hold(value)
        for value in (0, 601, True, "600", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_hold(value)

    def test_private_single_loopback_proxy(self):
        validate_proxy(self.binding(), 8765)

    def test_adb_or_other_ports_are_not_exposed(self):
        for text in (CONFIG.replace("8765", "5037"), CONFIG.replace('type = "http"', 'type = "tcp"'),
                     CONFIG.replace('localIP = "127.0.0.1"', 'localIP = "0.0.0.0"')):
            with self.subTest(text=text), self.assertRaises(ValueError):
                validate_proxy(self.binding(text), 8765)

    def test_additional_proxy_or_config_is_rejected(self):
        for text in (CONFIG + CONFIG[CONFIG.index("[[proxies]]"):], 'includes = ["*"]\n' + CONFIG):
            with self.subTest(text=text), self.assertRaises(ValueError):
                validate_proxy(self.binding(text), 8765)

    def test_public_permissions_and_symlinks_are_rejected(self):
        path = self.binding()
        path.chmod(0o644)
        with self.assertRaises(ValueError):
            validate_proxy(path, 8765)
        path.chmod(0o600)
        link = path.parent / "link"
        link.symlink_to(path)
        with self.assertRaises(ValueError):
            validate_proxy(link, 8765)

    def test_no_api_key_is_needed_inside_guest(self):
        source = (Path(__file__).parents[1] / "amazon_improved_task_001/harness/public_readiness.py").read_text()
        self.assertNotIn("getpass", source)
        self.assertNotIn("TunnelClient", source)
        self.assertIn("public_readonly=True", source)
        self.assertNotIn("worker.env.step", source)
