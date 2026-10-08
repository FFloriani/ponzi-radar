"""Dossiê de risco (Tarefa 15, spec 8.4): o `dossie.md` que o usuário lê, a `pontuacao.json` e o `diff.md`."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from jinja2 import UndefinedError

from radar.custodia import Custodia, hash_final, verificar
from radar.execucao import carregar_execucao
from radar.pendencias.definicoes import nova_pendencia
from radar.dossie import PendenciasAbertas, gerar_dossie
from radar.pontuacao import Eixo1
from radar.texto import escapar_md
from tests.execucao_em_disco import (
    AGORA,
    MATRIZ,
    PAGINA,
    PETROBRAS,
    REF_NOTICIA,
    REF_PAGINA,
    URL_NOTICIA,
    evidencias,
    gravar,
    pend_e_com,
    resposta,
    saidas_base,
    sinal_e,
)

BS = chr(92)  # barra invertida
TITULOS = [
    "## 1. Identificação",
    "## 2. Veredito",
    "## 3. Itens da matriz",
    "## 4. Linha do tempo",
    "## 5. Empresa e pessoas",
    "## 6. Infraestrutura",
    "## 7. Lacunas",
    "## 8. Mudanças desde a execução anterior",
    "## 9. Anexo: artefatos e verificação",
]
CPF = re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}")


def dossie(pasta: Path, **kw) -> str:
    return gerar_dossie(pasta, MATRIZ, **kw).read_text(encoding="utf-8")


def secao(texto: str, n: int) -> str:
    """O texto da seção `n` (do título até o próximo)."""
    inicio = texto.index(TITULOS[n - 1])
    fim = texto.index(TITULOS[n]) if n < len(TITULOS) else len(texto)
    return texto[inicio:fim]


def celulas(linha: str) -> int:
    """Quantas células tem a linha da tabela: as barras que separam, sem as escapadas."""
    return len(re.findall(r"(?<!\\)\|", linha)) - 1


# ---------------------------------------------------------------------------- pendências


def test_dossie_exige_pendencias_fechadas(tmp_path):
    pasta = gravar(tmp_path, abertas=("P-A1",))
    with pytest.raises(PendenciasAbertas) as erro:
        gerar_dossie(pasta, MATRIZ)
    assert erro.value.ids == ["P-A1"]
    assert "P-A1" in str(erro.value)
    assert not (pasta / "dossie.md").exists() and not (pasta / "pontuacao.json").exists()


def test_dossie_lista_todas_as_pendencias_abertas(tmp_path):
    pasta = gravar(tmp_path, abertas=("P-B", "P-A1"))
    with pytest.raises(PendenciasAbertas) as erro:
        gerar_dossie(pasta, MATRIZ)
    assert sorted(erro.value.ids) == ["P-A1", "P-B"]


def test_dossie_forcar_vira_nao_verificado(tmp_path):
    pasta = gravar(tmp_path, abertas=("P-A1",))
    md_ = dossie(pasta, forcar=True)
    lacunas = secao(md_, 7)
    assert "A1 — não verificado" in lacunas
    assert "P-A1" in lacunas
    # o aviso de que o dossiê saiu com pendência aberta fica no veredito
    assert "P-A1" in secao(md_, 2) and "forçado" in secao(md_, 2).lower()
    # o item aberto soma o máximo dele ao intervalo: A3 2 + C1 3 = 5 de mínimo; 5 + A1 4 + D2 2 = 11 de máximo
    assert "5–11 de 34" in secao(md_, 2)


def test_dossie_sem_pendencia_aberta_nao_avisa_de_forcado(tmp_path):
    pasta = gravar(tmp_path)
    assert "forçado" not in dossie(pasta, forcar=True).lower()


# ---------------------------------------------------------------------------- estrutura e textos


def test_dossie_estrutura_e_textos(tmp_path):
    pasta = gravar(tmp_path)
    caminho = gerar_dossie(pasta, MATRIZ)
    assert caminho == pasta / "dossie.md"
    md_ = caminho.read_text(encoding="utf-8")
    for titulo in [*TITULOS, "Heurística não validada: os pesos ainda não foram calibrados.", "de 34"]:
        assert titulo in md_
    posicoes = [md_.index(t) for t in TITULOS]
    assert posicoes == sorted(posicoes)
    assert not CPF.search(md_)
    assert "\r" not in md_ and md_.endswith("\n")


def test_dossie_nao_mexe_na_custodia(tmp_path):
    pasta = gravar(tmp_path)
    antes = hash_final(pasta)
    dossie(pasta)
    assert hash_final(pasta) == antes and verificar(pasta) == []


def test_dossie_cabecalho_com_hash_da_custodia_e_da_matriz(tmp_path):
    pasta = gravar(tmp_path)
    s1 = secao(dossie(pasta), 1)
    assert "exemplo.com.br" in s1 and "2026-10-07" in s1 and "exemplo-com-br/2026-10-07_120000" in s1
    assert MATRIZ.versao in s1 and MATRIZ.hash in s1
    assert hash_final(pasta) in s1
    assert "captura" in s1  # modo_contato
    assert "modo cego" in s1.lower()


def test_dossie_retroativo_diz_que_olha_o_passado(tmp_path):
    pasta = gravar(tmp_path, as_of=date(2019, 7, 1))
    s1 = secao(dossie(pasta), 1)
    assert "2019-07-01" in s1 and "retroativ" in s1.lower()


def test_dossie_custodia_vazia_nao_quebra_o_cabecalho(tmp_path):
    pasta = gravar(tmp_path)
    (pasta / "custodia.log").unlink()
    md_ = dossie(pasta)
    assert "sem registros" in secao(md_, 1) and "nenhum artefato" in secao(md_, 9).lower()


def test_dossie_intervalo_classe_e_regras(tmp_path):
    pasta = gravar(tmp_path)
    s2 = secao(dossie(pasta), 2)
    assert "8–10 de 34" in s2
    assert "provável" in s2 and "R1" in s2
    assert "pode chegar a" not in s2


def test_dossie_pode_chegar_a_e_regra_pendente(tmp_path):
    pasta = gravar(tmp_path, abertas=("P-B",))
    s2 = secao(dossie(pasta, forcar=True), 2)
    assert "8–19 de 34" in s2
    assert "provável (pode chegar a característico)" in s2
    assert "R2 dispara se B4 se confirmar" in s2


def test_dossie_eixo2_sem_sinal(tmp_path):
    s2 = secao(dossie(gravar(tmp_path)), 2)
    assert "sem estágio (nenhum sinal de estágio)" in s2 and "previsão numérica" in s2
    assert "nenhum sinal confirmado" not in s2


def test_dossie_eixo2_estagio_sinal_janela_e_modificadores(tmp_path):
    pend_e = pend_e_com(
        sinal_e("atraso_pagamento", "2026-09-20", 0),
        modificadores=[{"id": "midia_de_massa", "evidencia": 1}],
    )
    s2 = secao(dossie(gravar(tmp_path, saidas={"pend_e": pend_e})), 2)
    assert "E4" in s2 and "atraso_pagamento" in s2 and "2026-09-20" in s2
    assert escapar_md(MATRIZ.janelas["E4"]) in s2  # o "~" do texto da matriz sai escapado
    assert "midia_de_massa" in s2 and "encurta" in s2
    assert "previsão numérica" in s2


def test_dossie_eixo2_sinal_do_coletor(tmp_path):
    recentes = {
        "rdap": {**saidas_base()["rdap"], "registro": "2026-09-01"},
        "cnpj": {**saidas_base()["cnpj"], "abertura": "2026-09-05"},
    }
    pasta = gravar(tmp_path, saidas=recentes)
    s2 = secao(dossie(pasta), 2)
    assert "E0" in s2 and "registro_recente" in s2 and "coletor" in s2


# ---------------------------------------------------------------------------- seção 3: itens


def test_dossie_tabela_tem_os_15_itens_e_as_colunas(tmp_path):
    s3 = secao(dossie(gravar(tmp_path)), 3)
    linhas = [linha for linha in s3.splitlines() if linha.startswith("|")]
    cabecalho = linhas[0]
    for coluna in ["Item", "Estado", "Pontos", "Origem", "Marcas", "Trecho", "Fonte", "Hash", "Nota"]:
        assert coluna in cabecalho
    assert len({celulas(linha) for linha in linhas}) == 1
    ids = [re.match(r"\| (\w\d)\b", linha) for linha in linhas[2:]]
    assert {m.group(1) for m in ids if m} == set(MATRIZ.itens)


def test_dossie_item_confirmado_mostra_trecho_fonte_hash_e_origem(tmp_path):
    s3 = secao(dossie(gravar(tmp_path)), 3)
    linhas_a1 = [linha for linha in s3.splitlines() if linha.startswith("| A1")]
    assert len(linhas_a1) == 2  # uma linha por evidência
    primeira, segunda = linhas_a1
    assert "confirmado" in primeira and "3/4" in primeira
    assert "Rendimento de 5% ao mês garantido" in primeira
    # a fonte `sha256:` mostra de onde veio o artefato; o hash é o dela
    assert REF_PAGINA[:19] in primeira and "https://exemplo.com.br/" in primeira
    # a fonte URL mostra a URL e o hash do artefato arquivado (`tipo=fonte`, `origem=url`)
    assert URL_NOTICIA in segunda and REF_NOTICIA[:19] in segunda
    assert "imprensa" in segunda
    # a segunda linha do item é só a continuação: estado, pontos, origem e marcas ficam na primeira
    assert segunda.startswith("| A1 |  |  |  |  | paga 5% ao mês |")
    # a origem: P-A1 tem candidato de percentual? sem candidatos na fixture, quem achou foi o Claude
    assert "Claude" in primeira


def test_dossie_item_do_coletor_mostra_a_nota_e_nenhum_hash(tmp_path):
    s3 = secao(dossie(gravar(tmp_path)), 3)
    c1 = next(linha for linha in s3.splitlines() if linha.startswith("| C1"))
    assert "coletor" in c1 and "3/3" in c1 and "sem registro na CVM nem no BCB" in c1


def test_dossie_item_do_coletor_cita_o_no_na_coluna_fonte(tmp_path):
    """C1, C3 (parte automática), C4 (pela CVM) e D3: a fonte é o nó do coletor, sem hash."""
    alerta = {
        "tipo": "cnpj", "valor": PETROBRAS, "numero": 9, "data": "2026-01-01",
        "url": "https://cvm.example/9", "trecho": "atuação irregular",
    }  # fmt: skip
    pasta = gravar(
        tmp_path,
        saidas={
            "cnpj": {**saidas_base()["cnpj"], "cnae": 4711302},  # fora da seção K, com oferta de investimento: C3
            "cvm_alertas": {"correspondencias": [alerta], "cobertura": {"com_texto_integral": 1, "so_resumo": 0}},
        },
    )
    linhas = secao(dossie(pasta), 3).splitlines()

    def celula_fonte(item: str) -> str:
        linha = next(linha for linha in linhas if linha.startswith(f"| {item}"))
        return linha.split(" | ")[6]

    assert celula_fonte("C1") == "coletor: registros"
    assert celula_fonte("C3") == "coletor: cnpj"
    assert celula_fonte("D3") == "coletor: rdap, cnpj"
    # o C4 pela CVM traz também a evidência da deliberação
    assert celula_fonte("C4").startswith("coletor: cvm_alertas; oficial, 2026-01-01 — `https://cvm.example/9`")
    # item que não é do coletor não leva a marca
    assert "coletor" not in celula_fonte("A1") and "coletor" not in celula_fonte("D2")


def test_dossie_item_nao_verificado_mostra_o_intervalo_de_pontos(tmp_path):
    s3 = secao(dossie(gravar(tmp_path)), 3)
    d2 = next(linha for linha in s3.splitlines() if linha.startswith("| D2"))
    assert "não verificado" in d2 and "0–2" in d2


def test_dossie_estados_com_acento(tmp_path):
    s3 = secao(dossie(gravar(tmp_path)), 3)
    assert "não se aplica" in s3 and "nao_se_aplica" not in s3


def test_dossie_item_confirmado_so_mostra_evidencia_de_item_confirmado(tmp_path):
    """Os quatro itens da P-B dividem a resposta: só o que pontuou leva as evidências para a tabela."""
    b = resposta(valor={"indicacao": "nenhuma", "token_proprio": True, "carencia_com_multa": False, "taxa_para_sacar": False})
    s3 = secao(dossie(gravar(tmp_path, saidas={"pend_b": b})), 3)
    assert len([linha for linha in s3.splitlines() if linha.startswith("| B2")]) == 2
    assert not [linha for linha in s3.splitlines() if linha.startswith("| B1") and "Rendimento" in linha]


def test_dossie_mostra_as_marcas_de_validacao(tmp_path):
    pasta = gravar(tmp_path, marcas={"P-A1": ["trecho_nao_conferido", "data_desconhecida"]})
    s3 = secao(dossie(pasta), 3)
    a1 = next(linha for linha in s3.splitlines() if linha.startswith("| A1"))
    assert "trecho_nao_conferido" in a1 and "data_desconhecida" in a1
    a3 = next(linha for linha in s3.splitlines() if linha.startswith("| A3"))
    assert "trecho_nao_conferido" not in a3


def test_dossie_sem_marcas_no_julgamento_nao_quebra(tmp_path):
    s3 = secao(dossie(gravar(tmp_path)), 3)  # os julgamentos da fixture não têm a chave `marcas`
    a1 = next(linha for linha in s3.splitlines() if linha.startswith("| A1"))
    assert "—" in a1


def test_dossie_marcas_so_valem_para_o_item_da_pendencia(tmp_path):
    """C4 confirmado pelo coletor (CVM) não herda as marcas do julgamento da P-C4."""
    alerta = {
        "tipo": "cnpj", "valor": PETROBRAS, "numero": 9, "data": "2026-01-01",
        "url": "https://cvm.example/9", "trecho": "atuação irregular",
    }  # fmt: skip
    pasta = gravar(
        tmp_path,
        saidas={"cvm_alertas": {"correspondencias": [alerta], "cobertura": {"com_texto_integral": 1, "so_resumo": 0}}},
        marcas={"P-C4": ["trecho_nao_conferido"]},
    )
    c4 = next(linha for linha in secao(dossie(pasta), 3).splitlines() if linha.startswith("| C4"))
    assert "coletor" in c4 and "trecho_nao_conferido" not in c4


def test_dossie_escapa_o_conteudo_do_site_nas_tabelas(tmp_path):
    ruim = (
        "paga 5% | ao mês\nsegunda linha\N{LINE SEPARATOR}terceira <script>alert(1)</script> "
        "[clique](http://evil.example) **forte** `código` _it_ CPF 123.456.789-09"
    )
    a1 = resposta(
        valor={"pct_mes": 5.0, "taxa_diaria": False, "garantido": True},
        evidencias_=[{"fonte": REF_PAGINA, "trecho": ruim, "data_fonte": None, "tipo_fonte": "operador"}],
    )
    md_ = dossie(gravar(tmp_path, saidas={"pend_a1": a1}))
    s3 = secao(md_, 3)
    linhas = [linha for linha in s3.splitlines() if linha.startswith("|")]
    assert len({celulas(linha) for linha in linhas}) == 1  # o "|" do trecho não criou célula
    assert all(linha.startswith("| ") for linha in linhas)
    a1_linha = next(linha for linha in linhas if linha.startswith("| A1"))
    assert "\\|" in a1_linha and "ao mês" in a1_linha and "segunda linha terceira" in a1_linha
    assert "<script>" not in md_ and "\\<script\\>" in md_
    assert "[clique](" not in md_ and "\\[clique\\]" in md_
    assert "**forte**" not in md_ and "\\*\\*forte\\*\\*" in md_
    assert not CPF.search(md_) and "(CPF omitido)" in md_


# ---------------------------------------------------------------------------- seção 4: linha do tempo


def test_dossie_linha_do_tempo_em_ordem_de_data(tmp_path):
    alerta = {
        "tipo": "dominio", "valor": "exemplo.com.br", "numero": 55, "data": "2026-06-01",
        "url": "https://cvm.example/d55", "trecho": "atuação irregular",
    }  # fmt: skip
    pasta = gravar(
        tmp_path,
        saidas={
            "cvm_alertas": {"correspondencias": [alerta], "cobertura": {"com_texto_integral": 1, "so_resumo": 0}},
            "pend_e": pend_e_com(sinal_e("escalada_taxa", "2026-09-20", 0)),
        },
    )
    s4 = secao(dossie(pasta), 4)
    ordem = ["2014-01-10", "2015-03-02", "2016-01-12", "2019-05-20", "2026-06-01", "2026-09-20", "2026-09-30"]
    posicoes = [s4.index(d) for d in ordem]
    assert posicoes == sorted(posicoes)
    for texto in ["CNPJ aberto", "Domínio registrado", "Primeiro snapshot", "Primeiro certificado", "Deliberação 55",
                  "escalada_taxa", "Último snapshot"]:
        assert texto in s4  # fmt: skip


def test_dossie_linha_do_tempo_sem_datas_dos_nos_que_falharam(tmp_path):
    pasta = gravar(tmp_path, status={"ct": ("erro", "crt.sh: 503"), "wayback_indice": "bloqueado", "cnpj": ("erro", "x")})
    s4 = secao(dossie(pasta), 4)
    assert "certificado" not in s4.lower() and "snapshot" not in s4.lower() and "CNPJ aberto" not in s4
    assert "Domínio registrado" in s4


def test_dossie_sinal_sem_data_vai_para_o_fim_da_linha_do_tempo(tmp_path):
    pend_e = pend_e_com(sinal_e("pico_reclamacoes", None, 0))
    s4 = secao(dossie(gravar(tmp_path, saidas={"pend_e": pend_e})), 4)
    assert s4.index("pico_reclamacoes") > s4.index("2026-09-30") and "sem data" in s4


# ---------------------------------------------------------------------------- seção 5: empresa e pessoas


def test_dossie_empresa_e_socios_sem_cpf(tmp_path):
    cnpj = saidas_base()["cnpj"]
    socio = {
        "nome": "JOAO | PEREIRA", "qualificacao": "Sócio", "entrada": "2020-02-03",
        "cpf": "123.456.789-09", "cnpj_cpf_do_socio": "***CPFZZ**",
    }  # fmt: skip
    pasta = gravar(tmp_path, saidas={"cnpj": {**cnpj, "socios": [*cnpj["socios"], socio]}})
    md_ = dossie(pasta)
    s5 = secao(md_, 5)
    assert "33.000.167/0001-01" in s5 and "EXEMPLO INVESTIMENTOS LTDA" in s5 and "Exemplo Invest" in s5
    assert "6619302" in s5 and "ATIVA" in s5 and "2014-01-10" in s5
    assert "MARIA DA SILVA" in s5 and "Sócio-Administrador" in s5
    assert "JOAO \\| PEREIRA" in s5 and "2020-02-03" in s5
    assert not CPF.search(md_) and "CPFZZ" not in md_


def test_dossie_cnae_com_zero_a_esquerda(tmp_path):
    cnpj = {**saidas_base()["cnpj"], "cnae": 111301}  # 0111301: o int perde o zero
    assert "0111301" in secao(dossie(gravar(tmp_path, saidas={"cnpj": cnpj})), 5)


def test_dossie_sem_cnpj_identificado(tmp_path):
    pasta = gravar(tmp_path, saidas={"cnpj": {"cnpj": None, "motivo": "não encontrado"}})
    s5 = secao(dossie(pasta), 5)
    assert "não identificado" in s5.lower() and "não encontrado" in s5


def test_dossie_cnpj_em_erro_diz_o_motivo_na_empresa(tmp_path):
    pasta = gravar(tmp_path, status={"cnpj": ("erro", "APIs de CNPJ indisponíveis: timeout")})
    assert "APIs de CNPJ indisponíveis: timeout" in secao(dossie(pasta), 5)


def test_dossie_registros_da_cvm_e_do_bcb(tmp_path):
    reg = {**saidas_base()["registros"], "bcb": [{"conjunto": "x", "raiz_cnpj": "33000167", "nome": "BANCO X"}], "registrado": True}
    s5 = secao(dossie(gravar(tmp_path, saidas={"registros": reg})), 5)
    assert "BCB" in s5 and "BANCO X" in s5


def test_dossie_pessoas_com_vinculo_a_esquemas(tmp_path):
    d1 = resposta(valor={"historico_fraude": True, "pessoas": [{"pessoa": "PEDRO ALVES", "vinculo": "operador da pirâmide Z"}]})
    s5 = secao(dossie(gravar(tmp_path, saidas={"pend_d1": d1})), 5)
    assert "PEDRO ALVES" in s5 and "operador da pirâmide Z" in s5


def test_dossie_sem_historico_de_fraude_nao_lista_pessoas_do_d1(tmp_path):
    d1 = resposta(valor={"historico_fraude": False, "pessoas": [{"pessoa": "PEDRO ALVES", "vinculo": "citado"}]})
    assert "PEDRO ALVES" not in dossie(gravar(tmp_path, saidas={"pend_d1": d1}))


def test_dossie_retroativo_marca_o_dado_de_hoje(tmp_path):
    vazamento = ["razao_social", "nome_fantasia", "cnae", "cnae_descricao", "capital_social", "situacao", "socios", "fonte"]
    pasta = gravar(
        tmp_path,
        as_of=date(2019, 7, 1),
        saidas={
            "cnpj": {**saidas_base()["cnpj"], "vazamento_temporal": vazamento},
            "registros": {**saidas_base()["registros"], "bcb": [{"conjunto": "x", "raiz_cnpj": "33000167", "nome": "BANCO X"}],
                          "registrado": True, "vazamento_temporal": ["bcb", "bcb_dominio"]},
        },
        status={"dns": ("pulado", "só atual"), "captura": ("pulado", "só atual")},
    )  # fmt: skip
    s5 = secao(dossie(pasta), 5)
    linhas = s5.splitlines()
    for rotulo in ["Razão social", "Nome fantasia", "CNAE", "Situação"]:
        assert "(dado de hoje)" in next(linha for linha in linhas if rotulo in linha), rotulo
    # abertura e CNPJ valem em qualquer as_of
    assert "(dado de hoje)" not in next(linha for linha in linhas if "Abertura" in linha)
    assert "(dado de hoje)" in next(linha for linha in linhas if "BANCO X" in linha)
    assert "(dado de hoje)" in next(linha for linha in linhas if "Sócios" in linha)


def test_dossie_modo_atual_nao_marca_dado_de_hoje(tmp_path):
    assert "(dado de hoje)" not in dossie(gravar(tmp_path))


# ---------------------------------------------------------------------------- seção 6: infraestrutura


def test_dossie_infraestrutura(tmp_path):
    s6 = secao(dossie(gravar(tmp_path)), 6)
    for texto in [
        "Registro.br", "2015-03-02", "2027-03-02",  # RDAP
        "203.0.113.7", "mail.exemplo.com.br", "ns1.exemplo.com.br",  # DNS
        "2019-05-20", "www.exemplo.com.br",  # certificados
        "2016-01-12", "2026-09-30", "120",  # Wayback
        "googletagmanager.com",  # terceiros carregados pela captura
    ]:  # fmt: skip
        assert texto in s6, texto


def test_dossie_infraestrutura_dos_nos_que_nao_rodaram(tmp_path):
    pasta = gravar(
        tmp_path,
        as_of=date(2019, 7, 1),
        status={"dns": ("pulado", "só atual"), "captura": ("pulado", "só atual"), "ct": ("erro", "crt.sh: 503")},
    )
    s6 = secao(dossie(pasta), 6)
    assert "só atual" in s6 and "crt.sh: 503" in s6


def test_dossie_lista_longa_de_sans_e_cortada(tmp_path):
    sans = [f"sub{i:03d}.exemplo.com.br" for i in range(60)]
    s6 = secao(dossie(gravar(tmp_path, saidas={"ct": {"primeiro_certificado": "2019-05-20", "total": 60, "sans": sans}})), 6)
    assert "sub000.exemplo.com.br" in s6 and "sub059.exemplo.com.br" not in s6 and "+40" in s6


# ---------------------------------------------------------------------------- seção 7: lacunas


def test_dossie_lacunas_com_wayback_sem_snapshot(tmp_path):
    """Foco 5: sem snapshot do Wayback e sem captura, o dossiê sai e as lacunas dizem por quê."""
    pasta = gravar(
        tmp_path,
        as_of=date(2019, 6, 1),
        status={
            "dns": ("pulado", "só atual"),
            "captura": ("pulado", "só atual"),
            "wayback_snapshot": ("erro", "sem snapshot até 2019-06-01"),
            "extracao": ("bloqueado", "dependência com erro: wayback_snapshot"),
            "pend_a1": ("bloqueado", "dependência bloqueada: extracao"),
            "pend_a3": ("bloqueado", "dependência bloqueada: pend_a1"),
            "pend_b": ("bloqueado", "dependência bloqueada: extracao"),
            "pend_c": ("bloqueado", "dependência bloqueada: extracao"),
            "pend_d1": ("bloqueado", "dependência bloqueada: extracao"),
            "pend_d4": ("bloqueado", "dependência bloqueada: extracao"),
            "cnpj": ("bloqueado", "dependência bloqueada: extracao"),
        },
    )
    md_ = dossie(pasta)
    s7 = secao(md_, 7)
    assert "sem snapshot até 2019-06-01" in s7
    assert "wayback_snapshot" in s7 and "extracao" in s7 and "dependência com erro: wayback_snapshot" in s7
    assert "`wayback_snapshot` — erro: sem snapshot até 2019-06-01 (para resolver: rodar de novo a análise)" in s7
    assert "`extracao` — bloqueado: dependência com erro: wayback_snapshot (para resolver: resolver a dependência wayback_snapshot)" in s7
    assert "`pend_a3` — bloqueado: dependência bloqueada: pend_a1 (para resolver: resolver a dependência pend_a1)" in s7
    assert "A1 — não verificado" in s7
    # nada vira zero: o intervalo se abre
    assert re.search(r"\d+–\d+ de 34", secao(md_, 2))


def test_dossie_lacunas_listam_cada_no_que_nao_terminou_com_o_motivo(tmp_path):
    pasta = gravar(
        tmp_path,
        status={"ct": ("erro", "crt.sh: resposta inválida"), "rdap": ("bloqueado", "dependência com erro: alvo"),
                "captura": ("pulado", "modo_contato=nenhum"), "cvm_alertas": "aguardando"},
    )  # fmt: skip
    s7 = secao(dossie(pasta), 7)
    assert "`ct` — erro: crt.sh: resposta inválida (para resolver: rodar de novo a análise)" in s7
    assert "`rdap` — bloqueado: dependência com erro: alvo (para resolver: resolver a dependência alvo)" in s7
    assert "`captura` — pulado: modo_contato=nenhum" in s7
    assert "`cvm_alertas` — aguardando" in s7


def test_dossie_lacunas_so_listam_pulado_que_deixa_dado_sem_cobertura(tmp_path):
    pasta = gravar(
        tmp_path,
        status={
            "dns": ("pulado", "só atual"),
            "captura": ("pulado", "modo_contato=nenhum"),
            "pend_a3": ("pulado", "dependência pulada: pend_a1"),
            "wayback_snapshot": ("pulado", "captura ok"),
            "pend_a2": ("pulado", "sem histórico de rentabilidade"),
            "pend_d4": ("pulado", "sem oferta de investimento"),
        },
    )
    s7 = secao(dossie(pasta), 7)
    assert "`dns` — pulado: só atual" in s7
    assert "`captura` — pulado: modo_contato=nenhum" in s7
    assert "`pend_a3` — pulado: dependência pulada: pend_a1" in s7
    # pulado sem resolução: o dado não existe nessa execução, rodar de novo não muda
    assert "`dns` — pulado: só atual (" not in s7
    for benigno in ["wayback_snapshot", "captura ok", "pend_a2", "pend_d4", "sem histórico de rentabilidade"]:
        assert benigno not in s7, benigno


def test_dossie_lacuna_de_no_aguardando_manda_responder_a_pendencia(tmp_path):
    s7 = secao(dossie(gravar(tmp_path, abertas=("P-B",)), forcar=True), 7)
    assert "`pend_b` — aguardando (para resolver: responder a P-B)" in s7


def test_dossie_lacunas_inconclusivo_e_nao_verificado(tmp_path):
    a1 = resposta("inconclusivo", evidencias_=[])
    s7 = secao(dossie(gravar(tmp_path, saidas={"pend_a1": a1})), 7)
    assert "A1 — inconclusivo" in s7 and "D2 — não verificado" in s7
    # a P-A1 já foi respondida (inconclusivo): precisa de outra resposta, com evidência
    assert "A1 — inconclusivo (para resolver: responder de novo a P-A1 com evidência)" in s7
    # o D2 não depende de pendência: nada a responder
    assert next(linha for linha in s7.splitlines() if linha.startswith("- D2")).count("para resolver") == 0


def test_dossie_lacunas_nao_listam_item_confirmado_nem_nao_se_aplica(tmp_path):
    s7 = secao(dossie(gravar(tmp_path)), 7)
    assert "A3 —" not in s7 and "C1 —" not in s7 and "B1 —" not in s7


@pytest.mark.parametrize(
    "so_resumo,frase", [(7, "7 deliberações da CVM só têm resumo"), (1, "1 deliberação da CVM só tem resumo")]
)
def test_dossie_lacunas_cvm_so_com_resumo(tmp_path, so_resumo, frase):
    cvm = {"correspondencias": [], "cobertura": {"com_texto_integral": 10, "so_resumo": so_resumo}}
    s7 = secao(dossie(gravar(tmp_path, saidas={"cvm_alertas": cvm})), 7)
    assert frase in s7 and "sem prova negativa por CNPJ ou domínio" in s7


def test_dossie_lacunas_sem_aviso_de_cvm_quando_tudo_tem_texto(tmp_path):
    assert "só têm resumo" not in secao(dossie(gravar(tmp_path)), 7)


def test_dossie_lacunas_wayback_truncado(tmp_path):
    indice = {**saidas_base()["wayback_indice"], "truncado": True}
    s7 = secao(dossie(gravar(tmp_path, saidas={"wayback_indice": indice})), 7)
    assert "truncad" in s7 and "Wayback" in s7
    assert "truncad" not in secao(dossie(gravar(tmp_path / "outra")), 7)


def test_dossie_item_aberto_diz_o_que_resolve(tmp_path):
    s7 = secao(dossie(gravar(tmp_path, abertas=("P-C",)), forcar=True), 7)
    assert "C2 — não verificado" in s7 and "responder a P-C" in s7


# ---------------------------------------------------------------------------- seções 8 e 9


def test_dossie_primeira_execucao_nao_tem_diff(tmp_path):
    pasta = gravar(tmp_path)
    md_ = dossie(pasta)
    assert "não há execução anterior" in secao(md_, 8).lower()
    assert not (pasta / "diff.md").exists()


def test_dossie_compara_com_a_execucao_anterior_e_grava_o_diff(tmp_path):
    ontem = gravar(tmp_path, agora=AGORA - timedelta(days=1), saidas={"pend_e": pend_e_com(sinal_e("escalada_taxa"))})
    hoje = gravar(
        tmp_path,
        saidas={"pend_e": pend_e_com(sinal_e("escalada_taxa"), sinal_e("atraso_pagamento", "2026-10-02", 1))},
    )
    md_ = dossie(hoje)
    s8 = secao(md_, 8)
    assert "⚠ estágio subiu: E3 → E4" in s8
    assert ontem.name in s8  # diz com qual execução comparou
    diff = (hoje / "diff.md").read_text(encoding="utf-8")
    assert "⚠ estágio subiu: E3 → E4" in diff and ontem.name in diff
    assert "\r" not in diff


def test_dossie_remove_o_diff_velho_quando_nao_ha_anterior(tmp_path):
    pasta = gravar(tmp_path)
    (pasta / "diff.md").write_text("velho", encoding="utf-8")
    dossie(pasta)
    assert not (pasta / "diff.md").exists()


def test_dossie_usa_a_matriz_atual_na_repontuacao_da_anterior(tmp_path):
    ontem = gravar(tmp_path, agora=AGORA - timedelta(days=1))
    # ontem foi pontuada, no passado, com outra matriz: o dossiê de hoje mostra as duas contas
    (ontem / "pontuacao.json").write_text(
        json.dumps(
            {
                "matriz": {"versao": "2026-09-01", "hash": "ab" * 32},
                "eixo1": Eixo1(minimo=2, maximo=3, classe="sem sinal estrutural forte", pode_chegar_a=None,
                               regras_disparadas=[], regras_pendentes=[]).model_dump(),
            }
        ),
        encoding="utf-8",
    )  # fmt: skip
    s8 = secao(dossie(gravar(tmp_path)), 8)
    assert "2026-09-01" in s8 and "2–3 de 34" in s8 and "8–10 de 34" in s8


def test_dossie_anexo_lista_os_artefatos_e_o_comando(tmp_path):
    pasta = gravar(tmp_path)
    s9 = secao(dossie(pasta), 9)
    assert REF_PAGINA in s9 and REF_NOTICIA in s9  # o hash inteiro
    assert "pagina" in s9 and "fonte" in s9 and URL_NOTICIA in s9
    assert "radar verificar exemplo-com-br/2026-10-07_120000" in s9


def test_dossie_anexo_conta_cada_artefato_uma_vez(tmp_path):
    pasta = gravar(tmp_path)
    Custodia(pasta).guardar(PAGINA, "html", "outro", "x")  # o mesmo conteúdo, registrado de novo
    s9 = secao(dossie(pasta), 9)
    assert s9.count(REF_PAGINA) == 1


# ---------------------------------------------------------------------------- pontuacao.json


def test_dossie_grava_a_pontuacao_json(tmp_path):
    pasta = gravar(tmp_path, saidas={"pend_e": pend_e_com(sinal_e("atraso_pagamento"))})
    dossie(pasta)
    dados = json.loads((pasta / "pontuacao.json").read_text(encoding="utf-8"))
    assert set(dados) == {"matriz", "itens", "eixo1", "eixo2", "gerado_em"}
    assert dados["matriz"] == {"versao": MATRIZ.versao, "hash": MATRIZ.hash}
    assert list(dados["itens"]) == list(MATRIZ.itens)
    assert dados["itens"]["A1"]["pontos"] == 3 and dados["itens"]["A1"]["estado"] == "confirmado"
    assert dados["eixo1"]["minimo"] == 8 and dados["eixo1"]["maximo"] == 10 and dados["eixo1"]["classe"] == "provável"
    assert Eixo1.model_validate(dados["eixo1"]).regras_disparadas == ["R1"]
    assert dados["eixo2"]["estagio"] == "E4" and dados["eixo2"]["sinal"]["tipo"] == "atraso_pagamento"
    assert dados["gerado_em"].startswith("20")


# ---------------------------------------------------------------------------- falhas e regravação


def test_dossie_nao_escreve_nada_se_a_montagem_falha(tmp_path, monkeypatch):
    """O template é StrictUndefined: variável que falta levanta, e nenhum arquivo é escrito ou trocado."""
    pasta = gravar(tmp_path)
    gravar(tmp_path, agora=AGORA - timedelta(days=1))  # há anterior: o diff.md também ficaria de fora
    monkeypatch.setattr("radar.dossie._contexto", lambda *a, **k: {"cab": {}})
    with pytest.raises(UndefinedError):
        gerar_dossie(pasta, MATRIZ)
    assert sorted(p.name for p in pasta.iterdir()) == [
        "artefatos", "custodia.log", "estado.json", "evidencias.json", "julgamentos.json"
    ]  # fmt: skip


def test_dossie_custodia_ilegivel_manda_rodar_o_verificar(tmp_path):
    pasta = gravar(tmp_path)
    with (pasta / "custodia.log").open("a", encoding="utf-8", newline="\n") as f:
        f.write("isto nao e json\n")
    md_ = dossie(pasta)  # a última linha do log ilegível não impede o dossiê
    mensagem = "custódia ilegível — rode `radar verificar exemplo-com-br/2026-10-07_120000`"
    assert mensagem in secao(md_, 1) and mensagem in secao(md_, 9)
    assert "sem registros na custódia" not in md_
    assert REF_PAGINA in secao(md_, 9)  # as linhas legíveis seguem no anexo


def test_dossie_sem_estado_json_levanta(tmp_path):
    (tmp_path / "vazia").mkdir()
    with pytest.raises(FileNotFoundError):
        gerar_dossie(tmp_path / "vazia", MATRIZ)


@pytest.mark.parametrize("marcas", ["trecho_nao_conferido", None, 7, [1, {"a": 2}], {"x": "y"}])
def test_dossie_marcas_malformadas_valem_como_sem_marcas(tmp_path, marcas):
    pasta = gravar(tmp_path)
    julgamentos = json.loads((pasta / "julgamentos.json").read_text(encoding="utf-8"))
    julgamentos[0]["marcas"] = marcas
    (pasta / "julgamentos.json").write_text(json.dumps(julgamentos), encoding="utf-8")
    a1 = next(linha for linha in secao(dossie(pasta), 3).splitlines() if linha.startswith("| A1"))
    assert "trecho_nao_conferido" not in a1


def test_dossie_gerado_de_novo_troca_os_arquivos_sem_deixar_lixo(tmp_path):
    pasta = gravar(tmp_path)
    primeiro = dossie(pasta)
    segundo = dossie(pasta)
    assert primeiro == segundo  # nada no dossiê depende da hora de gerar
    assert sorted(p.name for p in pasta.iterdir()) == [
        "artefatos", "custodia.log", "dossie.md", "estado.json", "evidencias.json", "julgamentos.json", "pontuacao.json"
    ]  # fmt: skip


def test_dossie_sinal_cita_a_fonte_e_nao_so_o_hash(tmp_path):
    pasta = gravar(tmp_path, saidas={"pend_e": pend_e_com(sinal_e("atraso_pagamento", "2026-09-20", 0))})
    md_ = dossie(pasta)
    # a evidência do sinal é a página capturada (`sha256:`): o dossiê diz que página é
    assert "`pagina: https://exemplo.com.br/`" in secao(md_, 2) and "`pagina: https://exemplo.com.br/`" in secao(md_, 4)


def test_dossie_conteudo_hostil_do_site_nao_cria_titulo_nem_html(tmp_path):
    """Razão social, nome fantasia, sócio, motivo de erro e nota de item vêm de fora: nenhum vira título, tag ou link."""
    hostil = "ACME\n## 9. Anexo: artefatos e verificação\n<img src=x onerror=alert(1)> [x](http://evil.example)"
    cnpj = {**saidas_base()["cnpj"], "razao_social": hostil, "nome_fantasia": hostil}
    cnpj["socios"] = [{"nome": hostil, "qualificacao": hostil, "entrada": hostil}]
    pasta = gravar(
        tmp_path,
        saidas={"cnpj": cnpj},
        status={"ct": ("erro", hostil), "rdap": ("bloqueado", hostil)},
    )
    md_ = dossie(pasta)
    titulos = [linha for linha in md_.splitlines() if linha.startswith("## ")]
    assert titulos == TITULOS
    # o que veio de fora sai com "\" antes de "<" e de "[": texto, não tag nem link
    assert not re.search(r"(?<!\\)<", md_) and not re.search(r"(?<!\\)\[x\]", md_)
    assert md_.count("\n## 9. Anexo") == 1


# ---------------------------------------------------------------------------- retroativa, anterior ilegível, fonte hostil


def test_dossie_retroativo_nao_compara_com_execucao_atual(tmp_path):
    """Passado contra presente não diz nada ("estágio caiu" porque a retroativa não vê os sinais de hoje)."""
    gravar(tmp_path, agora=AGORA - timedelta(days=1), saidas={"pend_e": pend_e_com(sinal_e("atraso_pagamento"))})
    pasta = gravar(tmp_path, as_of=date(2019, 7, 1))
    (pasta / "diff.md").write_text("velho", encoding="utf-8")
    md_ = dossie(pasta)
    s8 = secao(md_, 8)
    assert "Execução retroativa: sem comparação com execuções atuais." in s8
    assert "Estágio" not in s8 and "estágio" not in s8.replace("Mudanças", "")
    assert not (pasta / "diff.md").exists()


def test_dossie_retroativo_pontua_sem_olhar_a_anterior(tmp_path):
    """A anterior ilegível também não conta: a retroativa nem tenta lê-la."""
    anterior = gravar(tmp_path, agora=AGORA - timedelta(days=1))
    (anterior / "evidencias.json").write_text("{isto não é json", encoding="utf-8")
    pasta = gravar(tmp_path, as_of=date(2019, 7, 1))
    assert "Execução retroativa: sem comparação" in secao(dossie(pasta), 8)


def test_dossie_anterior_ilegivel_nao_impede_o_dossie_novo(tmp_path):
    anterior = gravar(tmp_path, agora=AGORA - timedelta(days=1))
    (anterior / "evidencias.json").write_text("{isto não é json", encoding="utf-8")
    pasta = gravar(tmp_path)
    s8 = secao(dossie(pasta), 8)
    assert "A execução anterior exemplo-com-br/2026-10-06_120000 não pôde ser lida (JSONDecodeError). Sem comparação." in s8
    assert (pasta / "dossie.md").exists() and (pasta / "pontuacao.json").exists()
    assert not (pasta / "diff.md").exists()


def test_dossie_anterior_sem_campos_do_estado_tambem_nao_impede(tmp_path):
    anterior = gravar(tmp_path, agora=AGORA - timedelta(days=1))
    estado = json.loads((anterior / "estado.json").read_text(encoding="utf-8"))
    del estado["nos"]  # estado legível para `execucao_anterior`, mas sem o que `carregar_execucao` precisa
    (anterior / "estado.json").write_text(json.dumps(estado), encoding="utf-8")
    s8 = secao(dossie(gravar(tmp_path)), 8)
    assert "2026-10-06_120000 não pôde ser lida (KeyError)" in s8


def test_dossie_fonte_com_barra_e_barra_vertical_nao_escapa_da_celula(tmp_path):
    """Dentro do trecho de código não há escape: barra invertida e barra vertical juntas, seguidas de `[pwn](u)`,
    têm de sair em percent-encoding, senão o resto da fonte vira link vivo."""
    hostil = "https://evil.example/a" + BS + "|[pwn](http://evil.example)`x"
    a1 = resposta(
        valor={"pct_mes": 5.0, "taxa_diaria": False, "garantido": True},
        evidencias_=[{"fonte": hostil, "trecho": "paga 5% ao mês garantido", "data_fonte": None, "tipo_fonte": "relato"}],
    )
    md_ = dossie(gravar(tmp_path, saidas={"pend_a1": a1}))
    linhas = [linha for linha in secao(md_, 3).splitlines() if linha.startswith("|")]
    assert len({celulas(linha) for linha in linhas}) == 1
    a1_linha = next(linha for linha in linhas if linha.startswith("| A1"))
    assert "`https://evil.example/a%5C%7C[pwn](http://evil.example)%60x`" in a1_linha
    # nem a barra invertida nem a barra vertical sobram dentro da célula da fonte
    fonte = a1_linha.split(" | ")[6]
    assert BS not in fonte and "|" not in fonte


def test_dossie_lacuna_do_item_cita_a_pendencia_que_a_nota_cita(tmp_path):
    """O C3 fica inconclusivo pela P-CNPJ (não pela P-C que o cobre): é a P-CNPJ que precisa de resposta nova."""
    pasta = gravar(tmp_path, saidas={"cnpj": {"cnpj": None, "motivo": "não encontrado"}})
    ctx = carregar_execucao(pasta).ctx
    estado = json.loads((pasta / "estado.json").read_text(encoding="utf-8"))
    pendencia = nova_pendencia("P-CNPJ", ctx, [], "cnpj", MATRIZ).model_dump(mode="json")
    estado["pendencias"]["P-CNPJ"] = {**pendencia, "aberta": False}
    (pasta / "estado.json").write_text(json.dumps(estado), encoding="utf-8")
    julgamentos = json.loads((pasta / "julgamentos.json").read_text(encoding="utf-8"))
    julgamentos.append(
        {
            "id": "P-CNPJ#1", "pendencia": "P-CNPJ", "resposta": resposta("inconclusivo", evidencias_=[])["resposta"],
            "em": "2026-10-07T12:00:00.000+00:00", "substitui": None, "ativa": True,
        }
    )  # fmt: skip
    (pasta / "julgamentos.json").write_text(json.dumps(julgamentos), encoding="utf-8")
    s7 = secao(dossie(pasta), 7)
    c3 = next(linha for linha in s7.splitlines() if linha.startswith("- C3"))
    assert "C3 — inconclusivo" in c3 and "P-CNPJ inconclusiva" in c3
    assert c3.endswith("(para resolver: responder de novo a P-CNPJ com evidência)")
