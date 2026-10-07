import tomllib

import pytest
from pydantic import ValidationError

import radar.config as modulo
from radar.config import Config, RedeConfig, carregar_config


def test_config_padrao(tmp_path):
    cfg = carregar_config(tmp_path / "nao_existe.toml")
    assert cfg.rede.tentativas == 4 and cfg.rede.proxy is None
    assert cfg.rede.limites["web.archive.org"] == 2.0 and cfg.rede.limites["*"] == 1.0
    assert cfg.rede.timeouts == {"web.archive.org": 120.0} and cfg.rede.timeout_s == 30.0
    assert cfg.captura.max_subpaginas == 10 and cfg.indices.ttl_horas == 24
    assert cfg.casos_dir.name == "casos"


def test_config_sobrescreve_parcialmente(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('[rede]\nproxy = "socks5://127.0.0.1:9050"\n[captura]\nmax_subpaginas = 3\n', encoding="utf-8")
    cfg = carregar_config(p)
    assert cfg.rede.proxy == "socks5://127.0.0.1:9050" and cfg.captura.max_subpaginas == 3
    assert cfg.rede.tentativas == 4


def test_config_local_sobrepoe_config_toml(tmp_path, monkeypatch):
    monkeypatch.setattr(modulo, "RAIZ_RADAR", tmp_path)
    (tmp_path / "config.toml").write_text("[rede]\ntentativas = 2\ntimeout_s = 5\n", encoding="utf-8")
    (tmp_path / "config.local.toml").write_text("[rede]\ntentativas = 7\n", encoding="utf-8")
    cfg = carregar_config()
    assert cfg.rede.tentativas == 7 and cfg.rede.timeout_s == 5.0


def test_config_rejeita_chave_desconhecida(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text("[rede]\ntentativa = 3\n", encoding="utf-8")  # typo: "tentativas"
    with pytest.raises(ValidationError):
        carregar_config(p)


def test_limites_substitui_o_dicionario_mas_mantem_o_curinga(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('[rede.limites]\n"crt.sh" = 5.0\n', encoding="utf-8")
    limites = carregar_config(p).rede.limites
    assert limites == {"*": 1.0, "crt.sh": 5.0}


def test_timeouts_somam_ao_padrao_quando_so_outro_host_e_configurado(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('[rede.timeouts]\n"crt.sh" = 60.0\n', encoding="utf-8")
    # diferente de `limites`: o padrão do Wayback não se perde
    assert carregar_config(p).rede.timeouts == {"web.archive.org": 120.0, "crt.sh": 60.0}


def test_timeouts_permitem_trocar_o_valor_do_wayback(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('[rede.timeouts]\n"web.archive.org" = 200.0\n', encoding="utf-8")
    assert carregar_config(p).rede.timeouts == {"web.archive.org": 200.0}


def test_timeouts_na_construcao_direta_tambem_somam_ao_padrao():
    assert RedeConfig(timeouts={"x.com": 5}).timeouts == {"web.archive.org": 120.0, "x.com": 5.0}
    assert RedeConfig().timeouts is not RedeConfig().timeouts  # sem dicionário compartilhado


def test_timeouts_local_substitui_o_dicionario_do_config_toml_mas_mantem_o_padrao(tmp_path, monkeypatch):
    monkeypatch.setattr(modulo, "RAIZ_RADAR", tmp_path)
    (tmp_path / "config.toml").write_text('[rede.timeouts]\n"a.com" = 1.0\n', encoding="utf-8")
    (tmp_path / "config.local.toml").write_text('[rede.timeouts]\n"b.com" = 2.0\n', encoding="utf-8")
    assert carregar_config().rede.timeouts == {"web.archive.org": 120.0, "b.com": 2.0}


def test_casos_dir_relativo_vale_a_partir_de_radar(tmp_path, monkeypatch):
    monkeypatch.setattr(modulo, "RAIZ_RADAR", tmp_path)
    p = tmp_path / "c.toml"
    p.write_text('casos_dir = "dados"\n', encoding="utf-8")
    assert carregar_config(p).casos_dir == (tmp_path / "dados").resolve()


def test_config_toml_do_repo_documenta_os_padroes():
    texto = (modulo.RAIZ_RADAR / "config.toml").read_text(encoding="utf-8")
    # "# x = y" é um padrão comentado; "## texto" é prosa; "[seção]" fica como está
    linhas = [
        linha[2:] if linha.startswith("# ") else linha
        for linha in texto.splitlines()
        if not linha.startswith("##")
    ]
    documentado = tomllib.loads("\n".join(linhas))
    assert set(documentado) == {"casos_dir", "rede", "captura", "indices"}
    assert Config.model_validate(documentado) == Config()
    # o padrão tem de estar documentado de fato: sem a seção, o validador o completaria sozinho
    assert documentado["rede"]["timeouts"] == {"web.archive.org": 120.0}
