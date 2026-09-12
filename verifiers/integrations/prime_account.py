"""Read existing Prime auth without creating or changing ~/.prime files."""
from unittest.mock import patch

def api_client():
    from prime_cli.core import APIClient,Config
    # CLI Config normally mkdirs in ~/.prime even for a GET. Suppress that write;
    # existing config and process secrets are read, never copied into the repo.
    with patch.object(Config,"_ensure_config_dir",lambda self: None):
        api=APIClient()
    identity=api.get("/user/whoami")["data"]
    if identity.get("slug")!="terrano09" or api.config.team_id:
        api.client.close()
        raise RuntimeError("Expected terrano09 personal account")
    return api

if __name__=="__main__":
    from amazon_cart_001.agents.openrouter import model_info
    from prime_evals import EvalsClient
    api=api_client()
    model=model_info("dots-studio/dots-3-note-preview:free")
    historical=EvalsClient(api).get_evaluation("kl9bsyib7fjf81699n0d4ik6")
    print({"account":"terrano09","model":model["id"],"pricing":model["pricing"],
        "input_modalities":model["architecture"]["input_modalities"],
        "existing_environment_ids":historical["environment_ids"]})

