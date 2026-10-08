"""A matriz dos testes dos nós `pend_*` e da validação: a de verdade (`radar/matriz.yaml`, spec 8.1).

A P-E só lê `estagios` e `modificadores` dela (`definicoes.validos_da_matriz`, por duck typing).
"""

from __future__ import annotations

from radar.pontuacao import carregar_matriz

MATRIZ_SPEC = carregar_matriz()
