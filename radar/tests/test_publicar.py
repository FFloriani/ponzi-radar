"""`tools/publicar.py` (item barato da revisão final): o que o `.gitignore` ignora nunca vai para o repositório."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_CAMINHO = Path(__file__).resolve().parents[2] / "tools" / "publicar.py"
_spec = importlib.util.spec_from_file_location("publicar", _CAMINHO)
publicar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(publicar)

GITIGNORE = """# comentário
casos/

# Python
.venv/
__pycache__/
*.py[cod]
*.egg-info/

# local
.env
config.local.toml
/so_na_raiz.txt
docs/rascunhos/
"""


@pytest.fixture
def raiz(tmp_path) -> Path:
    (tmp_path / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    for caminho in (
        "radar/config.local.toml", "radar/config.toml", ".env", "radar/.env", "radar/.venv/lib/x.py",
        "radar/radar/__pycache__/m.cpython-314.pyc", "radar/radar/m.pyc", "radar/radar/m.py",
        "radar/radar_piramides.egg-info/PKG-INFO", "so_na_raiz.txt", "radar/so_na_raiz.txt",
        "docs/rascunhos/a.md", "docs/a.md", "casos/x/estado.json", "Config.Local.TOML",
    ):
        (tmp_path / caminho).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / caminho).write_text("x", encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    ("arquivo", "padrao"),
    [
        ("radar/config.local.toml", "config.local.toml"),
        ("Config.Local.TOML", "config.local.toml"),  # sem diferenciar maiúsculas (o Windows não diferencia)
        (".env", ".env"),
        ("radar/.env", ".env"),
        ("radar/.venv/lib/x.py", ".venv/"),
        ("radar/radar/__pycache__/m.cpython-314.pyc", "__pycache__/"),
        ("radar/radar/m.pyc", "*.py[cod]"),
        ("radar/radar_piramides.egg-info/PKG-INFO", "*.egg-info/"),
        ("so_na_raiz.txt", "/so_na_raiz.txt"),
        ("docs/rascunhos/a.md", "docs/rascunhos/"),
    ],
)
def test_recusa_o_que_o_gitignore_ignora(raiz, arquivo, padrao):
    with pytest.raises(publicar.ErroPublicar) as e:
        publicar.caminho_relativo(arquivo, raiz)
    assert str(e.value) == (
        f"recusado, ignorado pelo .gitignore ({padrao}): {arquivo} pode ter credencial ou dado local"
    )


@pytest.mark.parametrize("arquivo", ["radar/config.toml", "radar/radar/m.py", "radar/so_na_raiz.txt", "docs/a.md"])
def test_aceita_o_que_o_gitignore_nao_ignora(raiz, arquivo):
    assert publicar.caminho_relativo(arquivo, raiz) == arquivo


def test_casos_continua_recusado(raiz):
    with pytest.raises(publicar.ErroPublicar, match="casos/ nunca vai para o repositório"):
        publicar.caminho_relativo("casos/x/estado.json", raiz)


def test_sem_gitignore_vale_so_a_regra_de_casos(tmp_path):
    (tmp_path / "config.local.toml").write_text("x", encoding="utf-8")
    assert publicar.caminho_relativo("config.local.toml", tmp_path) == "config.local.toml"


def test_o_gitignore_do_repositorio_protege_a_config_local():
    raiz = _CAMINHO.parents[1]
    with pytest.raises(publicar.ErroPublicar, match="ignorado pelo .gitignore"):
        publicar.caminho_relativo("radar/config.local.toml", raiz)
