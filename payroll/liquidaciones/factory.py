"""Fábrica de liquidaciones por tipo (Factory + polimorfismo)."""

from __future__ import annotations

from .contexto import ContextoLiquidacion
from .tipos import (
    AbandonoTrabajo,
    DespidoConCausa,
    DespidoSinCausa,
    LiquidacionBase,
    MutuoAcuerdo,
    RenunciaVoluntaria,
)

_TIPOS: dict[str, type[LiquidacionBase]] = {
    RenunciaVoluntaria.tipo: RenunciaVoluntaria,
    DespidoSinCausa.tipo: DespidoSinCausa,
    DespidoConCausa.tipo: DespidoConCausa,
    AbandonoTrabajo.tipo: AbandonoTrabajo,
    MutuoAcuerdo.tipo: MutuoAcuerdo,
}

# Alias tolerantes para valores heredados del formulario/DB.
_ALIAS: dict[str, str] = {
    "renuncia": RenunciaVoluntaria.tipo,
    "renuncia-voluntaria": RenunciaVoluntaria.tipo,
    "despido": DespidoSinCausa.tipo,
    "despido-sin-causa": DespidoSinCausa.tipo,
    "despido-injustificado": DespidoSinCausa.tipo,
    "despido-con-causa": DespidoConCausa.tipo,
    "despido-justificado": DespidoConCausa.tipo,
    "abandono": AbandonoTrabajo.tipo,
    "abandono-trabajo": AbandonoTrabajo.tipo,
    "mutuo-acuerdo": MutuoAcuerdo.tipo,
    "fin-de-contrato": MutuoAcuerdo.tipo,
    "fin-contrato": MutuoAcuerdo.tipo,
}


def normalizar_tipo(tipo: str | None) -> str:
    clave = (tipo or "").strip().lower()
    return _ALIAS.get(clave, clave if clave in _TIPOS else RenunciaVoluntaria.tipo)


def tipos_disponibles() -> list[str]:
    return list(_TIPOS.keys())


def crear_liquidacion(tipo: str | None, contexto: ContextoLiquidacion) -> LiquidacionBase:
    """Instancia la liquidación correspondiente al ``tipo`` indicado."""
    clave = normalizar_tipo(tipo)
    clase = _TIPOS.get(clave, RenunciaVoluntaria)
    return clase(contexto)
