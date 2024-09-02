from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "dJetLawyer ChatBot"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    DATABASE_URL: str
    TEST_DATABASE_URL: str
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str
    OPENAI_API_KEY: str
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str = "noreply@djetlawyer.com"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "lion.wghservers.com"
    SERVER_HOST: str = "http://localhost:8000"
    REDIS_HOST: str = "default:3xREOznDaa5qCz6wQ6pLi8OM9CnJj4cF@redis-11803.c321.us-east-1-2.ec2.redns.redis-cloud.com" #"localhost"
    REDIS_PORT: int = 11803 #6379
    RATE_LIMIT_TIMES: int = 10
    RATE_LIMIT_SECONDS: int = 60
    TESTING: bool
    REFRESH_TOKEN_EXPIRE_DAYS: int = 20
    

    class Config:
        env_file = ".env"

settings = Settings()
