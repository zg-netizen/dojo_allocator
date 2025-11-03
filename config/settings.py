"""Application settings and configuration management."""
from pydantic_settings import BaseSettings
from functools import lru_cache
import yaml
from pathlib import Path

class Settings(BaseSettings):
    """Application settings from environment variables."""
    
    # Database
    DATABASE_URL: str = "postgresql://dojo:password@postgres:5432/dojo_allocator"
    
    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # Broker
    BROKER_TYPE: str = "paper"
    
    # External APIs
    QUIVER_API_KEY: str = ""
    FRED_API_KEY: str = ""
    IB_ACCOUNT_ID: str = ""
    ALPACA_API_KEY: str = ""
    ALPACA_API_SECRET: str = ""
    
    # Environment
    ENV: str = "development"
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

@lru_cache()
def get_philosophy_config() -> dict:
    """Load philosophy configuration from YAML."""
    config_path = Path(__file__).parent / "philosophy.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

@lru_cache()
def get_risk_limits() -> dict:
    """Load risk limits from YAML."""
    config_path = Path(__file__).parent / "risk_limits.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

@lru_cache()
def get_data_sources_config() -> dict:
    """Load data sources configuration from YAML."""
    config_path = Path(__file__).parent / "data_sources.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)
