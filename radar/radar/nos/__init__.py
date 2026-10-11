"""Nós do DAG. `nos_do_nucleo()` é a lista que o motor executa; cresce a cada tarefa."""

from __future__ import annotations

from radar.motor import NoBase
from radar.nos.alvo import AlvoNo
from radar.nos.captura import CapturaNo
from radar.nos.cnpj import CnpjNo
from radar.nos.ct import CtNo
from radar.nos.cvm import CvmAlertasNo, CvmSancionadorNo, RegistrosNo
from radar.nos.destino import DestinoNo
from radar.nos.dns import DnsNo
from radar.nos.extracao import ExtracaoNo
from radar.nos.pendencias import nos_de_pendencia
from radar.nos.rdap import RdapNo
from radar.nos.wayback import WaybackIndiceNo, WaybackSnapshotNo


# A `CapturaNo` vê o redirect da página inicial e o `DestinoNo` escolhe o domínio que os coletores de domínio (`rdap`,
# `dns`, `ct`, `wayback_*`) analisam: o do alvo ou o do site para onde ele redireciona (melhorias do aceite, T1). O motor
# recusa dependência inexistente: os três entram juntos. `WaybackSnapshotNo` também declara `captura` como opcional.
# `ExtracaoNo` lê a captura e o snapshot e `CnpjNo` lê a extração. Os três nós da CVM/BCB leem `Servicos.indices` (sem ele
# caem em erro): `cvm_alertas` usa o `cnpj` se houver, os outros dois dependem dele; `registros` e `cvm_alertas` usam o
# domínio do `destino`. Os `pend_*` (T12) vêm por último: leem a extração, o `cnpj` e o `cvm_alertas`, e a `pend_e`
# espera todos os coletores.
def nos_do_nucleo() -> list[NoBase]:
    return [
        AlvoNo(),
        CapturaNo(),
        DestinoNo(),
        RdapNo(),
        DnsNo(),
        CtNo(),
        WaybackIndiceNo(),
        WaybackSnapshotNo(),
        ExtracaoNo(),
        CnpjNo(),
        RegistrosNo(),
        CvmSancionadorNo(),
        CvmAlertasNo(),
        *nos_de_pendencia(),
    ]
