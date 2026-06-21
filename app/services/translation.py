from .base import BaseService


class TranslationService(BaseService):
    num_predict = 200

    def build_prompt(self, payload: dict) -> str:
        text = payload["text"]
        target = payload["target_language"]
        return (
            f"Eres un traductor profesional. Traduce el siguiente texto al {target}. "
            f"Responde ÚNICAMENTE con la traducción, sin explicaciones ni comentarios adicionales.\n\n"
            f"Texto a traducir:\n{text}"
        )
