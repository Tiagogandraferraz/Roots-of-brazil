```python
"""
Logging estruturado em JSON — Roots of Brazil (Seção 8 do Manual de Execução).

Níveis:
  INFO    — operação normal (requisição atendida, migration aplicada, carga concluída)
  WARNING — situação anômala mas não bloqueante (objeto órfão, valor sentinela consultado)
  ERROR   — falha que impede a operação solicitada (ID não encontrado, violação de constraint)
  AUDIT   — evento relevante para a Regra Mestra (Seção 3) — nunca descartado por rotação padrão
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

AUDIT_LEVEL_NUM = 25
logging.addLevelName(AUDIT_LEVEL_NUM, "AUDIT")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False)


class RootsLogger(logging.Logger):
    def audit(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log de nível AUDIT — persistido separadamente, nunca descartado por rotação padrão."""
        if self.isEnabledFor(AUDIT_LEVEL_NUM):
            self._log(AUDIT_LEVEL_NUM, message, args, **kwargs)


logging.setLoggerClass(RootsLogger)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    audit_handler = logging.FileHandler("logs/audit.log", encoding="utf-8")
    audit_handler.setFormatter(JsonFormatter())
    audit_handler.setLevel(AUDIT_LEVEL_NUM)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler, audit_handler]


def get_logger(name: str) -> RootsLogger:
    return logging.getLogger(name)  # type: ignore[return-value]
```
