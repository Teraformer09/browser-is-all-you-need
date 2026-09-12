"""Compute-only Prime Android inspection; never calls a model or uploads an eval."""
import argparse
import asyncio
import json

from amazon_cart_001.integrations.hosted_session import DEFAULT_IMAGE, HostedSession
from amazon_cart_001.integrations.viewer_tunnel import start_viewer, stop_viewer


async def run(args):
    session = HostedSession(args.output_dir, args.image, inspection=True)
    viewer, error = None, None
    try:
        await asyncio.to_thread(session.start)
        viewer = await start_viewer(session, interactive=True)
        print(json.dumps({"kind": "prime_android_ui_smoke", "model_calls": 0,
            "live_url": session.info["live_viewer"]["url"],
            "private_access_file": str(session.root / ".viewer-private/access.json"),
            "hold_seconds": args.hold_seconds}), flush=True)
        # Do not log the private access token. The operator can hand the private
        # link to the user while the session is alive, then it is revoked.
        await asyncio.sleep(args.hold_seconds)
    except BaseException as exc:
        error = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        try:
            await stop_viewer(viewer)
        finally:
            result = await asyncio.to_thread(session.finish, error)
            print(json.dumps({"kind": "prime_android_ui_smoke", "evaluation": False,
                "artifacts": str(session.root), "sandbox_deleted": session.info.get("sandbox_deleted"),
                "outcome": result}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-compute", action="store_true")
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--hold-seconds", type=int, default=180)
    args = parser.parse_args()
    if not args.allow_compute:
        parser.error("Explicit --allow-compute required: this creates a billed Prime Android VM")
    if not 15 <= args.hold_seconds <= 300:
        parser.error("Hold must be 15-300 seconds; a fresh VM is used for later evaluations")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
