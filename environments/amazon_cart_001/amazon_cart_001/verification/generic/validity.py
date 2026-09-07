from amazon_cart_001.verification.contracts import require
from amazon_cart_001.verification.evidence_readers import state, artifact
from amazon_cart_001.verification.records import verify as record_verify
from amazon_cart_001.harness.actions import PACKAGE

def validity_check(c, policy):
    frames, transitions = c["frames"], c["transitions"]
    if policy == "V1":
        from amazon_cart_001.verification.registry import VERIFIERS
        require(c["registry_valid"] and record_verify(frames[0]["state"], c["task"], c["episode_id"])["status"] != "INVALID",
                "SPEC_OR_APP_CONTRACT_UNUSABLE")
        installed = c["installed_apk"]
        require(installed["package"] == PACKAGE and installed["sha256"] == installed["expected_sha256"],
                "APK_INCOMPATIBLE")
        require(c["capabilities"] == {"adb":True,"ui_dump":True,"screenshot":True,"runtime_probe":True,"preferences":True},
                "CAPABILITY_UNAVAILABLE")
        require(len(VERIFIERS) == 70, "VERIFIER_REGISTRY_INCOMPLETE")
        return True
    if policy == "V2":
        require(len(frames) == len(transitions)+1, "FRAME_COUNT_MISMATCH")
        for i, frame in enumerate(frames):
            require(frame["index"] == i and frame["episode_id"] == c["episode_id"]
                    and frame.get("stable") and not frame.get("errors"), "FRAME_IDENTITY_OR_CAPTURE_INVALID")
            for name in frame["artifacts"]:
                artifact(c, frame, name, "bytes")
            state(c, frame, "runtime_probe")
        require(not c.get("pipeline_error"), "PIPELINE_ABORTED")
        return True
    raise ValueError("Unknown validity policy")
