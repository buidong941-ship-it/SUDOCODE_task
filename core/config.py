"""Cấu hình duy nhất của hệ thống — đọc từ biến môi trường (và file .env nếu có).

Mọi thứ phụ thuộc máy chạy (khóa API, DB, model) nằm ở đây để code không biết mình chạy trên laptop hay server.
"""
import os
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_dotenv(path=os.path.join(ROOT, ".env")):
    """Đọc .env đơn giản (KEY=VALUE), không ghi đè biến đã có trong môi trường."""
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


def _env(name, default=None):
    v = os.environ.get(name)
    return v if v not in (None, "") else default


@dataclass
class Settings:
    # --- Router / orchestrator: jev | llm | rules
    router_backend: str = field(default_factory=lambda: _env("ROUTER_BACKEND", "jev"))
    typesafe_api_key: str = field(default_factory=lambda: _env("TYPESAFE_API_KEY"))
    jev_model: str = field(default_factory=lambda: _env("JEV_MODEL", "jev-latest"))
    jev_base_url: str = field(default_factory=lambda: _env("TYPESAFE_BASE_URL"))      # để trống = https://api.typesafe.ai
    jev_timeout_s: float = field(default_factory=lambda: float(_env("JEV_TIMEOUT_S", "8")))
    router_min_confidence: float = field(default_factory=lambda: float(_env("ROUTER_MIN_CONFIDENCE", "0.45")))

    # --- Generator (lời thoại): deepseek | offline
    generator_backend: str = field(default_factory=lambda: _env("GENERATOR_BACKEND", "deepseek"))
    deepseek_api_key: str = field(default_factory=lambda: _env("DEEPSEEK_API_KEY"))
    deepseek_base_url: str = field(default_factory=lambda: _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    deepseek_model: str = field(default_factory=lambda: _env("DEEPSEEK_MODEL", "deepseek-v4-flash"))
    llm_temperature: float = field(default_factory=lambda: float(_env("LLM_TEMPERATURE", "0.3")))
    llm_max_tokens: int = field(default_factory=lambda: int(_env("LLM_MAX_TOKENS", "350")))
    llm_timeout_s: float = field(default_factory=lambda: float(_env("LLM_TIMEOUT_S", "30")))

    # --- Lưu trữ: sqlite (mặc định, chạy ở đâu cũng được) hoặc postgresql+psycopg://... trên server
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL", "sqlite:///" + os.path.join(ROOT, "data", "memory.db")))

    # --- Dữ liệu BTC
    btc_dir: str = field(default_factory=lambda: _env("BTC_DIR", ROOT))

    def describe(self):
        """Ghi vào runs/<id>/config.json để số liệu tái lập được (không ghi khóa API)."""
        return {"router_backend": self.router_backend, "jev_model": self.jev_model,
                "router_min_confidence": self.router_min_confidence,
                "generator_backend": self.generator_backend, "deepseek_model": self.deepseek_model,
                "deepseek_base_url": self.deepseek_base_url, "llm_temperature": self.llm_temperature,
                "llm_max_tokens": self.llm_max_tokens,
                "database": self.database_url.split("://", 1)[0]}


settings = Settings()
