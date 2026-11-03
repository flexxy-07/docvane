import os

# Ensure litellm does not make blocking network calls to remote price maps during test execution
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
os.environ["LITELLM_MODE"] = "OFFLINE"
os.environ["ANONYMOUS_TELEMETRY"] = "False"
