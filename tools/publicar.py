#!/usr/bin/env python3
"""Cria um commit no GitHub pela API REST, sem git local.

Uso:
    GH_TOKEN=$(gh auth token) python tools/publicar.py -m "mensagem" ARQ [ARQ ...]
    (opções: --repo FFloriani/piramide-pentest  --branch main)

ARQ é um caminho relativo à raiz do repositório (a pasta acima de tools/), de onde o
conteúdo é lido. O trailer de coautoria é acrescentado à mensagem se faltar. Caminhos em
`casos/` são recusados: a evidência coletada pelo radar nunca vai para o repositório.

Fluxo: blobs (base64) -> confere sha1("blob <len>\\0" + dados) local contra o remoto ->
tree com base_tree -> commit -> PATCH da ref. Repositório vazio: o primeiro arquivo vai
pela Contents API (que cria o branch) e o resto segue o fluxo normal.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API = "https://api.github.com"
RAIZ = Path(__file__).resolve().parents[1]
REPO_PADRAO = "FFloriani/piramide-pentest"
BRANCH_PADRAO = "main"
TRAILER = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
PASTA_PROIBIDA = "casos"


class ErroPublicar(Exception):
    """Falha esperada (entrada inválida ou resposta inesperada da API)."""


def montar_mensagem(mensagem: str) -> str:
    mensagem = mensagem.rstrip()
    return mensagem if TRAILER in mensagem else f"{mensagem}\n\n{TRAILER}"


def caminho_relativo(arquivo: str, raiz: Path = RAIZ) -> str:
    """Valida `arquivo` (relativo à raiz do repo) e devolve o caminho em formato posix."""
    pedido = Path(arquivo)
    absoluto = (pedido if pedido.is_absolute() else raiz / pedido).resolve()
    try:
        relativo = absoluto.relative_to(raiz.resolve())
    except ValueError:
        raise ErroPublicar(f"fora da raiz do repositório: {arquivo}") from None
    # lower(): no Windows "Casos/" é a mesma pasta; resolve() já eliminou "x/../casos/"
    if relativo.parts and relativo.parts[0].lower() == PASTA_PROIBIDA:
        raise ErroPublicar(f"recusado, {PASTA_PROIBIDA}/ nunca vai para o repositório: {arquivo}")
    if not absoluto.is_file():
        raise ErroPublicar(f"arquivo não encontrado: {arquivo}")
    return relativo.as_posix()


def sha_blob(dados: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(dados) + dados).hexdigest()


def chamar(token: str, metodo: str, caminho: str, corpo: dict | None = None) -> tuple[int, Any]:
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(
        API + caminho,
        data=dados,
        method=metodo,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "radar-publicar",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            texto = r.read()
            return r.status, (json.loads(texto) if texto else None)
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode(errors="replace")[:500] or None)
    except urllib.error.URLError as e:
        raise ErroPublicar(f"sem conexão com o GitHub: {e.reason}") from None


def exigir(status: int, resposta: Any, esperado: tuple[int, ...], etapa: str) -> Any:
    if status not in esperado:
        raise ErroPublicar(f"{etapa}: HTTP {status} {resposta}")
    return resposta


def conferir(caminho: str, sha_local: str, sha_remoto: str) -> None:
    if sha_local != sha_remoto:
        raise ErroPublicar(f"DIF {caminho}: sha local {sha_local} != remoto {sha_remoto}")
    print(f"ok {caminho}")


def publicar(token: str, repo: str, branch: str, mensagem: str, arquivos: list[str],
             raiz: Path = RAIZ) -> str:
    """Faz o commit e devolve o sha dele. `arquivos` já passou por `caminho_relativo`."""
    conteudo = {rel: (raiz / rel).read_bytes() for rel in arquivos}
    ref_url = f"/repos/{repo}/git/ref/heads/{urllib.parse.quote(branch)}"
    ultimo_sha = ""

    status, ref = chamar(token, "GET", ref_url)
    if status in (404, 409):
        # repositório vazio (ou branch ainda inexistente): o primeiro arquivo cria o branch
        primeiro, *arquivos = arquivos
        r = exigir(*chamar(token, "PUT", f"/repos/{repo}/contents/{urllib.parse.quote(primeiro)}", {
            "message": mensagem,
            "content": base64.b64encode(conteudo[primeiro]).decode(),
            "branch": branch,
        }), (200, 201), "criar o branch pela Contents API")
        conferir(primeiro, sha_blob(conteudo[primeiro]), r["content"]["sha"])
        ultimo_sha = r["commit"]["sha"]
        if not arquivos:
            return ultimo_sha
        status, ref = chamar(token, "GET", ref_url)
    ref = exigir(status, ref, (200,), "ler o branch")

    base = ref["object"]["sha"]
    commit_base = exigir(*chamar(token, "GET", f"/repos/{repo}/git/commits/{base}"), (200,), "ler o commit base")
    itens = []
    for rel in arquivos:
        blob = exigir(*chamar(token, "POST", f"/repos/{repo}/git/blobs", {
            "content": base64.b64encode(conteudo[rel]).decode(),
            "encoding": "base64",
        }), (201,), f"enviar {rel}")
        conferir(rel, sha_blob(conteudo[rel]), blob["sha"])
        itens.append({"path": rel, "mode": "100644", "type": "blob", "sha": blob["sha"]})

    arvore = exigir(*chamar(token, "POST", f"/repos/{repo}/git/trees", {
        "base_tree": commit_base["tree"]["sha"],
        "tree": itens,
    }), (201,), "criar a tree")
    novo = exigir(*chamar(token, "POST", f"/repos/{repo}/git/commits", {
        "message": mensagem,
        "tree": arvore["sha"],
        "parents": [base],
    }), (201,), "criar o commit")
    exigir(*chamar(token, "PATCH", f"/repos/{repo}/git/refs/heads/{urllib.parse.quote(branch)}",
                   {"sha": novo["sha"]}), (200,), "atualizar o branch")
    return novo["sha"]


def main(argv: list[str] | None = None) -> int:
    for fluxo in (sys.stdout, sys.stderr):
        fluxo.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Commit no GitHub pela API, sem git local.")
    ap.add_argument("-m", "--mensagem", required=True, help="mensagem do commit")
    ap.add_argument("--repo", default=REPO_PADRAO)
    ap.add_argument("--branch", default=BRANCH_PADRAO)
    ap.add_argument("arquivos", nargs="+", metavar="ARQ", help="caminhos relativos à raiz do repositório")
    args = ap.parse_args(argv)
    try:
        arquivos = list(dict.fromkeys(caminho_relativo(a) for a in args.arquivos))
        token = os.environ.get("GH_TOKEN")
        if not token:
            raise ErroPublicar("GH_TOKEN ausente (use GH_TOKEN=$(gh auth token))")
        mensagem = montar_mensagem(args.mensagem)
        sha = publicar(token, args.repo, args.branch, mensagem, arquivos)
    except ErroPublicar as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    print(f"commit {sha[:10]} em {args.repo}@{args.branch} ({len(arquivos)} arquivo(s)): "
          f"{mensagem.splitlines()[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
