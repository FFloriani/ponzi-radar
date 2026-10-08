"""Índices de registro, sanções e alertas (CVM e BCB), baixados uma vez e guardados em disco com validade.

Cada índice é um arquivo `pasta/<nome>.json` com `{"gerado_em": ISO, "itens": [...]}`, refeito quando passa de
`ttl_horas`. Se a renovação falha e há um índice anterior completo, ele volta como `IndiceVencido` (a lista, com
`vencido_desde`): uma queda da CVM por um dia não derruba C1, C4 e a P-C4 de toda análise. Os nós registram isso na
saída (`indices_vencidos`) e o dossiê o mostra nas lacunas. Sem índice anterior, a falha vira `ErroNo` e o nó que
pediu cai em erro. Os pedidos passam por `Rede` com `usar_cache=False`, porque o cache em memória dela não expira e
devolveria o arquivo de horas atrás.

Fontes (conferidas em 07/10/2026):

- CVM, dados abertos: ZIPs com CSV `;` em latin-1. Cadastros de intermediários, crowdfunding, administradores
  de carteira (`cad_adm_cart_pj.csv`) e consultores (`cad_consultor_vlmob_pj.csv`); o processo sancionador vem
  em dois CSV (`processo_sancionador.csv` e `processo_sancionador_acusado.csv`), ligados pelo NUP. As datas vêm
  em ISO; `DD/MM/AAAA` também é aceito. O CSV do crowdfunding não tem `DT_CANCEL`: quem está "Cancelado" perde o
  registro em `DT_INI_SIT`, e quem está "Em Análise" ou "Registro Não Concedido" não tem `DT_REG`.
- BCB, Olinda `Instituicoes_em_funcionamento`: o campo `CNPJ` é a raiz de 8 caracteres. `DominiosVerificados`
  traz uma linha por instituição, e metade delas está "Sem domínio verificado" (`DOMINIO` vazio).
- Deliberações de "Atuação Irregular" da CVM (stop orders): a busca em `conteudo.cvm.gov.br/legislacao` pagina
  por `resultadoLegislacao.jsp`, que só responde a quem já passou pela página de partida (o cookie `JSESSIONID`
  fica na `Rede`; sem ele a resposta vem em branco). O `lastName` vai com as aspas, percent-encoded duas vezes,
  e o `Páginas n/N` da resposta diz onde parar. Cada deliberação tem um invólucro `deliNNN.html`: o bloco
  `<article class="contentTextoGeral">` tem o resumo e o carimbo da data (`Tue Nov 25 18:00:00 BRST 2025`). Só as
  mais recentes (de 2024 em diante) trazem o texto integral, com CNPJ e domínios, num `anexos/.../deliNNN.htm`
  ligado no invólucro; nas outras o texto integral só existe em PDF (`.../anexos/0NNN/deliNNN.pdf`, também ligado
  no invólucro), que é lido com `pypdf`. `.doc` e `.docx` não são lidos. Sem o texto integral a deliberação fica
  só com o resumo (`integral=False`), e quem consulta o índice precisa dizer isso: "nenhuma correspondência" numa
  deliberação só com o resumo não prova nada sobre o CNPJ ou o domínio.

Erros ao montar as deliberações: o 404 de uma página (do invólucro, do `.htm` ou do PDF) é pulado. O erro no anexo
(`.htm` ou PDF) de uma deliberação antiga (mais de 180 dias, a mesma janela de releitura) a deixa só com o resumo e
segue: um anexo antigo que nunca responde não trava a renovação. Qualquer outro erro (no invólucro, no anexo de uma
deliberação recente ou sem data), o invólucro sem o bloco do texto (layout novo) e a busca que corta a lista (página
sem resultado antes do total) levantam `ErroNo`, depois de guardar o que já foi baixado, para uma deliberação nova
nunca sumir em silêncio.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import re
import zipfile
import zlib
from collections.abc import Awaitable, Callable, Iterable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal, TypeVar
from urllib.parse import urljoin

from pydantic import BaseModel, ValidationError

from radar.arquivos import gravar_json_atomico, ler_json
from radar.cnpj_util import normalizar_cnpj
from radar.modelos import ErroNo
from radar.rede import ErroRede, Rede, RespostaRede
from radar.texto import normalizar, texto_de_html, texto_de_pdf

_log = logging.getLogger(__name__)

URL_CVM = "https://dados.cvm.gov.br/dados/"
# (valor de `cadastro`, caminho do ZIP em URL_CVM, CSV de pessoas jurídicas dentro do ZIP)
_CADASTROS = (
    ("intermed", "INTERMED/CAD/DADOS/cad_intermed.zip", "cad_intermed.csv"),
    ("crowdfunding", "CROWDFUNDING/CAD/DADOS/cad_crowdfunding.zip", "cad_crowdfunding.csv"),
    ("adm_cart", "ADM_CART/CAD/DADOS/cad_adm_cart.zip", "cad_adm_cart_pj.csv"),
    ("consultor", "CONSULTOR_VLMOB/CAD/DADOS/cad_consultor_vlmob.zip", "cad_consultor_vlmob_pj.csv"),
)
_SANCIONADOR = "PROCESSO/SANCIONADOR/DADOS/processo_sancionador.zip"
CONJUNTOS_BCB = ("SedesBancoComMultCE", "SedesSociedades", "SedesCooperativas", "SedesConsorcios")
URL_OLINDA = (
    "https://olinda.bcb.gov.br/olinda/servico/Instituicoes_em_funcionamento/versao/v1/odata/{conjunto}"
    "?$format=json&$top=100000"
)
# a busca de "Atuação Irregular" nas Deliberações, como a spec (seção 13) a registra
URL_DELIBERACOES_PARTIDA = (
    "https://conteudo.cvm.gov.br/legislacao/index.html?numero=&lastNameShow=%22Atua%C3%A7%C3%A3o+Irregular%22"
    "&lastName=%2522Atua%25C3%25A7%25C3%25A3o%2520Irregular%2522&buscado=true&pasta=deliberacoes&filtro=todos"
    "&contCategoriasCheck=1&vimDaCategoria=%2Flegislacao%2Fdeliberacoes%2F&tags="
)
URL_DELIBERACOES_PAGINAS = (
    "https://conteudo.cvm.gov.br/system/modules/br.com.squadra.legislacao/elements/resultadoLegislacao.jsp"
)
# o formulário da página manda isto por POST; o GET com os mesmos campos responde igual. `lastName` é o termo
# `"Atuação Irregular"` percent-encoded: o `Rede` o codifica de novo, que é o que o JSP espera
_PARAMS_BUSCA = {
    "lastName": "%22Atua%C3%A7%C3%A3o%20Irregular%22",
    "numero": "",
    "filtro": "todos",
    "dataInicio": "",
    "dataFim": "",
    "buscado": "true",
    "contCategoriasCheck": "1",
    "itensPagina": "10",
    "ordenar": "recentes",
    "dataInicioBound": "",
    "dataFimBound": "",
    "listaBuscaAside": "",
    "tipos": "",
    "tags": "",
}
_MAX_PAGINAS = 300  # a busca tem 28; um total muito maior é a página mudando, não mais deliberações

_PAGINAS = re.compile(r"P[áa]ginas\s+(\d+)\s*/\s*(\d+)")
_LINK_DELIBERACAO = re.compile(r"""href\s*=\s*["']([^"']*/deliberacoes/deli\d+/deli(\d+)\.html)["']""", re.IGNORECASE)
_BLOCO_DO_TEXTO = re.compile(r"<article\b[^>]*\bcontentTextoGeral\b[^>]*>(.*?)</article>", re.IGNORECASE | re.DOTALL)
_LINK_DO_DOCUMENTO = re.compile(r"""<a\b[^>]*\bhref\s*=\s*["']([^"']*/anexos/[^"']*\.html?)["']""", re.IGNORECASE)
_LINK_DO_PDF = re.compile(r"""<a\b[^>]*\bhref\s*=\s*["']([^"']*/anexos/[^"']*\.pdf)["']""", re.IGNORECASE)
# um anexo pode ser publicado depois do invólucro: o que está só com o resumo é visto de novo por este prazo
_DIAS_PARA_RELER = 180
_MESES_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_CARIMBO = re.compile(
    r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) (" + "|".join(_MESES_EN) + r") (\d{1,2}) \d{2}:\d{2}:\d{2} [A-Z]{2,5} (\d{4})\b"
)
_MESES_PT = ("janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
             "novembro", "dezembro")
# o "ç" de março é opcional no texto; o índice do mês vem de `normalizar` (sem acento, minúsculo)
_DATA_POR_EXTENSO = re.compile(
    r"\b(\d{1,2})\s*[º°]?\s+de\s+(" + "|".join(m.replace("c", "[cç]") if m == "marco" else m for m in _MESES_PT) +
    r")\s+de\s+(\d{4})\b",
    re.IGNORECASE,
)
_DATA_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_DATA_BR = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
_RAIZ = re.compile(r"[0-9A-Z]{8}")

_T = TypeVar("_T", bound=BaseModel)


class RegistroCVM(BaseModel):
    cadastro: Literal["intermed", "crowdfunding", "adm_cart", "consultor"]
    cnpj: str
    denominacao: str
    nome_comercial: str | None = None
    situacao: str
    dt_reg: date | None = None
    dt_cancel: date | None = None


class InstituicaoBCB(BaseModel):
    conjunto: str
    raiz_cnpj: str
    nome: str
    segmento: str | None = None


class DominioBCB(BaseModel):
    dominio: str
    instituicao: str
    raiz_cnpj: str


class ProcessoCVM(BaseModel):
    """Uma linha por acusado: o processo (NUP, objeto, abertura, fase) e a situação desse acusado."""

    nup: str
    objeto: str
    data_abertura: date | None = None
    fase: str | None = None
    acusado: str
    situacao: str | None = None


class Deliberacao(BaseModel):
    """`url` é a do invólucro `deliNNN.html`; `texto` junta o resumo dele e, se houver, o texto integral.

    `integral` diz se o texto integral (do `.htm` ou do PDF do anexo) foi lido. Sem ele só há o resumo, que
    quase nunca traz CNPJ nem domínio. O campo é obrigatório: um cache de antes dele não vale e é refeito.
    """

    numero: int
    data: date | None = None
    url: str
    texto: str
    integral: bool


class IndiceVencido(list):
    """Os itens do índice anterior, devolvidos porque a renovação falhou: `vencido_desde` é quando ele venceu
    (`gerado_em` + `ttl_horas`)."""

    def __init__(self, itens: Iterable, vencido_desde: datetime) -> None:
        super().__init__(itens)
        self.vencido_desde = vencido_desde


def vencido_desde(itens: object) -> datetime | None:
    """Quando venceu o índice devolvido por `Indices`, se ele é o anterior a uma renovação que falhou; senão `None`."""
    return itens.vencido_desde if isinstance(itens, IndiceVencido) else None


def _texto(valor: object) -> str:
    return str(valor or "").strip()


def _data(valor: object) -> date | None:
    """`AAAA-MM-DD` (com ou sem hora) ou `DD/MM/AAAA`; vazio, outro formato ou dia que não existe viram `None`."""
    texto = _texto(valor)[:10]
    try:
        if achado := _DATA_ISO.fullmatch(texto):
            return date(int(achado[1]), int(achado[2]), int(achado[3]))
        if achado := _DATA_BR.fullmatch(texto):
            return date(int(achado[3]), int(achado[2]), int(achado[1]))
    except ValueError:
        pass
    return None


def _abrir_zip(dados: bytes, rotulo: str) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(io.BytesIO(dados))
    except zipfile.BadZipFile as erro:
        raise ErroNo(f"{rotulo}: o arquivo baixado não é um ZIP ({erro})", permanente=True) from erro


def _ler_csv(
    zf: zipfile.ZipFile, arquivo: str, obrigatorias: Iterable[str], rotulo: str
) -> list[dict[str, str]]:
    """As linhas do CSV `arquivo` do ZIP (`;`, latin-1) como dicionários pelo nome da coluna."""
    try:
        with zf.open(arquivo) as f:
            leitor = csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";")
            faltam = [c for c in obrigatorias if c not in (leitor.fieldnames or ())]
            if faltam:
                raise ErroNo(f"{rotulo}: {arquivo} sem a coluna {', '.join(faltam)}", permanente=True)
            return list(leitor)
    except KeyError as erro:
        raise ErroNo(f"{rotulo}: o ZIP não tem {arquivo}", permanente=True) from erro
    except (csv.Error, zipfile.BadZipFile, zlib.error) as erro:
        raise ErroNo(f"{rotulo}: {arquivo} ilegível ({erro})", permanente=True) from erro


def _registros_cvm(cadastro: str, linhas: list[dict[str, str]]) -> list[RegistroCVM]:
    registros = []
    for linha in linhas:
        cnpj = normalizar_cnpj(_texto(linha["CNPJ"]))
        if cnpj is None:  # o intermed tem um CNPJ-curinga (00.999.999/9999-99), o do custodiante de títulos públicos
            continue
        situacao = _texto(linha.get("SIT"))
        dt_cancel = _data(linha.get("DT_CANCEL"))
        if dt_cancel is None and normalizar(situacao).startswith("cancelad"):
            dt_cancel = _data(linha.get("DT_INI_SIT"))  # o crowdfunding não tem DT_CANCEL
        comercial = _texto(linha.get("DENOM_COMERC"))
        registros.append(
            RegistroCVM(
                cadastro=cadastro,
                cnpj=cnpj,
                denominacao=_texto(linha["DENOM_SOCIAL"]),
                nome_comercial=comercial if comercial.strip("-–— ") else None,
                situacao=situacao,
                dt_reg=_data(linha["DT_REG"]),
                dt_cancel=dt_cancel,
            )
        )
    return registros


def _linhas_olinda(resposta: RespostaRede, rotulo: str) -> list[dict]:
    try:
        dados = resposta.json()
    except ValueError as erro:
        raise ErroNo(f"{rotulo}: {resposta.url} devolveu corpo que não é JSON ({erro})", permanente=True) from erro
    valor = dados.get("value") if isinstance(dados, dict) else None
    if not isinstance(valor, list):
        raise ErroNo(f"{rotulo}: {resposta.url} sem a lista `value` do OData", permanente=True)
    return [linha for linha in valor if isinstance(linha, dict)]


def _raiz(valor: object) -> str | None:
    texto = _texto(valor).upper()
    return texto if _RAIZ.fullmatch(texto) else None


def _bloco_do_texto(html: str) -> str | None:
    achado = _BLOCO_DO_TEXTO.search(html)
    return achado[1] if achado else None


def _data_por_extenso(texto: str) -> date | None:
    """A primeira data "25 de novembro de 2025" do texto que existe no calendário."""
    for achado in _DATA_POR_EXTENSO.finditer(texto):
        try:
            return date(int(achado[3]), _MESES_PT.index(normalizar(achado[2])) + 1, int(achado[1]))
        except ValueError:  # dia que não existe: segue para a próxima data do texto
            continue
    return None


class Indices:
    """Os índices da CVM e do BCB, com cache em `pasta` e validade de `ttl_horas`.

    As falhas viram `ErroNo` (`permanente` vem do `ErroRede`; arquivo fora do formato esperado é permanente).
    Chamadas simultâneas ao mesmo índice baixam uma vez só.
    """

    def __init__(
        self, pasta: Path, rede: Rede, ttl_horas: int, agora: Callable[[], datetime] = datetime.now
    ) -> None:
        self._pasta = Path(pasta)
        self._rede = rede
        self._ttl = timedelta(hours=ttl_horas)
        self._agora = agora
        self._travas: dict[str, asyncio.Lock] = {}

    # --- índices -----------------------------------------------------------------------------

    async def cadastros_cvm(self) -> list[RegistroCVM]:
        return await self._indice("cadastros_cvm", RegistroCVM, self._baixar_cadastros)

    async def instituicoes_bcb(self) -> list[InstituicaoBCB]:
        return await self._indice("instituicoes_bcb", InstituicaoBCB, self._baixar_instituicoes)

    async def dominios_bcb(self) -> list[DominioBCB]:
        return await self._indice("dominios_bcb", DominioBCB, self._baixar_dominios)

    async def sancionador(self) -> list[ProcessoCVM]:
        return await self._indice("sancionador", ProcessoCVM, self._baixar_sancionador)

    async def deliberacoes(self) -> list[Deliberacao]:
        """Todas as deliberações de "Atuação Irregular", da mais nova para a mais antiga.

        Incremental: a busca é refeita inteira quando o índice vence, mas só os números que ainda não estão no
        disco têm a página baixada. Se uma página falha no meio, o que já veio fica guardado (sem `gerado_em`,
        isto é, vencido) e a próxima chamada continua dali.
        """
        async with self._trava("deliberacoes"):
            cache = self._ler_cache("deliberacoes", Deliberacao)
            if cache is not None and self._vigente(cache[0]):
                return cache[1]
            gerado_antes, anteriores = cache if cache is not None else (None, [])
            try:
                itens = await self._atualizar_deliberacoes({d.numero: d for d in anteriores}, gerado_antes)
            except ErroNo as erro:
                if gerado_antes is None:  # nunca houve índice completo: não há o que devolver
                    raise
                # o que já veio nesta tentativa ficou no disco, com o `gerado_em` anterior
                atual = self._ler_cache("deliberacoes", Deliberacao)
                return self._vencido("deliberacoes", atual[1] if atual else anteriores, gerado_antes, erro)
            self._gravar("deliberacoes", itens, self._agora())
            return itens

    # --- cache -------------------------------------------------------------------------------

    def _trava(self, nome: str) -> asyncio.Lock:
        return self._travas.setdefault(nome, asyncio.Lock())

    def _ler_cache(self, nome: str, modelo: type[_T]) -> tuple[datetime | None, list[_T]] | None:
        """`(gerado_em, itens)` do arquivo, ou `None` se ele não existe, não é JSON ou não tem o formato esperado."""
        try:
            bruto = ler_json(self._pasta / f"{nome}.json")
        except (ValueError, OSError):
            return None
        if not isinstance(bruto, dict) or not isinstance(bruto.get("itens"), list):
            return None
        try:
            itens = [modelo.model_validate(item) for item in bruto["itens"]]
        except ValidationError:
            return None
        gerado = None
        if isinstance(bruto.get("gerado_em"), str):
            try:
                gerado = datetime.fromisoformat(bruto["gerado_em"])
            except ValueError:
                pass
        return gerado, itens

    def _vigente(self, gerado: datetime | None) -> bool:
        """Dentro da validade. Um `gerado_em` à frente do relógio (relógio que andou para trás) não vale."""
        if gerado is None:
            return False
        try:
            idade = self._agora() - gerado
        except TypeError:  # um relógio com fuso e o outro sem
            return False
        return timedelta(0) <= idade <= self._ttl

    def _vencido(self, nome: str, itens: list[_T], gerado_em: datetime, erro: ErroNo) -> IndiceVencido:
        desde = gerado_em + self._ttl
        _log.warning("índice %s: a renovação falhou (%s); vale o anterior, vencido desde %s", nome, erro.mensagem,
                     desde.isoformat())  # fmt: skip
        return IndiceVencido(itens, desde)

    def _gravar(self, nome: str, itens: list[_T], gerado_em: datetime | None) -> None:
        """`gerado_em=None` marca o índice como incompleto: a próxima leitura o trata como vencido."""
        self._pasta.mkdir(parents=True, exist_ok=True)
        gravar_json_atomico(
            self._pasta / f"{nome}.json",
            {
                "gerado_em": gerado_em.isoformat() if gerado_em is not None else None,
                "itens": [item.model_dump(mode="json") for item in itens],
            },
        )

    async def _indice(self, nome: str, modelo: type[_T], baixar: Callable[[], Awaitable[list[_T]]]) -> list[_T]:
        async with self._trava(nome):
            cache = self._ler_cache(nome, modelo)
            if cache is not None and self._vigente(cache[0]):
                return cache[1]
            try:
                itens = await baixar()
            except ErroNo as erro:
                if cache is None or cache[0] is None:
                    raise
                return self._vencido(nome, cache[1], cache[0], erro)
            self._gravar(nome, itens, self._agora())
            return itens

    # --- rede --------------------------------------------------------------------------------

    async def _get(self, url: str, rotulo: str, params: dict | None = None) -> RespostaRede:
        try:
            return await self._rede.get(url, tipo="api", params=params, usar_cache=False)
        except ErroRede as erro:
            raise ErroNo(f"{rotulo}: {erro}", permanente=erro.permanente) from erro

    async def _get_ou_none(self, url: str, rotulo: str) -> RespostaRede | None:
        """Como `_get`, mas a página que não existe (404) devolve `None`. Qualquer outro erro continua `ErroNo`."""
        try:
            return await self._get(url, rotulo)
        except ErroNo as erro:
            if isinstance(erro.__cause__, ErroRede) and erro.__cause__.status == 404:
                return None
            raise

    # --- CVM: cadastros e processo sancionador -------------------------------------------------

    async def _baixar_cadastros(self) -> list[RegistroCVM]:
        registros: list[RegistroCVM] = []
        for cadastro, caminho, arquivo in _CADASTROS:
            resposta = await self._get(URL_CVM + caminho, "cadastros_cvm")
            linhas = _ler_csv(
                _abrir_zip(resposta.conteudo, "cadastros_cvm"),
                arquivo,
                ("CNPJ", "DENOM_SOCIAL", "SIT", "DT_REG"),
                "cadastros_cvm",
            )
            registros += _registros_cvm(cadastro, linhas)
        return registros

    async def _baixar_sancionador(self) -> list[ProcessoCVM]:
        resposta = await self._get(URL_CVM + _SANCIONADOR, "sancionador")
        zf = _abrir_zip(resposta.conteudo, "sancionador")
        processos = {
            _texto(linha["NUP"]): linha
            for linha in _ler_csv(
                zf, "processo_sancionador.csv", ("NUP", "Objeto", "Data_Abertura", "Fase_Atual"), "sancionador"
            )
        }
        acusados = _ler_csv(
            zf, "processo_sancionador_acusado.csv", ("NUP", "Nome_Acusado", "Situacao"), "sancionador"
        )
        lista = []
        for acusado in acusados:
            nup = _texto(acusado["NUP"])
            processo = processos.get(nup)
            nome = _texto(acusado["Nome_Acusado"])
            if processo is None or not nome:  # sem o processo não há data de abertura para filtrar
                continue
            lista.append(
                ProcessoCVM(
                    nup=nup,
                    objeto=_texto(processo["Objeto"]) or _texto(processo.get("Ementa")),
                    data_abertura=_data(processo["Data_Abertura"]),
                    fase=_texto(processo["Fase_Atual"]) or None,
                    acusado=nome,
                    situacao=_texto(acusado["Situacao"]) or None,
                )
            )
        return lista

    # --- BCB: Olinda ---------------------------------------------------------------------------

    async def _baixar_instituicoes(self) -> list[InstituicaoBCB]:
        instituicoes = []
        for conjunto in CONJUNTOS_BCB:
            resposta = await self._get(URL_OLINDA.format(conjunto=conjunto), "instituicoes_bcb")
            for linha in _linhas_olinda(resposta, "instituicoes_bcb"):
                if (raiz := _raiz(linha.get("CNPJ"))) is None:
                    continue
                instituicoes.append(
                    InstituicaoBCB(
                        conjunto=conjunto,
                        raiz_cnpj=raiz,
                        nome=_texto(linha.get("NOME_INSTITUICAO")),
                        segmento=_texto(linha.get("SEGMENTO")) or None,
                    )
                )
        return instituicoes

    async def _baixar_dominios(self) -> list[DominioBCB]:
        resposta = await self._get(URL_OLINDA.format(conjunto="DominiosVerificados"), "dominios_bcb")
        dominios: dict[tuple[str, str], DominioBCB] = {}
        for linha in _linhas_olinda(resposta, "dominios_bcb"):
            dominio = _texto(linha.get("DOMINIO")).lower().strip(".")
            raiz = _raiz(linha.get("CNPJ"))
            if dominio and raiz:  # metade das linhas é "Sem domínio verificado": DOMINIO vazio
                dominios.setdefault(
                    (dominio, raiz),
                    DominioBCB(dominio=dominio, instituicao=_texto(linha.get("INSTITUICAO_FINANCEIRA")), raiz_cnpj=raiz),
                )
        return list(dominios.values())

    # --- CVM: deliberações de "Atuação Irregular" -----------------------------------------------

    async def _atualizar_deliberacoes(
        self, conhecidas: dict[int, Deliberacao], gerado_antes: datetime | None
    ) -> list[Deliberacao]:
        achadas = await self._listar_deliberacoes()
        guardadas = dict(conhecidas)
        desde = self._agora().date() - timedelta(days=_DIAS_PARA_RELER)
        try:
            for numero, url in achadas.items():
                anterior = guardadas.get(numero)
                # o que já está no disco só volta se tem só o resumo e é recente (ou de data desconhecida)
                if anterior is not None and (anterior.integral or (anterior.data is not None and anterior.data < desde)):
                    continue
                if (deliberacao := await self._baixar_deliberacao(numero, url)) is not None:
                    guardadas[numero] = deliberacao
        except BaseException:
            self._gravar("deliberacoes", _por_numero(guardadas), gerado_antes)
            raise
        if not guardadas:
            raise ErroNo("deliberacoes: nenhuma página de deliberação legível", permanente=True)
        return _por_numero(guardadas)

    async def _listar_deliberacoes(self) -> dict[int, str]:
        """`{número: URL do invólucro}` de todas as páginas da busca, da mais nova para a mais antiga."""
        await self._get(URL_DELIBERACOES_PARTIDA, "deliberacoes")  # abre a sessão que o JSP exige
        achadas: dict[int, str] = {}
        pagina, total = 1, 1
        while pagina <= total:
            resposta = await self._get(
                URL_DELIBERACOES_PAGINAS, "deliberacoes", {"searchPage": str(pagina), **_PARAMS_BUSCA}
            )
            html = resposta.texto
            marcador = _PAGINAS.search(html)
            if marcador is None:
                # sem sessão, com a lista cortada ("Nenhum resultado" antes da última página) ou com a página mudada:
                # uma lista parcial nunca vira índice
                raise ErroNo(
                    f"deliberacoes: a busca não devolveu a página {pagina} de {total} "
                    "(sessão perdida, lista cortada ou página mudou)",
                    permanente=False,
                )
            total = int(marcador[2])
            if total > _MAX_PAGINAS:
                raise ErroNo(f"deliberacoes: a busca diz ter {total} páginas", permanente=True)
            for achado in _LINK_DELIBERACAO.finditer(html):
                achadas.setdefault(int(achado[2]), urljoin(URL_DELIBERACOES_PARTIDA, achado[1]))
            pagina += 1
        return achadas

    async def _baixar_deliberacao(self, numero: int, url: str) -> Deliberacao | None:
        """A deliberação do invólucro `url`; `None` só se o invólucro não existe (404).

        Invólucro sem o bloco do texto (o layout mudou) ou qualquer outro erro é `ErroNo`: pular a deliberação
        em silêncio esconderia justamente as novas, que são as únicas com texto integral.
        """
        resposta = await self._get_ou_none(url, "deliberacoes")
        if resposta is None:
            return None
        if (bloco := _bloco_do_texto(resposta.texto)) is None:
            raise ErroNo(
                f"deliberacoes: {url} sem o bloco do texto da deliberação (o layout da página mudou?)", permanente=True
            )
        resumo = texto_de_html(bloco)
        carimbo = _CARIMBO.search(resumo)
        data = date(int(carimbo[3]), _MESES_EN.index(carimbo[1]) + 1, int(carimbo[2])) if carimbo else None
        try:
            integral = await self._texto_integral(url, bloco)
        except ErroNo as erro:
            # o anexo de uma deliberação antiga que não responde não trava o índice: ela fica só com o resumo. A
            # recente (ou sem data) é a que traz CNPJ e domínio: o erro sobe e a renovação é tentada de novo
            if data is None or data >= self._agora().date() - timedelta(days=_DIAS_PARA_RELER):
                raise
            _log.warning("deliberacoes: anexo da %s indisponível (%s); fica só com o resumo", numero, erro.mensagem)
            integral = ""
        if not integral:
            return Deliberacao(numero=numero, data=data, url=url, texto=resumo, integral=False)
        # sem carimbo, vale a primeira data do texto integral; a do resumo cita leis e resoluções
        return Deliberacao(
            numero=numero, data=data or _data_por_extenso(integral), url=url, texto=f"{resumo}\n{integral}", integral=True
        )

    async def _texto_integral(self, url: str, bloco: str) -> str:
        """O texto do `.htm` do anexo ou, sem ele (ou sem texto nele), o do PDF; `""` se nenhum dos dois serve."""
        for padrao, extrair in (
            (_LINK_DO_DOCUMENTO, lambda r: texto_de_html(r.texto).strip()),
            # qualquer falha do `pypdf` com o PDF é só "sem texto": a deliberação fica com o resumo
            (_LINK_DO_PDF, lambda r: texto_de_pdf(r.conteudo)),
        ):
            link = padrao.search(bloco)
            resposta = await self._get_ou_none(urljoin(url, link[1]), "deliberacoes") if link else None
            if resposta is not None and (texto := extrair(resposta)):
                return texto
        return ""


def _por_numero(deliberacoes: dict[int, Deliberacao]) -> list[Deliberacao]:
    return sorted(deliberacoes.values(), key=lambda d: d.numero, reverse=True)
