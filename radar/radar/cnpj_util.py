"""CNPJ numérico e alfanumérico: dígitos verificadores e normalização.

Desde julho de 2026 a Receita emite CNPJ com letras (IN RFB 2.229/2024): 12 caracteres `[0-9A-Z]` (a raiz
de 8 e a ordem de 4) e 2 dígitos verificadores numéricos. O valor de cada caractere é `ord(c) - 48`, o
que deixa o CNPJ só de dígitos com a mesma conta de sempre; os pesos são os mesmos.
"""

from __future__ import annotations

import re

_PESOS_DV1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_PESOS_DV2 = (6, *_PESOS_DV1)
_FORMA = re.compile(r"[0-9A-Z]{12}[0-9]{2}")
_PONTUACAO = re.compile(r"[.\-/\s]")


def _digito(caracteres: str, pesos: tuple[int, ...]) -> int:
    resto = sum((ord(c) - 48) * p for c, p in zip(caracteres, pesos, strict=True)) % 11
    return 0 if resto < 2 else 11 - resto


def cnpj_valido(cnpj: str) -> bool:
    """14 caracteres ASCII, sem pontuação e em maiúsculas (12 de `[0-9A-Z]` e 2 dígitos), com os dois
    dígitos verificadores certos.

    Sequências de um caractere só (`00000000000000`, `11111111111111`...) não valem: a de zeros passa na
    conta dos dígitos verificadores, mas não é um CNPJ. Quem recebe texto solto usa `normalizar_cnpj`.
    """
    if not _FORMA.fullmatch(cnpj) or len(set(cnpj)) == 1:
        return False
    dv1 = _digito(cnpj[:12], _PESOS_DV1)
    dv2 = _digito(cnpj[:12] + str(dv1), _PESOS_DV2)
    return cnpj[12:] == f"{dv1}{dv2}"


def normalizar_cnpj(texto: str) -> str | None:
    """O CNPJ de `texto` (com ou sem `.`, `/`, `-` e espaços, em qualquer caixa) como os 14 caracteres em
    maiúsculas, ou `None` se não for um CNPJ válido."""
    limpo = _PONTUACAO.sub("", texto).upper()
    return limpo if cnpj_valido(limpo) else None
