"""Environment configuration. Secrets should never be committed."""

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    mode: str
    db_path: Path
    max_searches: int
    model: str

    @classmethod
    def from_env(cls, require_live_keys: bool = True) -> "Settings":
        load_dotenv()
        mode = os.getenv("RESEARCHFLOW_MODE", "mock").lower().strip()
        if mode not in {"mock", "live"}:
            raise ValueError("RESEARCHFLOW_MODE must be 'mock' or 'live'")
        try:
            max_searches = int(os.getenv("RESEARCHFLOW_MAX_SEARCHES", "3"))
        except ValueError as exc:
            raise ValueError("RESEARCHFLOW_MAX_SEARCHES must be an integer") from exc
        if not 1 <= max_searches <= 5:
            raise ValueError("RESEARCHFLOW_MAX_SEARCHES must be between 1 and 5")
        if mode == "live" and require_live_keys:
            missing = [k for k in ("OPENAI_API_KEY", "TAVILY_API_KEY") if not os.getenv(k)]
            if missing:
                raise ValueError(f"Missing environment variables: {', '.join(missing)}")
        return cls(
            mode=mode,
            db_path=Path(os.getenv("RESEARCHFLOW_DB", ".data/researchflow.sqlite")),
            max_searches=max_searches,
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        )
