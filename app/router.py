from app.services import TranslationService, ProductQAService, CommercialTextService
from app.config import DEFAULT_MODEL

_SERVICES = {
    "translation": TranslationService(),
    "product_qa": ProductQAService(),
    "commercial_text": CommercialTextService(),
}


async def route(service_name: str, payload: dict, model: str = DEFAULT_MODEL) -> dict:
    service = _SERVICES.get(service_name)
    if service is None:
        raise ValueError(f"Servicio desconocido: {service_name}")
    return await service.run(payload, model)
