import asyncio
import heapq
from collections import defaultdict


class ModelAwareScheduler:
    """
    Cola de prioridad que minimiza los swaps de modelo en Ollama.

    Algoritmo:
      1. Si el modelo actualmente en VRAM tiene jobs pendientes → procesa el de
         mayor prioridad sin hacer swap.
      2. Si la cola del modelo actual está vacía → busca el modelo cuyo job
         pendiente tenga la mejor prioridad global y hace el swap.
      3. Si todas las colas están vacías → espera hasta que llegue un job nuevo.

    Acepta cualquier modelo dinámicamente; no requiere lista fija en el constructor.
    """

    def __init__(self) -> None:
        self._queues: dict[str, list] = defaultdict(list)
        self._current_model: str | None = None
        self._total: int = 0
        self._swaps: int = 0
        self._event: asyncio.Event = asyncio.Event()

    def put(self, priority: int, seq: int, job_id: str, service: str, model: str, payload: dict) -> None:
        heapq.heappush(self._queues[model], (priority, seq, job_id, service, payload))
        self._total += 1
        self._event.set()

    async def get(self) -> tuple[str, str, str, dict]:
        """Devuelve (model, job_id, service, payload). Bloquea si no hay jobs."""
        while True:
            result = self._try_get()
            if result is not None:
                return result
            self._event.clear()
            await self._event.wait()

    def _try_get(self) -> tuple[str, str, str, dict] | None:
        if self._current_model and self._queues[self._current_model]:
            return self._pop(self._current_model)

        best_model: str | None = None
        best_key: tuple | None = None
        for model, q in self._queues.items():
            if q and (best_key is None or q[0][:2] < best_key):
                best_key = q[0][:2]
                best_model = model

        if best_model is None:
            return None

        if best_model != self._current_model:
            self._swaps += 1
            self._current_model = best_model

        return self._pop(best_model)

    def _pop(self, model: str) -> tuple[str, str, str, dict]:
        _, _, job_id, service, payload = heapq.heappop(self._queues[model])
        self._total -= 1
        return model, job_id, service, payload

    def qsize(self) -> int:
        return self._total

    @property
    def current_model(self) -> str | None:
        return self._current_model

    @property
    def swaps(self) -> int:
        return self._swaps

    def pending_by_model(self) -> dict[str, int]:
        return {m: len(q) for m, q in self._queues.items() if q}
