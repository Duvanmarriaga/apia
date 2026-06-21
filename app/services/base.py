from abc import ABC, abstractmethod
import httpx
from app.config import OLLAMA_URL, DEFAULT_MODEL


class BaseService(ABC):
    num_predict: int = 256

    @abstractmethod
    def build_prompt(self, payload: dict) -> str:
        ...

    async def run(self, payload: dict, model: str = DEFAULT_MODEL) -> dict:
        prompt = self.build_prompt(payload)
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": self.num_predict},
                },
            )
            resp.raise_for_status()
            data = resp.json()
        return {
            "response": data["response"],
            "model": model,
            "service": self.__class__.__name__,
        }
