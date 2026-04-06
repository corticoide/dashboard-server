from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    jwt_secret: str = "dev-secret-change-in-production"
    db_path: str = "./data/serverdash.db"
    cert_file: str = "./certs/cert.pem"
    key_file: str = "./certs/key.pem"
    port: int = 8443
    admin_username: str = "admin"
    admin_password: str = "changeme"
    allowed_origins: list[str] = ["https://localhost:8443"]
    log_retention_days: int = 30
    metrics_retention_days: int = 30
    network_retention_days: int = 30
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
