"""Nós do DAG. `nos_do_nucleo()` é a lista que o motor executa; cresce a cada tarefa."""

from __future__ import annotations

from radar.motor import NoBase
from radar.nos.alvo import AlvoNo
from radar.nos.captura import CapturaNo
from radar.nos.cnpj import CnpjNo
from radar.nos.ct import CtNo
from radar.nos.cvm import CvmAlertasNo, CvmSancionadorNo, RegistrosNo
from radar.nos.dns import DnsNo
from radar.nos.extracao import ExtracaoNo
from radar.nos.pendencias import nos_de_pendencia
from radar.nos.rdap import RdapNo
from radar.nos.wayback import WaybackIndiceNo, WaybackSnapshotNo


# `WaybackSnapshotNo` declara `captura` como opcional e o motor recusa dependência inexistente: os
# dois entram juntos, a captura antes do snapshot. `ExtracaoNo` lê os dois e `CnpjNo` lê a extração. Os três nós da
# CVM/BCB leem `Servicos.indices` (sem ele caem em erro): `cvm_alertas` usa o `cnpj` se houver, os outros dois dependem dele.
# Os `pend_*` (T12) vêm por último: leem a extração, o `cnpj` e o `cvm_alertas`, e a `pend_e` espera todos os coletores.
def nos_do_nucleo() -> list[NoBase]:
    return [
        AlvoNo(),
        RdapNo(),
        DnsNo(),
        CtNo(),
        WaybackIndiceNo(),
        CapturaNo(),
        WaybackSnapshotNo(),
        ExtracaoNo(),
        CnpjNo(),
        RegistrosNo(),
        CvmSancionadorNo(),
        CvmAlertasNo(),
        *nos_de_pendencia(),
    ]
