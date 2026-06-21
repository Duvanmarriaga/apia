from .base import BaseService


class ProductQAService(BaseService):
    num_predict = 200

    def build_prompt(self, payload: dict) -> str:
        context = payload["context"]
        question = payload["question"]
        # responde solo con el contexto dado, no debe inventar info que no este ahi
        return (
            f"Eres un asistente de atencion al cliente. Responde la pregunta del usuario "
            f"UNICAMENTE basandote en la informacion del producto proporcionada. "
            f"Si la informacion no esta en el contexto,  responde que no tienes esa informacion disponible. "
            f"No inventes datos.\n\n"
            f"Informacion del producto:\n{context}\n\n"
            f"Pregunta del cliente:\n{question}"
        )
