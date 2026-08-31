import os

os.environ["PHOENIX_ENABLED"] = "false"
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
