import httpx
from app.config import OLLAMA_URL

_CODE_PATTERNS = frozenset({"coder", "starcoder", "code"})

_SERVICE_REQUIRED_TAG: dict[str, str] = {
    "translation":     "text",
    "product_qa":      "text",
    "commercial_text": "text",
}

_registry: dict[str, str] = {}


def _classify(name: str) -> str:
    lower = name.lower()
    if any(p in lower for p in _CODE_PATTERNS):
        return "code"
    return "text"


_ollama_available: bool = False


async def refresh() -> None:
    global _registry, _ollama_available
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            resp.raise_for_status()
            models = resp.json().get("models", [])
        _registry = {m["name"]: _classify(m["name"]) for m in models}
        _ollama_available = True
    except Exception:
        _ollama_available = False


def all_models() -> dict[str, str]:
    return dict(_registry)


def allowed_for(service: str) -> list[str]:
    required = _SERVICE_REQUIRED_TAG.get(service, "text")
    return [name for name, tag in _registry.items() if tag == required]


def is_available() -> bool:
    return _ollama_available


def validate(model: str, service: str) -> str | None:
    if not _ollama_available:
        return None

    if model not in _registry:
        available = ", ".join(sorted(_registry)) or "ninguno"
        return f"Modelo '{model}' no encontrado en Ollama. Disponibles: {available}"

    required = _SERVICE_REQUIRED_TAG.get(service, "text")
    if _registry[model] != required:
        allowed = ", ".join(sorted(allowed_for(service))) or "ninguno"
        return (
            f"Modelo '{model}' es de tipo '{_registry[model]}' "
            f"y no es compatible con el servicio '{service}'. "
            f"Modelos permitidos: {allowed}"
        )

    return None
