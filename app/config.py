from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str = 'sqlite:///./ops_guard.db'
    api_token: str = 'local-demo-token'
    llm_mode: str = 'mock'
    llm_model: str = 'gpt-4.1-mini'
    llm_api_key: str = ''
    llm_base_url: str | None = None

settings = Settings()
if settings.llm_mode not in ('mock', 'openai'):
    raise ValueError('LLM_MODE must be mock or openai')
