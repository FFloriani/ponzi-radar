"""Execuções gravadas em disco do jeito que o Motor as grava (`estado.json`, `evidencias.json`, `julgamentos.json`
e a custódia): o dossiê e o diff (Tarefa 15) leem a pasta.

`gravar` parte de uma execução em modo atual, com tudo `feito`: A1 = 3 (5% ao mês), A3 = 2 e C1 = 3, o resto sem
pontos, e troca ou acrescenta saídas e status por nó.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from pathlib import Path

from radar.arquivos import gravar_json_atomico, ler_json
from radar.custodia import Custodia
from radar.modelos import Contexto, Resposta
from radar.pendencias.definicoes import nova_pendencia
from radar.pontuacao import carregar_matriz

MATRIZ = carregar_matriz()
AGORA = datetime(2026, 10, 7, 12, 0, 0)
PETROBRAS = "33000167000101"
URL_SITE = "https://exemplo.com.br/"
URL_NOTICIA = "https://noticia.example/materia"
PAGINA = "<html><body>Rendimento de 5% ao mês garantido pela Exemplo Investimentos</body></html>".encode()
NOTICIA = "<html><body>A Exemplo paga 5% ao mês, diz a reportagem</body></html>".encode()
REF_PAGINA = "sha256:" + hashlib.sha256(PAGINA).hexdigest()
REF_NOTICIA = "sha256:" + hashlib.sha256(NOTICIA).hexdigest()
# o que a custódia sempre tem: a página capturada (a fonte `sha256:`) e a notícia arquivada (a fonte URL)
ARTEFATOS = ((PAGINA, "html", "pagina", URL_SITE), (NOTICIA, "html", "fonte", URL_NOTICIA))

NOS = (
    "alvo", "captura", "destino", "rdap", "dns", "ct", "wayback_indice", "wayback_snapshot", "extracao", "cnpj",
    "registros", "cvm_sancionador", "cvm_alertas", "pend_a1", "pend_a2", "pend_a3", "pend_b", "pend_c", "pend_c4",
    "pend_d1", "pend_d4", "pend_e",
)  # fmt: skip
PENDENCIA_DO_NO = {
    "pend_a1": "P-A1", "pend_a2": "P-A2", "pend_a3": "P-A3", "pend_b": "P-B", "pend_c": "P-C", "pend_c4": "P-C4",
    "pend_d1": "P-D1", "pend_d4": "P-D4", "pend_e": "P-E",
}  # fmt: skip
NO_DA_PENDENCIA = {pendencia: no for no, pendencia in PENDENCIA_DO_NO.items()}
_STATUS_PADRAO = {
    "wayback_snapshot": ("pulado", "captura ok"),
    "pend_a2": ("pulado", "sem histórico de rentabilidade"),
}


def evidencias(*, data_fonte: str | None = None) -> list[dict]:
    """Duas evidências citáveis: a página capturada (`sha256:`) e a notícia (URL)."""
    return [
        {"fonte": REF_PAGINA, "trecho": "Rendimento de 5% ao mês garantido", "data_fonte": None, "tipo_fonte": "operador"},
        {"fonte": URL_NOTICIA, "trecho": "paga 5% ao mês", "data_fonte": data_fonte, "tipo_fonte": "imprensa"},
    ]  # fmt: skip


def resposta(status: str = "confirmado", valor: dict | None = None, evidencias_: list[dict] | None = None) -> dict:
    """A saída de um nó `pend_*` com essa resposta (como o motor grava)."""
    if evidencias_ is None:
        evidencias_ = evidencias() if status in ("confirmado", "corrigido") else []
    modelo = Resposta(
        status=status,
        valor=valor or {},
        evidencias=evidencias_,
        onde_procurou=["site e imprensa"] if status == "nao_encontrado" else [],
    )
    return {"resposta": modelo.model_dump(mode="json")}


def saidas_base() -> dict[str, dict]:
    """As saídas de todos os nós `feito`: empresa e domínio antigos, CNAE da seção K, sem registro, sem alerta."""
    return {
        "alvo": {"dominio": "exemplo.com.br", "slug": "exemplo-com-br", "url_inicial": URL_SITE},
        # sem redirect para outro domínio: os coletores analisaram o próprio alvo
        "destino": {"dominio": "exemplo.com.br", "redirecionado_de": None, "url_destino": None},
        "rdap": {
            "registro": "2015-03-02", "expiracao": "2027-03-02", "registrador": "Registro.br",
            "cnpj_titular": PETROBRAS, "vazamento_temporal": [],
        },
        "dns": {
            "A": ["203.0.113.7"], "AAAA": [], "MX": ["10 mail.exemplo.com.br."], "NS": ["ns1.exemplo.com.br."],
            "TXT": [], "nxdomain": False,
        },
        "ct": {"primeiro_certificado": "2019-05-20", "total": 4, "sans": ["exemplo.com.br", "www.exemplo.com.br"]},
        "wayback_indice": {
            "primeiro": "2016-01-12", "ultimo": "2026-09-30", "total": 120,
            "por_mes": {"2016-01": 3, "2026-09": 7}, "truncado": False,
        },
        "captura": {
            "paginas": [{"url": URL_SITE, "status": 200, "html": REF_PAGINA}],
            "terceiros": ["googletagmanager.com"], "bloqueada": False, "falhas": [],
        },
        "extracao": {"candidatos": [], "fonte": "captura", "truncado": False},
        "cnpj": {
            "cnpj": PETROBRAS, "razao_social": "EXEMPLO INVESTIMENTOS LTDA", "nome_fantasia": "Exemplo Invest",
            "abertura": "2014-01-10", "cnae": 6619302, "cnae_descricao": "Corretoras de câmbio",
            "capital_social": 1000.0, "situacao": "ATIVA",
            "socios": [{"nome": "MARIA DA SILVA", "qualificacao": "Sócio-Administrador", "entrada": "2014-01-10"}],
            "fonte": "brasilapi", "vazamento_temporal": [],
        },
        "registros": {
            "cvm": [], "bcb": [], "bcb_dominio": [], "registrado": False, "motivo": None, "vazamento_temporal": [],
        },
        "cvm_sancionador": {"processos": [], "motivo": None},
        "cvm_alertas": {"correspondencias": [], "cobertura": {"com_texto_integral": 10, "so_resumo": 0}},
        "pend_a1": resposta(valor={"pct_mes": 5.0, "taxa_diaria": False, "garantido": True}),
        "pend_a3": resposta(valor={"origem_verificavel": False, "custodiante_independente": False}),
        "pend_b": resposta(
            valor={"indicacao": "nenhuma", "token_proprio": False, "carencia_com_multa": False, "taxa_para_sacar": False}
        ),
        "pend_c": resposta(
            valor={"contrato_atipico": False, "tipo_contrato": None, "conta_pf_ou_terceiro": False, "offshore_alegado": False}
        ),
        "pend_c4": resposta(valor={"alerta_vigente": False, "alertas": []}),
        "pend_d1": resposta(valor={"historico_fraude": False, "pessoas": []}),
        "pend_d4": resposta(valor={"credibilidade_emprestada": False, "tipos": []}),
        "pend_e": resposta("nao_encontrado"),
    }  # fmt: skip


def sinal_e(tipo: str, data: str | None = "2026-09-20", evidencia: int = 0) -> dict:
    return {"tipo": tipo, "data": data, "evidencia": evidencia}


def pend_e_com(*sinais: dict, modificadores: list[dict] | None = None) -> dict:
    """A saída do `pend_e` com esses sinais (cada um aponta para uma das duas evidências padrão)."""
    return resposta(valor={"sinais": list(sinais), "modificadores": modificadores or []})


def gravar(
    casos: Path,
    *,
    agora: datetime = AGORA,
    as_of: date | None = None,
    saidas: dict | None = None,
    status: dict | None = None,
    abertas: tuple[str, ...] = (),
    marcas: dict[str, list[str]] | None = None,
    slug: str = "exemplo-com-br",
    alvo: str = "exemplo.com.br",
) -> Path:
    """Grava a execução em `casos/<slug>/<AAAA-MM-DD_HHMMSS>` e devolve a pasta.

    - `alvo`: o `contexto.alvo` (e a saída do nó `alvo` e do `destino`, se `saidas` não os trouxer); a `url_inicial`
      é `https://<alvo>/`;

    - `saidas`: `{nó: saída}` troca ou acrescenta a saída do nó (que fica `feito`);
    - `status`: `{nó: "erro"}` ou `{nó: ("erro", motivo)}` tira o nó do `feito` e apaga a saída dele;
    - `abertas`: ids de pendência (`"P-A1"`) sem resposta: o nó dono fica `aguardando` e a pendência `aberta`;
    - `marcas`: `{id da pendência: [marcas]}` gravadas no julgamento ativo, como a T16 vai gravar.
    """
    carimbo = agora.strftime("%Y-%m-%d_%H%M%S")
    pasta = Path(casos) / slug / carimbo
    pasta.mkdir(parents=True)
    url_inicial = URL_SITE if alvo == "exemplo.com.br" else f"https://{alvo}/"
    ctx = Contexto(
        alvo=alvo, slug=slug, url_inicial=url_inicial, as_of=as_of or agora.date(), data_execucao=agora,
        modo_contato="captura", modo_cego=False, run_id=f"{slug}/{carimbo}", pasta=pasta,
    )  # fmt: skip

    base = saidas_base()
    base["alvo"] = {**base["alvo"], "dominio": alvo, "slug": slug, "url_inicial": url_inicial}
    base["destino"] = {**base["destino"], "dominio": alvo}
    todas = {**base, **(saidas or {})}
    pedidos = {**{n: s for n, s in _STATUS_PADRAO.items() if n not in (saidas or {})}, **(status or {})}
    for pendencia in abertas:
        pedidos[NO_DA_PENDENCIA[pendencia]] = "aguardando"
    estados = {no: {"status": "feito", "motivo": None} for no in NOS}
    for no, pedido in pedidos.items():
        st, motivo = pedido if isinstance(pedido, tuple) else (pedido, None)
        if motivo is None and st in ("erro", "bloqueado", "pulado"):
            motivo = f"motivo de {st}"
        estados[no] = {"status": st, "motivo": motivo}
        todas.pop(no, None)

    pendencias, julgamentos = {}, []
    for no, pid in PENDENCIA_DO_NO.items():
        if estados[no]["status"] not in ("feito", "aguardando"):
            continue  # o nó nunca chegou a pedir a pendência
        pendencia = nova_pendencia(pid, ctx, [], no, MATRIZ).model_dump(mode="json")
        pendencias[pid] = {**pendencia, "aberta": estados[no]["status"] == "aguardando"}
        if estados[no]["status"] == "feito":
            julgamento = {
                "id": f"{pid}#1", "pendencia": pid, "resposta": todas[no]["resposta"],
                "em": "2026-10-07T12:00:00.000+00:00", "substitui": None, "ativa": True,
            }  # fmt: skip
            if marcas and pid in marcas:
                julgamento["marcas"] = marcas[pid]
            julgamentos.append(julgamento)

    custodia = Custodia(pasta)
    for dados, ext, tipo, origem in ARTEFATOS:
        custodia.guardar(dados, ext, tipo, origem)
    gravar_json_atomico(
        pasta / "estado.json",
        {"contexto": ctx.model_dump(mode="json"), "nos": estados, "pendencias": pendencias},
    )
    gravar_json_atomico(pasta / "evidencias.json", {no: todas[no] for no in NOS if no in todas})
    gravar_json_atomico(pasta / "julgamentos.json", julgamentos)
    return pasta


def antes_da_t1(pasta: Path) -> Path:
    """Deixa a execução gravada como as de antes da T1 das melhorias do aceite: sem o nó `destino` no `estado.json` nem
    no `evidencias.json`, e a saída da captura sem `destino`, `redirect_ignorado` e `saltos`."""
    estado = ler_json(pasta / "estado.json")
    estado["nos"].pop("destino", None)
    gravar_json_atomico(pasta / "estado.json", estado)
    evidencias = ler_json(pasta / "evidencias.json")
    evidencias.pop("destino", None)
    for chave in ("destino", "redirect_ignorado", "saltos"):
        (evidencias.get("captura") or {}).pop(chave, None)
    gravar_json_atomico(pasta / "evidencias.json", evidencias)
    return pasta
