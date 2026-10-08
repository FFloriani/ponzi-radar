"""A matriz mínima dos testes dos nós `pend_*`: só `estagios` e `modificadores`, copiados da spec (8.1).

Serve até a Tarefa 14 criar o `carregar_matriz`; a P-E só lê esses dois dicionários.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import yaml

MATRIZ_SPEC = SimpleNamespace(
    **yaml.safe_load((Path(__file__).parent / "fixtures" / "matriz_spec.yaml").read_text(encoding="utf-8"))
)
