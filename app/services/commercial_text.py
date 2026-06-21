from .base import BaseService

_TYPE_INSTRUCTIONS = {
    "email": "un email de marketing profesional y persuasivo",
    "anuncio": "un anuncio publicitario breve y llamativo",
    "post": "un post para redes sociales atractivo y con llamada a la acción",
}


class CommercialTextService(BaseService):
    num_predict = 300

    def build_prompt(self, payload: dict) -> str:
        text_type = payload["text_type"]
        description = payload["product_description"]
        instruction = _TYPE_INSTRUCTIONS.get(text_type, f"un texto de tipo {text_type}")
        # 15 years de experiencia le da mejores resultados al modelo, probado a mano
        return (
            f"Eres un experto en marketing con 15 años de experiencia.  "
            f"Tu tarea es escribir {instruction} para el siguiente producto o servicio. "
            f"El texto debe ser creativo, persuasivo  y adaptado al formato solicitado.\n\n"
            f"Producto o servicio:\n{description}"
        )
