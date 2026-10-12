"""Environment configuration with explicit opt-in dotenv loading."""

import math
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class GeneratorConfig:
    api_key: str | None = field(default=None, repr=False)
    base_url: str | None = None
    model_name: str = "gpt-4"
    max_tokens: int = 8000
    request_timeout: float = 120
    planning_deadline: float = 360


class Config:
    def __init__(self):
        explicit_env = os.getenv("PPT_GENERATE_ENV_FILE")
        if explicit_env:
            env_path = Path(explicit_env).expanduser().resolve()
            if not env_path.is_file():
                raise ValueError("PPT_GENERATE_ENV_FILE does not exist")
            load_dotenv(env_path, override=False)
        self.generator = GeneratorConfig(
            api_key=os.getenv("LLM_API_KEY") or os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL")
            or os.getenv("API_BASE_URL")
            or os.getenv("OPENAI_BASE_URL"),
            model_name=os.getenv("LLM_MODEL_NAME")
            or os.getenv("MODEL_NAME")
            or os.getenv("GENERATOR_MODEL")
            or "gpt-4",
            max_tokens=int(os.getenv("GENERATOR_MAX_TOKENS", "8000")),
            request_timeout=float(os.getenv("GENERATOR_REQUEST_TIMEOUT", "120")),
            planning_deadline=float(os.getenv("GENERATOR_PLANNING_DEADLINE", "360")),
        )
        if self.generator.max_tokens < 1:
            raise ValueError("GENERATOR_MAX_TOKENS must be positive")
        if any(
            not math.isfinite(value) or value <= 0
            for value in [self.generator.request_timeout, self.generator.planning_deadline]
        ):
            raise ValueError("Generation timeouts must be positive")


config = Config()
