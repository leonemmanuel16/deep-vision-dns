"""Vision Assistant configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    db_host: str = "postgres"
    db_port: int = 5432
    db_name: str = "deepvision"
    db_user: str = "deepvision"
    db_password: str = "changeme_secure_password"

    # Ollama
    ollama_host: str = "ollama"
    ollama_port: int = 11434
    assistant_model: str = "phi3:mini"

    # Redis
    redis_url: str = "redis://redis:6379"

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def ollama_url(self) -> str:
        return f"http://{self.ollama_host}:{self.ollama_port}"

    class Config:
        env_file = ".env"


settings = Settings()
