from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "OmniPlant.AI Core Engine"
    SECRET_KEY: str = "SUP3R_S3CR3T_K3Y_FOR_DEV_ONLY_DO_NOT_USE_IN_PROD"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    

    model_config = ConfigDict(env_file=".env", extra="ignore")

    

settings = Settings()