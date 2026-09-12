"""Build the proven software runtime in a fresh Prime Ubuntu VM, from wheel assets."""
import hashlib
import io
import re
import tarfile
import time
from pathlib import Path

BASE_IMAGE = "ubuntu:24.04"
REMOTE_ENV = {
    "ANDROID_SDK_ROOT": "/opt/android-sdk", "JAVA_HOME": "/usr/lib/jvm/java-21-openjdk-amd64",
    "ANDROID_USER_HOME": "/data/Tirtha/democart-runtime/android-user",
    "TMPDIR": "/data/Tirtha/democart-runtime/tmp", "PYTHONDONTWRITEBYTECODE": "1",
    "PATH": "/opt/venv/bin:/opt/android-sdk/platform-tools:/opt/android-sdk/emulator:/opt/android-sdk/cmdline-tools/latest/bin:/usr/lib/jvm/java-21-openjdk-amd64/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
}


def source_bundle(destination):
    package = Path(__file__).resolve().parents[1]
    assets = package / "_bootstrap"
    # Editable checkouts use canonical source; installed wheels carry the same assets.
    if not assets.is_dir():
        assets = package.parent
    files = {}
    for item in package.rglob("*"):
        if item.is_file() and not {"__pycache__", "_bootstrap"}.intersection(item.parts) and item.suffix in {".py", ".json", ".html", ".css", ".js"}:
            files["amazon_cart_001/" + item.relative_to(package).as_posix()] = item
    for relative in ("pyproject.toml", "README.md", "scripts/provision_android.sh",
                     "app/amazon_android_ui/AndroidManifest.xml", "app/amazon_android_ui/build_apk.sh"):
        files[relative] = assets / relative
    for relative in ("app/amazon_android_ui/src", "app/amazon_android_ui/res"):
        for item in (assets / relative).rglob("*"):
            if item.is_file():
                files[item.relative_to(assets).as_posix()] = item
    if not any(name.endswith("MainActivity.java") for name in files):
        raise RuntimeError("BOOTSTRAP_APP_SOURCE_MISSING")
    with tarfile.open(destination, "w:gz") as archive:
        for name, item in sorted(files.items()):
            if item.is_symlink():
                raise RuntimeError("BOOTSTRAP_SOURCE_LINK")
            data = item.read_bytes()
            if re.search(rb"pit_[A-Za-z0-9]{20,}|sk-(?:or-v1-)?[A-Za-z0-9]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", data):
                raise RuntimeError("BOOTSTRAP_CREDENTIAL_PATTERN")
            member = tarfile.TarInfo(name)
            member.size, member.mode = len(data), 0o644
            archive.addfile(member, io.BytesIO(data))
    return {"files": len(files), "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            "bytes": destination.stat().st_size}


def provision(session):
    sdk, sid = session.client, session.sandbox_id
    bundle = session.root / "runtime-source.tar.gz"
    session.info["runtime_source"] = source_bundle(bundle)
    session.persist()
    def command(text):
        result = sdk.execute_command(sid, text, timeout=60)
        if result.exit_code:
            raise RuntimeError("Bootstrap command failed: " + result.stderr[-1500:])
    command("mkdir -p /opt/democart/source /data/Tirtha/democart-runtime/tmp")
    sdk.upload_file(sid, "/opt/democart/context.tar.gz", str(bundle))
    command("tar -xzf /opt/democart/context.tar.gz -C /opt/democart/source")
    job = sdk.start_background_job(sid, "bash /opt/democart/source/scripts/provision_android.sh", env=REMOTE_ENV)
    session.info["provision_job_id"] = job.job_id
    session.persist()
    # OS deps + ~1 GB SDK/AOSP download + pip install + APK build exceed five
    # minutes on contended Prime placements; stay bounded, not optimistic.
    deadline = time.monotonic() + 900
    try:
        while time.monotonic() < deadline:
            state = sdk.get_background_job_status(sid, job, timeout=20)
            if state.completed:
                if state.exit_code:
                    raise RuntimeError("Android provisioning failed; inspect provision.stderr.log")
                session.info["runtime_provisioned"] = True
                session.persist()
                return
            time.sleep(5)
        raise TimeoutError("Android provisioning exceeded 900 seconds")
    finally:
        for channel in ("stdout", "stderr"):
            try:
                sdk.download_file(sid, getattr(job, channel + "_log_file"), str(session.root / ("provision." + channel + ".log")))
            except Exception as exc:
                session.info["provision_log_error_" + channel] = type(exc).__name__
        session.persist()
