from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Document Search Platform"
    app_env: str = "local"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "docsearch"
    postgres_user: str = "docsearch"
    postgres_password: str = "docsearch"
    vector_table: str = "document_chunks"
    embed_dim: int = 768

    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "llama3.2"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_temperature: float = 0.1
    ollama_request_timeout: float = 180.0

    similarity_top_k: int = 6
    enable_hybrid_search: bool = True
    enable_contextual_enrichment: bool = True
    agentic_max_revision_rounds: int = 1

    prompts_dir: Path = Field(default=ROOT_DIR / "prompts")
    prompt_hot_reload: bool = True

    phoenix_collector_endpoint: str = "http://localhost:6006/v1/traces"
    phoenix_project_name: str = "document-search-platform"
    phoenix_enabled: bool = True

    pdf_dir: Path = Field(default=ROOT_DIR / "data" / "pdfs")
    upload_dir: Path = Field(default=ROOT_DIR / "data" / "uploads")
    eval_dataset_path: Path = Field(default=ROOT_DIR / "data" / "eval" / "golden_set.json")

    openai_api_key: str = "ollama-local"

    @property
    def postgres_uri(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def ollama_openai_base(self) -> str:
        return self.ollama_base_url.rstrip("/") + "/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
