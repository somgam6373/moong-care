from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DB: str = "moongcare"

    STT_MODEL_DIR: str = "iic/SenseVoiceSmall"
    SER_MODEL_DIR: str = "iic/emotion2vec_plus_large"
    TTS_MODEL_DIR: str = "pretrained_models/CosyVoice2-0.5B"

    class Config:
        env_file = ".env"


settings = Settings()
