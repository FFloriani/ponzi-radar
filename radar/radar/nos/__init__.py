"""Nós do DAG. `nos_do_nucleo()` é a lista que o motor executa; cresce a cada tarefa."""

from __future__ import annotations

from radar.motor import NoBase
from radar.nos.alvo import AlvoNo
from radar.nos.captura import CapturaNo
from radar.nos.ct import CtNo
from radar.nos.dns import DnsNo
from radar.nos.rdap import RdapNo
from radar.nos.wayback import WaybackIndiceNo, WaybackSnapshotNo


# `WaybackSnapshotNo` declara `captura` como opcional e o motor recusa dependência inexistente: os
# dois entram juntos, a captura antes do snapshot.
def nos_do_nucleo() -> list[NoBase]:
    return [
        AlvoNo(),
        RdapNo(),
        DnsNo(),
        CtNo(),
        WaybackIndiceNo(),
        CapturaNo(),
        WaybackSnapshotNo(),
    ]
