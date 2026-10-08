"""Custódia: artefatos endereçados por SHA-256 e log encadeado (Tarefa 3)."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

import pytest

from radar.custodia import Custodia, hash_final, registros, verificar

ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
ZEROS = "0" * 64


def _canonico(registro: dict) -> str:
    return json.dumps(registro, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _entrada(prev: str, registro_sem_entrada: dict) -> str:
    return hashlib.sha256((prev + _canonico(registro_sem_entrada)).encode("utf-8")).hexdigest()


def _linhas(pasta: Path) -> list[str]:
    """Linhas do log, separadas só por `\\n` (como a custódia grava)."""
    with (pasta / "custodia.log").open(encoding="utf-8", newline="\n") as f:
        return f.read().split("\n")[:-1]


def _escrever_linhas(pasta: Path, linhas: list[str]) -> None:
    with (pasta / "custodia.log").open("w", encoding="utf-8", newline="\n") as f:
        f.write("".join(linha + "\n" for linha in linhas))


def test_guardar_e_verificar(tmp_path):
    c = Custodia(tmp_path)
    ref = c.guardar(b"abc", "txt", tipo="pagina", origem="https://x")
    assert ref == f"sha256:{ABC}" and (tmp_path / "artefatos" / f"{ABC}.txt").read_bytes() == b"abc"
    assert verificar(tmp_path) == []


def test_mesmo_conteudo_um_arquivo_duas_linhas(tmp_path):
    c = Custodia(tmp_path)
    c.guardar(b"abc", "txt", "pagina", "a")
    c.guardar(b"abc", "txt", "pagina", "b")
    assert len(list((tmp_path / "artefatos").iterdir())) == 1
    assert len((tmp_path / "custodia.log").read_text(encoding="utf-8").splitlines()) == 2


def test_artefato_adulterado(tmp_path):
    c = Custodia(tmp_path)
    c.guardar(b"abc", "txt", "pagina", "a")
    (tmp_path / "artefatos" / f"{ABC}.txt").write_bytes(b"abd")
    assert verificar(tmp_path) == [f"artefato alterado: sha256:{ABC}"]


def test_log_adulterado(tmp_path):
    c = Custodia(tmp_path)
    c.guardar(b"abc", "txt", "pagina", "a")
    c.guardar(b"x", "txt", "pagina", "b")
    linhas = (tmp_path / "custodia.log").read_text(encoding="utf-8").splitlines()
    linhas[0] = linhas[0].replace('"origem":"a"', '"origem":"z"')
    (tmp_path / "custodia.log").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    assert "cadeia quebrada na linha 0" in verificar(tmp_path)


def test_formato_da_linha_e_encadeamento(tmp_path):
    c = Custodia(tmp_path)
    c.guardar(b"abc", "txt", "pagina", "a")
    c.guardar(b"x", "bin", "api", "b")
    registros = [json.loads(linha) for linha in _linhas(tmp_path)]

    assert [set(r) for r in registros] == [{"seq", "ts", "tipo", "origem", "sha256", "prev", "entrada"}] * 2
    assert [r["seq"] for r in registros] == [0, 1]
    assert registros[0]["sha256"] == ABC and registros[0]["tipo"] == "pagina"
    assert registros[1]["sha256"] == hashlib.sha256(b"x").hexdigest() and registros[1]["origem"] == "b"

    assert registros[0]["prev"] == ZEROS
    assert registros[1]["prev"] == registros[0]["entrada"]
    for r in registros:
        sem_entrada = {k: v for k, v in r.items() if k != "entrada"}
        assert r["entrada"] == _entrada(r["prev"], sem_entrada)

    # a linha é o registro completo, com entrada, no JSON canônico
    for linha, r in zip(_linhas(tmp_path), registros):
        assert linha == _canonico(r)


def test_log_em_utf8_com_lf(tmp_path):
    Custodia(tmp_path).guardar(b"abc", "txt", "pagina", "https://x/ação")
    bruto = (tmp_path / "custodia.log").read_bytes()
    assert b"\r" not in bruto and bruto.endswith(b"\n")
    assert "ação".encode("utf-8") in bruto  # ensure_ascii=False
    assert verificar(tmp_path) == []


def test_seq_continua_em_outra_instancia(tmp_path):
    Custodia(tmp_path).guardar(b"a", "txt", "t", "o")
    Custodia(tmp_path).guardar(b"b", "txt", "t", "o")
    assert [json.loads(linha)["seq"] for linha in _linhas(tmp_path)] == [0, 1]
    assert verificar(tmp_path) == []


def test_ler_e_caminho(tmp_path):
    c = Custodia(tmp_path)
    ref = c.guardar(b"abc", "txt", "pagina", "a")
    assert c.ler(ref) == b"abc"
    assert c.caminho(ref) == tmp_path / "artefatos" / f"{ABC}.txt"


def test_ler_ref_ausente_ou_invalida(tmp_path):
    c = Custodia(tmp_path)
    with pytest.raises(FileNotFoundError):
        c.ler(f"sha256:{ABC}")
    for invalida in ("abc", f"md5:{ABC}", "sha256:../../x", "sha256:" + ABC.upper(), f"sha256:{ABC[:-1]}"):
        with pytest.raises(ValueError):
            c.caminho(invalida)


def test_extensao_invalida(tmp_path):
    c = Custodia(tmp_path)
    for ext in ("", ".", "../x", "a/b", "a b", ".txt"):
        with pytest.raises(ValueError):
            c.guardar(b"abc", ext, "pagina", "a")
    assert not (tmp_path / "custodia.log").exists()


def test_extensao_composta(tmp_path):
    c = Custodia(tmp_path)
    ref = c.guardar(b"abc", "warc.gz", "captura", "a")
    assert c.caminho(ref).name == f"{ABC}.warc.gz"
    assert verificar(tmp_path) == []


def test_mesmo_conteudo_com_outra_extensao_nao_duplica(tmp_path):
    c = Custodia(tmp_path)
    c.guardar(b"abc", "txt", "pagina", "a")
    c.guardar(b"abc", "html", "pagina", "b")
    assert [p.name for p in (tmp_path / "artefatos").iterdir()] == [f"{ABC}.txt"]
    assert len(_linhas(tmp_path)) == 2


def test_guardar_nao_sobrescreve_artefato_existente(tmp_path):
    c = Custodia(tmp_path)
    c.guardar(b"abc", "txt", "pagina", "a")
    arquivo = tmp_path / "artefatos" / f"{ABC}.txt"
    arquivo.write_bytes(b"abd")
    c.guardar(b"abc", "txt", "pagina", "b")
    assert arquivo.read_bytes() == b"abd"  # só grava se ainda não existir
    assert verificar(tmp_path) == [f"artefato alterado: sha256:{ABC}"]


def test_artefato_ausente(tmp_path):
    c = Custodia(tmp_path)
    c.guardar(b"abc", "txt", "pagina", "a")
    (tmp_path / "artefatos" / f"{ABC}.txt").unlink()
    assert verificar(tmp_path) == [f"artefato ausente: sha256:{ABC}"]


def test_artefato_repetido_no_log_gera_um_problema(tmp_path):
    c = Custodia(tmp_path)
    c.guardar(b"abc", "txt", "pagina", "a")
    c.guardar(b"abc", "txt", "pagina", "b")
    (tmp_path / "artefatos" / f"{ABC}.txt").write_bytes(b"abd")
    assert verificar(tmp_path) == [f"artefato alterado: sha256:{ABC}"]


def test_sem_log_a_cadeia_esta_integra(tmp_path):
    assert verificar(tmp_path) == []


def test_log_adulterado_so_acusa_a_linha_editada(tmp_path):
    c = Custodia(tmp_path)
    for i in range(3):
        c.guardar(bytes([i]), "bin", "t", f"o{i}")
    linhas = _linhas(tmp_path)
    linhas[1] = linhas[1].replace('"origem":"o1"', '"origem":"zz"')
    _escrever_linhas(tmp_path, linhas)
    assert verificar(tmp_path) == ["cadeia quebrada na linha 1"]


def test_log_adulterado_com_entrada_recalculada_quebra_a_linha_seguinte(tmp_path):
    c = Custodia(tmp_path)
    c.guardar(b"abc", "txt", "pagina", "a")
    c.guardar(b"x", "txt", "pagina", "b")
    linhas = _linhas(tmp_path)
    r0 = json.loads(linhas[0])
    r0["origem"] = "z"
    r0["entrada"] = _entrada(r0["prev"], {k: v for k, v in r0.items() if k != "entrada"})
    linhas[0] = _canonico(r0)
    _escrever_linhas(tmp_path, linhas)
    assert verificar(tmp_path) == ["cadeia quebrada na linha 1"]


def test_linha_removida_quebra_a_cadeia(tmp_path):
    c = Custodia(tmp_path)
    for i in range(3):
        c.guardar(bytes([i]), "bin", "t", f"o{i}")
    linhas = _linhas(tmp_path)
    del linhas[1]
    _escrever_linhas(tmp_path, linhas)
    assert verificar(tmp_path) == ["cadeia quebrada na linha 1"]


def test_linhas_trocadas_quebram_a_cadeia(tmp_path):
    c = Custodia(tmp_path)
    for i in range(2):
        c.guardar(bytes([i]), "bin", "t", f"o{i}")
    linhas = _linhas(tmp_path)
    _escrever_linhas(tmp_path, linhas[::-1])
    assert verificar(tmp_path) == ["cadeia quebrada na linha 0", "cadeia quebrada na linha 1"]


def test_linha_ilegivel_quebra_a_cadeia(tmp_path):
    c = Custodia(tmp_path)
    c.guardar(b"abc", "txt", "pagina", "a")
    c.guardar(b"x", "txt", "pagina", "b")
    linhas = _linhas(tmp_path)
    linhas[0] = "isto não é json"
    _escrever_linhas(tmp_path, linhas)
    assert verificar(tmp_path) == ["cadeia quebrada na linha 0"]


def test_problemas_na_ordem_em_que_aparecem(tmp_path):
    c = Custodia(tmp_path)
    c.guardar(b"abc", "txt", "pagina", "a")
    c.guardar(b"x", "txt", "pagina", "b")
    (tmp_path / "artefatos" / f"{ABC}.txt").write_bytes(b"abd")
    xis = hashlib.sha256(b"x").hexdigest()
    (tmp_path / "artefatos" / f"{xis}.txt").unlink()
    assert verificar(tmp_path) == [f"artefato alterado: sha256:{ABC}", f"artefato ausente: sha256:{xis}"]


def test_separador_de_linha_unicode_no_registro(tmp_path):
    """U+2028 e U+0085 saem crus no JSON (ensure_ascii=False) e não podem partir a linha."""
    c = Custodia(tmp_path)
    c.guardar(b"abc", "txt", "pagina", "titulo com\u0085separadores")
    c.guardar(b"x", "txt", "pagina", "b")
    assert len(_linhas(tmp_path)) == 2
    assert verificar(tmp_path) == []


def test_guardar_recusa_estender_log_corrompido(tmp_path):
    c = Custodia(tmp_path)
    c.guardar(b"abc", "txt", "pagina", "a")
    _escrever_linhas(tmp_path, ["lixo"])
    with pytest.raises(ValueError, match="custodia.log"):
        c.guardar(b"x", "txt", "pagina", "b")


def test_guardar_nao_deixa_lixo_na_pasta(tmp_path):
    Custodia(tmp_path).guardar(b"abc", "txt", "pagina", "a")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["artefatos", "custodia.log"]
    assert [p.name for p in (tmp_path / "artefatos").iterdir()] == [f"{ABC}.txt"]


def test_guardar_concorrente_mantem_a_cadeia(tmp_path):
    erros: list[BaseException] = []

    def trabalhar(n: int) -> None:
        try:
            c = Custodia(tmp_path)
            for i in range(5):
                c.guardar(f"{n}-{i}".encode(), "txt", "t", f"thread{n}")
        except BaseException as e:  # noqa: BLE001 - leva o erro da thread para o teste
            erros.append(e)

    threads = [threading.Thread(target=trabalhar, args=(n,)) for n in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert erros == []
    assert [json.loads(linha)["seq"] for linha in _linhas(tmp_path)] == list(range(30))
    assert verificar(tmp_path) == []


def test_tipos_do_conteudo(tmp_path):
    c = Custodia(tmp_path)
    ref = c.guardar(b"abc", "txt", tipo="pagina", origem="a")
    assert c.tipos(ref) == {"pagina"}
    # o mesmo conteúdo guardado de novo, com outro tipo: o arquivo é um só, o log registra os dois
    c.guardar(b"abc", "txt", tipo="julgamento", origem="b")
    assert c.tipos(ref) == {"pagina", "julgamento"}
    assert c.tipos(f"sha256:{ZEROS}") == set()


def test_tipos_sem_log_e_vazio(tmp_path):
    assert Custodia(tmp_path / "nada").tipos(f"sha256:{ABC}") == set()


def test_tipos_ignora_linha_ilegivel(tmp_path):
    c = Custodia(tmp_path)
    ref = c.guardar(b"abc", "txt", tipo="pagina", origem="a")
    with (tmp_path / "custodia.log").open("a", encoding="utf-8", newline="\n") as f:
        f.write("isto nao e json\n[1, 2]\n")
    assert c.tipos(ref) == {"pagina"}


def test_tipos_recusa_ref_invalida(tmp_path):
    with pytest.raises(ValueError):
        Custodia(tmp_path).tipos("../etc/passwd")


# ---------------------------------------------------------------------------- hash_final e registros (Tarefa 15)


def test_hash_final_e_a_entrada_da_ultima_linha(tmp_path):
    c = Custodia(tmp_path)
    c.guardar(b"abc", "txt", "pagina", "a")
    c.guardar(b"x", "txt", "pagina", "b")
    ultima = json.loads(_linhas(tmp_path)[-1])
    assert hash_final(tmp_path) == ultima["entrada"]
    assert hash_final(tmp_path) != json.loads(_linhas(tmp_path)[0])["entrada"]


def test_hash_final_sem_log_ou_com_log_vazio_e_none(tmp_path):
    assert hash_final(tmp_path / "nada") is None
    assert hash_final(tmp_path) is None
    (tmp_path / "custodia.log").write_bytes(b"")
    assert hash_final(tmp_path) is None


def test_hash_final_com_separador_unicode_no_registro(tmp_path):
    """U+2028 e U+0085 crus na última linha não podem parti-la: só o LF separa registros."""
    c = Custodia(tmp_path)
    c.guardar(b"abc", "txt", "pagina", "a")
    c.guardar(b"x", "txt", "pagina", "titulo\N{LINE SEPARATOR}com\u0085separadores")
    assert hash_final(tmp_path) == json.loads(_linhas(tmp_path)[-1])["entrada"]


def test_hash_final_recusa_ultima_linha_ilegivel(tmp_path):
    Custodia(tmp_path).guardar(b"abc", "txt", "pagina", "a")
    with (tmp_path / "custodia.log").open("a", encoding="utf-8", newline="\n") as f:
        f.write("isto nao e json\n")
    with pytest.raises(ValueError, match="custodia.log"):
        hash_final(tmp_path)


def test_registros_na_ordem_do_log_sem_as_linhas_ilegiveis(tmp_path):
    c = Custodia(tmp_path)
    c.guardar(b"abc", "txt", "pagina", "a\N{LINE SEPARATOR}b")
    with (tmp_path / "custodia.log").open("a", encoding="utf-8", newline="\n") as f:
        f.write("isto nao e json\n[1, 2]\n")
    registros_ = registros(tmp_path)
    assert [(r["seq"], r["tipo"], r["origem"], r["sha256"]) for r in registros_] == [(0, "pagina", "a\N{LINE SEPARATOR}b", ABC)]
    assert registros(tmp_path / "nada") == []


def test_guardar_em_log_sem_quebra_de_linha_final(tmp_path):
    # I8: um log cujo fim perdeu o "\n" (editor, cópia, queda) não pode colar a linha nova na anterior
    c = Custodia(tmp_path)
    c.guardar(b"um", "txt", tipo="texto", origem="a")
    log = tmp_path / "custodia.log"
    log.write_bytes(log.read_bytes().rstrip(b"\n"))
    c.guardar(b"dois", "txt", tipo="texto", origem="b")
    assert verificar(tmp_path) == []
    assert len(log.read_bytes().split(b"\n")) == 3 and log.read_bytes().endswith(b"\n")
