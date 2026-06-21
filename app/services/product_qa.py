from .base import BaseService


class ProductQAService(BaseService):
    num_predict = 200

    def build_prompt(self, payload: dict) -> str:
        context = payload["context"]
        question = payload["question"]
        return (
            f"Eres un asistente de atención al cliente. Responde la pregunta del usuario "
            f"ÚNICAMENTE basándote en la información del producto proporcionada. "
            f"Si la información no está en el contexto, responde que no tienes esa información disponible. "
            f"No inventes datos.\n\n"
            f"Información del producto:\n{context}\n\n"
            f"Pregunta del cliente:\n{question}"
        )
