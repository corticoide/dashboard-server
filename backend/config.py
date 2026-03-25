from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    jwt_secret: str = "dev-secret-change-in-production"
    db_path: str = "./data/serverdash.db"
    cert_file: str = "./certs/cert.pem"
    key_file: str = "./certs/key.pem"
    port: int = 8443
    admin_username: str = "admin"
    admin_password: str = "changeme"

    class Config:
        env_file = ".env"

settings = Settings()
