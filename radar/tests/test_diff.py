"""Diff entre execuções (Tarefa 15, spec 8.5): as duas são repontuadas com a matriz atual."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from radar.arquivos import gravar_json_atomico
from radar.diff import Diff, alertas_da_execucao, comparar, renderizar_diff, texto_classe, texto_intervalo
from radar.execucao import carregar_execucao
from radar.pontuacao import Eixo1, site_nao_respondeu
from tests.execucao_em_disco import AGORA, MATRIZ, PETROBRAS, gravar, pend_e_com, resposta, saidas_base, sinal_e

ONTEM = AGORA - timedelta(days=1)


def duas(tmp_path: Path, a: dict | None = None, b: dict | None = None):
    """A execução de ontem (`a`) e a de hoje (`b`) do mesmo alvo, as duas em modo atual."""
    pasta_a = gravar(tmp_path, agora=ONTEM, **(a or {}))
    pasta_b = gravar(tmp_path, agora=AGORA, **(b or {}))
    return carregar_execucao(pasta_a), carregar_execucao(pasta_b)


def dns(**campos) -> dict:
    return {"dns": {**saidas_base()["dns"], **campos}}


# ---------------------------------------------------------------------------- estágio, itens, sócios


def test_diff_estagio_e_socios(tmp_path):
    a_socios = saidas_base()["cnpj"]["socios"]
    novo = {"nome": "JOAO PEREIRA", "qualificacao": "Sócio", "entrada": "2026-09-30"}
    a, b = duas(
        tmp_path,
        a={"saidas": {"pend_e": pend_e_com(sinal_e("escalada_taxa"))}},
        b={
            "saidas": {
                "pend_e": pend_e_com(sinal_e("escalada_taxa"), sinal_e("atraso_pagamento", "2026-10-02", 1)),
                "cnpj": {**saidas_base()["cnpj"], "socios": [*a_socios, novo]},
            }
        },
    )
    d = comparar(a, b, MATRIZ)
    assert (d.estagio_a, d.estagio_b) == ("E3", "E4")
    assert "⚠ estágio subiu: E3 → E4" in renderizar_diff(d)
    assert d.socios_entraram == ["JOAO PEREIRA"]
    assert d.socios_sairam == []
    assert "JOAO PEREIRA" in renderizar_diff(d)
    assert d.sinais_novos == ["atraso_pagamento (E4), 2026-10-02"]


def test_diff_socio_que_saiu(tmp_path):
    a, b = duas(tmp_path, b={"saidas": {"cnpj": {**saidas_base()["cnpj"], "socios": []}}})
    d = comparar(a, b, MATRIZ)
    assert d.socios_sairam == ["MARIA DA SILVA"] and d.socios_entraram == []
    assert "MARIA DA SILVA" in renderizar_diff(d)


def test_diff_socios_comparados_sem_caixa_nem_espaco_repetido(tmp_path):
    outro = {"nome": "  maria  da silva ", "qualificacao": "Sócio-Administrador", "entrada": "2014-01-10"}
    a, b = duas(tmp_path, b={"saidas": {"cnpj": {**saidas_base()["cnpj"], "socios": [outro]}}})
    d = comparar(a, b, MATRIZ)
    assert d.socios_entraram == d.socios_sairam == []


def test_diff_sem_cnpj_em_um_dos_lados_nao_inventa_socios(tmp_path):
    a, b = duas(tmp_path, b={"status": {"cnpj": ("erro", "APIs de CNPJ indisponíveis")}})
    d = comparar(a, b, MATRIZ)
    assert d.socios_entraram == d.socios_sairam == []


def test_diff_estagio_que_desceu_ou_nao_mudou_nao_tem_alerta(tmp_path):
    a, b = duas(
        tmp_path,
        a={"saidas": {"pend_e": pend_e_com(sinal_e("atraso_pagamento"))}},
        b={"saidas": {"pend_e": pend_e_com(sinal_e("escalada_taxa"))}},
    )
    texto = renderizar_diff(comparar(a, b, MATRIZ))
    assert "⚠" not in texto and "Estágio: E4 → E3 (desceu)" in texto
    mesmo = renderizar_diff(comparar(b, b, MATRIZ))
    assert "⚠" not in mesmo and "Estágio: E3 (sem mudança)" in mesmo


def test_diff_estagio_de_nenhum_para_e1_sobe(tmp_path):
    a, b = duas(tmp_path, b={"saidas": {"pend_e": pend_e_com(sinal_e("depoimentos"))}})
    d = comparar(a, b, MATRIZ)
    assert (d.estagio_a, d.estagio_b) == (None, "E1")
    assert "⚠ estágio subiu: sem estágio → E1" in renderizar_diff(d)


def test_diff_itens_mudados_de_estado_e_de_pontos(tmp_path):
    a, b = duas(
        tmp_path,
        b={
            "saidas": {
                "pend_a1": resposta(valor={"pct_mes": 12.0, "taxa_diaria": False, "garantido": True}),
                "pend_b": resposta(
                    valor={"indicacao": "nenhuma", "token_proprio": False, "carencia_com_multa": False,
                           "taxa_para_sacar": True}
                ),
            }
        },
    )  # fmt: skip
    d = comparar(a, b, MATRIZ)
    assert d.itens_mudados == [
        ("A1", "confirmado", 3, "confirmado", 4),
        ("B4", "nao_se_aplica", 0, "confirmado", 3),
    ]
    texto = renderizar_diff(d)
    assert "A1: confirmado (3) → confirmado (4)" in texto
    assert "B4: não se aplica (0) → confirmado (3)" in texto
    assert (d.eixo1_a.minimo, d.eixo1_b.minimo) == (8, 12)
    assert d.eixo1_b.classe == "característico"  # R2


def test_diff_sem_mudancas(tmp_path):
    a, b = duas(tmp_path)
    d = comparar(a, b, MATRIZ)
    assert d.itens_mudados == [] and d.sinais_novos == [] and d.infra == []
    assert d.socios_entraram == d.socios_sairam == [] and d.wayback_novas == 0
    assert d.matriz_diferente is False and d.eixo1_a_matriz_original is None
    texto = renderizar_diff(d)
    assert "Itens que mudaram: nenhum" in texto and "Intervalo: 8–10 de 34 (sem mudança)" in texto


# ---------------------------------------------------------------------------- sinais e alertas


def test_diff_alerta_novo_da_cvm_e_sinal_so_do_b(tmp_path):
    alerta = {
        "tipo": "cnpj", "valor": PETROBRAS, "numero": 1234, "data": "2026-09-01",
        "url": "https://conteudo.cvm.gov.br/d1234", "trecho": "atuação irregular",
    }  # fmt: skip
    a, b = duas(
        tmp_path,
        b={"saidas": {"cvm_alertas": {"correspondencias": [alerta], "cobertura": {"com_texto_integral": 3, "so_resumo": 0}}}},
    )
    d = comparar(a, b, MATRIZ)
    assert d.sinais_novos == ["alerta CVM: Deliberação 1234 (2026-09-01) cita o CNPJ"]
    assert ("C4", "nao_se_aplica", 0, "confirmado", 3) in d.itens_mudados
    assert "alerta CVM: Deliberação 1234" in renderizar_diff(d)


def test_diff_alerta_que_ja_existia_nao_e_novo(tmp_path):
    alerta = {"tipo": "dominio", "valor": "exemplo.com.br", "numero": 7, "data": "2026-01-01", "url": "u", "trecho": "t"}
    cvm = {"cvm_alertas": {"correspondencias": [alerta], "cobertura": {"com_texto_integral": 3, "so_resumo": 0}}}
    a, b = duas(tmp_path, a={"saidas": cvm}, b={"saidas": cvm})
    assert comparar(a, b, MATRIZ).sinais_novos == []


def _delib(numero: int, tipo: str, valor: str | None, data: str = "2026-09-01") -> dict:
    achado = {"tipo": tipo, "numero": numero, "data": data, "url": f"https://conteudo.cvm.gov.br/d{numero}", "trecho": "x"}
    return achado if valor is None else {**achado, "valor": valor}


def _cvm(*correspondencias: dict) -> dict:
    return {"cvm_alertas": {"correspondencias": list(correspondencias), "cobertura": {"com_texto_integral": 3, "so_resumo": 0}}}


def test_diff_deliberacao_que_cita_o_alvo_e_o_destino_diz_qual_dominio(tmp_path):
    # T1/R-A-T1-cvm: o `cvm_alertas` casa o domínio do alvo e o do destino, e a mesma deliberação pode citar os dois
    cvm = _cvm(_delib(15, "dominio", "phinv.link"), _delib(15, "dominio", "phinvestimentos.com"))
    a, b = duas(tmp_path, b={"saidas": cvm})
    d = comparar(a, b, MATRIZ)
    assert d.sinais_novos == [
        "alerta CVM: Deliberação 15 (2026-09-01) cita o domínio phinv.link",
        "alerta CVM: Deliberação 15 (2026-09-01) cita o domínio phinvestimentos.com",
    ]
    alertas = alertas_da_execucao(b)
    assert len({al.chave for al in alertas}) == 2 and [al.fonte for al in alertas] == ["https://conteudo.cvm.gov.br/d15"] * 2
    texto = renderizar_diff(d)
    assert "cita o domínio phinv.link" in texto and "cita o domínio phinvestimentos.com" in texto


def test_diff_alerta_da_cvm_so_e_novo_pelo_dominio_citado(tmp_path):
    # a execução de antes só citava o redirecionador; a de agora cita também o destino: só esse é novo
    antes = _cvm(_delib(15, "dominio", "phinv.link"))
    agora = _cvm(_delib(15, "dominio", "phinv.link"), _delib(15, "dominio", "phinvestimentos.com"))
    a, b = duas(tmp_path, a={"saidas": antes}, b={"saidas": agora})
    assert comparar(a, b, MATRIZ).sinais_novos == ["alerta CVM: Deliberação 15 (2026-09-01) cita o domínio phinvestimentos.com"]
    # e o mesmo domínio nas duas, escrito de outro jeito (caixa e espaço), não é novo
    a, b = duas(tmp_path / "igual", a={"saidas": antes}, b={"saidas": _cvm(_delib(15, "dominio", " PHINV.link "))})
    assert comparar(a, b, MATRIZ).sinais_novos == []


@pytest.mark.parametrize("valor", [None, "", "   ", 5, ["phinv.link"]])
def test_diff_alerta_de_dominio_sem_valor_legivel_segue_como_antes(tmp_path, valor):
    # execução salva sem o domínio na correspondência (ou com lixo): o rótulo e a chave de sempre
    achado = {**_delib(15, "dominio", None), "valor": valor}
    a, b = duas(tmp_path, b={"saidas": _cvm(achado)})
    assert comparar(a, b, MATRIZ).sinais_novos == ["alerta CVM: Deliberação 15 (2026-09-01) cita o domínio"]
    assert [al.chave for al in alertas_da_execucao(b)] == ["cvm:15:dominio"]


def test_diff_alerta_de_cnpj_e_de_nome_nao_levam_o_valor_no_rotulo(tmp_path):
    cvm = _cvm(_delib(1, "cnpj", PETROBRAS), _delib(2, "nome", "exemplo investimentos"))
    a, b = duas(tmp_path, b={"saidas": cvm})
    assert comparar(a, b, MATRIZ).sinais_novos == [
        "alerta CVM: Deliberação 1 (2026-09-01) cita o CNPJ",
        "alerta CVM: Deliberação 2 (2026-09-01) cita o nome",
    ]


def test_diff_alerta_de_dominio_hostil_nao_quebra_a_linha_do_diff(tmp_path):
    cvm = _cvm(_delib(15, "dominio", "x.com\n## Título falso | `código`"))
    a, b = duas(tmp_path, b={"saidas": cvm})
    texto = renderizar_diff(comparar(a, b, MATRIZ))
    assert "\n## Título falso" not in texto and "\n- Sinais e alertas novos" in texto


def test_diff_alerta_de_outro_regulador_da_pc4(tmp_path):
    pc4 = resposta(
        valor={"alerta_vigente": True, "alertas": [{"regulador": "FCA", "data": "2026-08-15", "url": "https://fca.example/w"}]}
    )
    a, b = duas(tmp_path, b={"saidas": {"pend_c4": pc4}})
    assert comparar(a, b, MATRIZ).sinais_novos == ["alerta FCA (2026-08-15)"]


def test_diff_repontua_a_execucao_anterior_com_a_propria_anterior(tmp_path):
    """O E6 por duas falhas de captura precisa da execução que veio antes da `a`: `comparar` a carrega."""
    falha = ("erro", "captura falhou: net::ERR_CONNECTION_REFUSED")
    anteontem = AGORA - timedelta(days=2)
    gravar(tmp_path, agora=anteontem, status={"captura": falha})
    pasta_a = gravar(tmp_path, agora=ONTEM, status={"captura": falha})
    pasta_b = gravar(tmp_path, agora=AGORA, status={"captura": falha})
    d = comparar(carregar_execucao(pasta_a), carregar_execucao(pasta_b), MATRIZ)
    assert d.estagio_a == "E6" and d.estagio_b == "E6"


# ---------------------------------------------------------------------------- infraestrutura


@pytest.mark.parametrize(
    "mudanca,esperado",
    [
        ({"A": ["198.51.100.9"]}, ["hospedagem mudou"]),
        ({"AAAA": ["2001:db8::1"]}, ["hospedagem mudou"]),
        ({"NS": ["ns9.outro.com"]}, ["NS mudou"]),
        ({"MX": ["10 mx.outro.com."]}, ["MX mudou"]),
        ({"A": ["198.51.100.9"], "NS": ["ns9.outro.com"], "MX": []}, ["hospedagem mudou", "NS mudou", "MX mudou"]),
        ({"NS": ["NS1.EXEMPLO.COM.BR"]}, []),  # mesmo conjunto: caixa e ponto final não contam
        ({}, []),
    ],
)
def test_diff_infra_dns(tmp_path, mudanca, esperado):
    a, b = duas(tmp_path, b={"saidas": dns(**mudanca)})
    assert comparar(a, b, MATRIZ).infra == esperado


def test_diff_infra_ordem_dos_enderecos_nao_conta(tmp_path):
    a, b = duas(
        tmp_path,
        a={"saidas": dns(A=["203.0.113.7", "203.0.113.8"])},
        b={"saidas": dns(A=["203.0.113.8", "203.0.113.7"])},
    )
    assert comparar(a, b, MATRIZ).infra == []


def test_diff_infra_sem_dns_de_um_lado_nao_compara(tmp_path):
    a, b = duas(tmp_path, b={"status": {"dns": ("pulado", "só atual")}})
    assert comparar(a, b, MATRIZ).infra == []


@pytest.mark.parametrize("dias,expira", [(59, True), (60, False), (0, True), (-5, True), (400, False)])
def test_diff_dominio_perto_de_expirar(tmp_path, dias, expira):
    expiracao = (AGORA.date() + timedelta(days=dias)).isoformat()
    base = saidas_base()["rdap"]
    a, b = duas(tmp_path, b={"saidas": {"rdap": {**base, "expiracao": expiracao}}})
    assert ("domínio expira em menos de 60 dias" in comparar(a, b, MATRIZ).infra) is expira


def test_diff_expiracao_desconhecida_nao_alerta(tmp_path):
    a, b = duas(tmp_path, b={"saidas": {"rdap": {**saidas_base()["rdap"], "expiracao": None}}})
    assert comparar(a, b, MATRIZ).infra == []


def test_diff_site_fora_do_ar_por_nxdomain(tmp_path):
    a, b = duas(tmp_path, b={"saidas": dns(A=["203.0.113.7"], nxdomain=True)})
    assert comparar(a, b, MATRIZ).infra == ["site fora do ar"]


@pytest.mark.parametrize(
    "motivo,fora_do_ar",
    [
        ("captura falhou: navegação: timeout", True),
        ("captura falhou: net::ERR_CONNECTION_REFUSED", True),
        ("captura falhou: HTTP 503", True),
        ("captura falhou: HTTP 521", True),
        ("captura falhou: HTTP 404", True),
        # o site respondeu e recusou o visitante (WAF, bloqueio geográfico): não é o site fora do ar (R-T14-e6)
        ("captura falhou: HTTP 403", False),
        ("captura falhou: HTTP 429", False),
        # erro do nosso código, não do site
        ("erro inesperado: KeyError: 'paginas'", False),
        ("motivo de erro", False),
    ],
)
def test_diff_site_fora_do_ar_por_captura_que_falhou_so_no_b(tmp_path, motivo, fora_do_ar):
    a, b = duas(tmp_path, b={"status": {"captura": ("erro", motivo)}})
    assert comparar(a, b, MATRIZ).infra == (["site fora do ar"] if fora_do_ar else [])


def test_diff_site_fora_do_ar_usa_o_criterio_da_pontuacao(tmp_path):
    """Mesma função do E6: o que o E6 chama de "site não respondeu" é o que o diff chama de "fora do ar"."""
    motivos = ["captura falhou: navegação: timeout", "captura falhou: HTTP 403", "erro inesperado: KeyError", "captura falhou: HTTP 502"]
    for n, motivo in enumerate(motivos):
        a, b = duas(tmp_path / f"caso{n}", b={"status": {"captura": ("erro", motivo)}})
        assert (comparar(a, b, MATRIZ).infra == ["site fora do ar"]) is site_nao_respondeu(b)


def test_diff_captura_que_ja_respondia_403_e_agora_cai_e_novidade(tmp_path):
    """A 403 em `a` não é "fora do ar"; o 503 em `b` é: a queda é nova."""
    a, b = duas(
        tmp_path,
        a={"status": {"captura": ("erro", "captura falhou: HTTP 403")}},
        b={"status": {"captura": ("erro", "captura falhou: HTTP 503")}},
    )
    assert comparar(a, b, MATRIZ).infra == ["site fora do ar"]


def test_diff_captura_que_ja_falhava_nao_e_novidade(tmp_path):
    falha = {"status": {"captura": ("erro", "captura falhou: navegação: timeout")}}
    a, b = duas(tmp_path, a=falha, b=falha)
    assert "site fora do ar" not in comparar(a, b, MATRIZ).infra


REDIRECT = {
    "dominio": "phinvestimentos.com",
    "redirecionado_de": "exemplo.com.br",
    "url_destino": "https://phinvestimentos.com/login",
}


CAPTURA_COM_REDIRECT = {
    **saidas_base()["captura"],
    "destino": {"url": REDIRECT["url_destino"], "dominio": REDIRECT["dominio"]},
    "redirect_ignorado": None,
}
# o DNS do destino: outra hospedagem, outro NS e sem MX, comparado com o do alvo da saída base
DNS_DO_DESTINO = {**saidas_base()["dns"], "A": ["76.76.21.21"], "NS": ["ns1.vercel-dns.com."], "MX": []}
COM_REDIRECT = {"saidas": {"destino": REDIRECT, "captura": CAPTURA_COM_REDIRECT, "dns": DNS_DO_DESTINO}}


def sem_o_no_destino(ex):
    """A execução como era antes da T1: sem o nó `destino` no estado nem nas evidências."""
    ex.status.pop("destino", None)
    ex.saidas.pop("destino", None)
    return ex


def test_diff_dominio_analisado_que_mudou_nao_compara_o_dns(tmp_path):
    a, b = duas(tmp_path, b=COM_REDIRECT)
    d = comparar(a, b, MATRIZ)
    # o DNS de b é de outro domínio: hospedagem, NS e MX diferentes não são mudança de infraestrutura
    assert d.infra == ["domínio analisado mudou: exemplo.com.br → phinvestimentos.com"]
    assert "  - domínio analisado mudou: exemplo.com.br → phinvestimentos.com" in renderizar_diff(d)
    # e de volta: o redirect sumiu
    assert comparar(b, a, MATRIZ).infra == ["domínio analisado mudou: phinvestimentos.com → exemplo.com.br"]


def test_diff_mesmo_dominio_analisado_compara_o_dns(tmp_path):
    outro_dns = {**DNS_DO_DESTINO, "A": ["76.76.21.22"]}
    b = {"saidas": {**COM_REDIRECT["saidas"], "destino": {**REDIRECT, "url_destino": "x"}, "dns": outro_dns}}
    a, b = duas(tmp_path, a=COM_REDIRECT, b=b)
    assert comparar(a, b, MATRIZ).infra == ["hospedagem mudou"]


def test_diff_captura_em_erro_depois_do_redirect_diz_que_o_dominio_mudou(tmp_path):
    # o caso do revisor: em b a captura caiu (HTTP 403 no destino) e os coletores voltaram ao redirecionador
    a, b = duas(tmp_path, a=COM_REDIRECT, b={"status": {"captura": ("erro", "captura falhou: HTTP 403")}})
    d = comparar(a, b, MATRIZ)
    assert d.infra == ["domínio analisado mudou: phinvestimentos.com → exemplo.com.br (sem captura em b)"]


def test_diff_execucao_de_antes_do_no_destino_vale_pelo_alvo(tmp_path):
    # o caso do revisor: a execução antiga analisou o alvo; a nova seguiu o redirect
    a, b = duas(tmp_path, b=COM_REDIRECT)
    d = comparar(sem_o_no_destino(a), b, MATRIZ)
    assert d.infra == ["domínio analisado mudou: exemplo.com.br → phinvestimentos.com"]
    # as duas de antes do nó: o mesmo alvo, o DNS é comparado como sempre
    a, b = duas(tmp_path / "antigas", b={"saidas": dns(A=["198.51.100.9"])})
    assert comparar(sem_o_no_destino(a), sem_o_no_destino(b), MATRIZ).infra == ["hospedagem mudou"]


NAO_COMPARAVEL = "- Capturas novas no Wayback: não comparável (domínio analisado mudou)"


def test_diff_dominio_analisado_que_mudou_nao_soma_as_capturas_do_wayback(tmp_path):
    indice = {**saidas_base()["wayback_indice"], "total": 500}
    a, b = duas(tmp_path, b={"saidas": {**COM_REDIRECT["saidas"], "wayback_indice": indice}})
    d = comparar(a, b, MATRIZ)
    # 500 capturas de outro domínio não são 380 novas: o campo diz "não comparável" (None), não 0
    assert d.wayback_novas is None
    texto = renderizar_diff(d)
    assert NAO_COMPARAVEL in texto.splitlines()
    assert "Capturas novas no Wayback: 0" not in texto and "Capturas novas no Wayback: None" not in texto


def test_diff_wayback_nao_comparavel_vale_nos_dois_sentidos_e_sem_captura(tmp_path):
    # o redirect que some, e o domínio que mudou porque a captura caiu (o `destino` voltou ao alvo)
    a, b = duas(tmp_path, a=COM_REDIRECT)
    assert comparar(a, b, MATRIZ).wayback_novas is None
    a, b = duas(tmp_path / "sem_captura", a=COM_REDIRECT, b={"status": {"captura": ("erro", "captura falhou: HTTP 403")}})
    d = comparar(a, b, MATRIZ)
    assert d.wayback_novas is None and NAO_COMPARAVEL in renderizar_diff(d).splitlines()


def test_diff_mesmo_dominio_analisado_continua_contando_as_capturas_do_wayback(tmp_path):
    # com o mesmo redirect nas duas execuções, o domínio analisado é o mesmo e o Wayback se compara
    indice = {**saidas_base()["wayback_indice"], "total": 150}
    b = {"saidas": {**COM_REDIRECT["saidas"], "wayback_indice": indice}}
    a, b = duas(tmp_path, a=COM_REDIRECT, b=b)
    d = comparar(a, b, MATRIZ)
    assert d.wayback_novas == 30 and "- Capturas novas no Wayback: 30" in renderizar_diff(d).splitlines()


def test_diff_infra_na_ordem_e_renderizada(tmp_path):
    a, b = duas(
        tmp_path,
        b={"saidas": {**dns(A=["198.51.100.9"], NS=["ns9.outro.com"]), "rdap": {**saidas_base()["rdap"], "expiracao": "2026-11-01"}}},
    )
    d = comparar(a, b, MATRIZ)
    assert d.infra == ["hospedagem mudou", "NS mudou", "domínio expira em menos de 60 dias"]
    texto = renderizar_diff(d)
    for linha in d.infra:
        assert linha in texto


# ---------------------------------------------------------------------------- Wayback


@pytest.mark.parametrize("total_b,esperado", [(150, 30), (120, 0), (100, 0)])
def test_diff_capturas_novas_no_wayback(tmp_path, total_b, esperado):
    indice = saidas_base()["wayback_indice"]
    a, b = duas(tmp_path, b={"saidas": {"wayback_indice": {**indice, "total": total_b}}})
    d = comparar(a, b, MATRIZ)
    assert d.wayback_novas == esperado
    assert (f"Capturas novas no Wayback: {esperado}" in renderizar_diff(d))


def test_diff_wayback_ausente_vale_zero(tmp_path):
    a, b = duas(tmp_path, b={"status": {"wayback_indice": ("erro", "429")}})
    assert comparar(a, b, MATRIZ).wayback_novas == 0


# ---------------------------------------------------------------------------- matriz


def _pontuacao_json(pasta: Path, hash_: str, eixo1: Eixo1, versao: str = "2026-09-01") -> None:
    gravar_json_atomico(
        pasta / "pontuacao.json",
        {
            "matriz": {"versao": versao, "hash": hash_},
            "itens": {},
            "eixo1": eixo1.model_dump(mode="json"),
            "eixo2": {"estagio": None, "sinal": None, "janela": None, "modificadores": []},
            "gerado_em": "2026-10-06T12:00:00+00:00",
        },
    )


ANTIGO = Eixo1(minimo=99, maximo=99, classe="característico", pode_chegar_a=None, regras_disparadas=[], regras_pendentes=[])


def test_diff_matriz_diferente_mostra_duas_contas(tmp_path):
    a, b = duas(tmp_path)
    _pontuacao_json(a.ctx.pasta, "ab" * 32, ANTIGO)
    d = comparar(a, b, MATRIZ)
    assert d.matriz_diferente is True
    assert d.eixo1_a_matriz_original == ANTIGO
    # a conta atual da execução antiga vem dos julgamentos guardados, não do JSON
    assert (d.eixo1_a.minimo, d.eixo1_a.maximo) == (8, 10)
    texto = renderizar_diff(d)
    assert "99 de 34" in texto and "8–10 de 34" in texto
    assert "2026-09-01" in texto and MATRIZ.versao in texto


def test_diff_mesma_matriz_nao_mostra_duas_contas(tmp_path):
    a, b = duas(tmp_path)
    _pontuacao_json(a.ctx.pasta, MATRIZ.hash, ANTIGO, versao=MATRIZ.versao)
    d = comparar(a, b, MATRIZ)
    assert d.matriz_diferente is False and d.eixo1_a_matriz_original is None
    assert "99 de 34" not in renderizar_diff(d)


def test_diff_sem_pontuacao_json_a_matriz_vale_igual(tmp_path):
    a, b = duas(tmp_path)
    assert not (a.ctx.pasta / "pontuacao.json").exists()
    d = comparar(a, b, MATRIZ)
    assert d.matriz_diferente is False and d.eixo1_a_matriz_original is None


@pytest.mark.parametrize("conteudo", ["{isto não é json", "[]", '{"matriz": {"versao": "x"}}', '{"matriz": {"hash": 5}}'])
def test_diff_pontuacao_json_ilegivel_vale_como_ausente(tmp_path, conteudo):
    a, b = duas(tmp_path)
    (a.ctx.pasta / "pontuacao.json").write_text(conteudo, encoding="utf-8")
    d = comparar(a, b, MATRIZ)
    assert d.matriz_diferente is False and d.eixo1_a_matriz_original is None


def test_diff_matriz_diferente_com_eixo1_ilegivel_no_json(tmp_path):
    """Hash diferente mas o `eixo1` guardado não é um Eixo1: a diferença fica registrada, sem a conta original."""
    a, b = duas(tmp_path)
    gravar_json_atomico(
        a.ctx.pasta / "pontuacao.json", {"matriz": {"versao": "2026-09-01", "hash": "cd" * 32}, "eixo1": {"minimo": "x"}}
    )
    d = comparar(a, b, MATRIZ)
    assert d.matriz_diferente is True and d.eixo1_a_matriz_original is None
    assert "2026-09-01" in renderizar_diff(d)


# ---------------------------------------------------------------------------- textos


def test_texto_do_intervalo_e_da_classe():
    assert texto_intervalo(8, 19, 34) == "8–19 de 34"
    assert texto_intervalo(8, 8, 34) == "8 de 34"
    mais = Eixo1(minimo=8, maximo=19, classe="provável", pode_chegar_a="característico", regras_disparadas=[], regras_pendentes=[])
    assert texto_classe(mais) == "provável (pode chegar a característico)"
    assert texto_classe(ANTIGO) == "característico"


def test_diff_e_um_dataclass_com_os_campos_do_brief(tmp_path):
    a, b = duas(tmp_path)
    d = comparar(a, b, MATRIZ)
    assert isinstance(d, Diff)
    campos = (
        "eixo1_a eixo1_b estagio_a estagio_b itens_mudados sinais_novos infra socios_entraram socios_sairam "
        "wayback_novas matriz_diferente eixo1_a_matriz_original"
    ).split()
    assert all(hasattr(d, campo) for campo in campos)
    assert isinstance(d.eixo1_a, Eixo1) and isinstance(d.eixo1_b, Eixo1)


def test_renderizar_diff_intervalo_e_classe_que_mudaram(tmp_path):
    a, b = duas(
        tmp_path, b={"saidas": {"pend_a1": resposta(valor={"pct_mes": 0.5, "taxa_diaria": False, "garantido": False})}}
    )
    texto = renderizar_diff(comparar(a, b, MATRIZ))
    assert "Intervalo: 8–10 de 34 → 6–8 de 34" in texto
    assert "Classe: provável → suspeito" in texto


def test_diff_matriz_diferente_com_a_mesma_versao_traz_o_hash(tmp_path):
    """Duas matrizes com a mesma versão (alguém mudou o YAML sem mudar `versao`): só o hash as distingue."""
    a, b = duas(tmp_path)
    _pontuacao_json(a.ctx.pasta, "ab" * 32, ANTIGO, versao=MATRIZ.versao)
    d = comparar(a, b, MATRIZ)
    assert d.matriz_diferente is True
    assert d.matriz_versoes == (f"{MATRIZ.versao} (hash abababab)", f"{MATRIZ.versao} (hash {MATRIZ.hash[:8]})")
    texto = renderizar_diff(d)
    assert "(hash abababab)" in texto and f"(hash {MATRIZ.hash[:8]})" in texto


def test_diff_matriz_diferente_com_versoes_diferentes_nao_poe_hash(tmp_path):
    a, b = duas(tmp_path)
    _pontuacao_json(a.ctx.pasta, "ab" * 32, ANTIGO, versao="2026-09-01")
    d = comparar(a, b, MATRIZ)
    assert d.matriz_versoes == ("2026-09-01", MATRIZ.versao)
    assert "hash" not in renderizar_diff(d)
