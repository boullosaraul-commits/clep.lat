#!/usr/bin/env python3
"""Política determinista de fallback de media para CLEP.

Este módulo no resuelve, adquiere ni valida media. Sólo clasifica si un fallo
estructurado permite rechazar el método actual y pedir al resolver el siguiente
método de la jerarquía. Errores de contrato, rutas, integridad/hash, seguridad
SVG y fallos internos son siempre fail-closed.
"""
from __future__ import annotations

from adquirir_media import MediaAcquisitionError, is_fallback_acquisition_error
from validar_media import (
    ERROR_DIMENSIONS_TOO_LARGE,
    ERROR_DIMENSIONS_TOO_SMALL,
    ERROR_EXTENSION_MISMATCH,
    ERROR_FILE_EMPTY,
    ERROR_FILE_TOO_LARGE,
    ERROR_FORMAT_UNSUPPORTED,
    ERROR_RASTER_CORRUPT,
    ERROR_TYPE_MISMATCH,
    MediaValidationResult,
)

FALLBACK_VALIDATION_ERRORS = frozenset(
    {
        ERROR_FILE_EMPTY,
        ERROR_FILE_TOO_LARGE,
        ERROR_FORMAT_UNSUPPORTED,
        ERROR_TYPE_MISMATCH,
        ERROR_EXTENSION_MISMATCH,
        ERROR_RASTER_CORRUPT,
        ERROR_DIMENSIONS_TOO_SMALL,
        ERROR_DIMENSIONS_TOO_LARGE,
    }
)


def validation_can_fallback(result: MediaValidationResult) -> bool:
    """True sólo si todos los errores pertenecen al asset concreto."""
    return bool(result.errors) and all(
        issue.code in FALLBACK_VALIDATION_ERRORS for issue in result.errors
    )


def acquisition_can_fallback(error: MediaAcquisitionError) -> bool:
    """Delega la clasificación de adquisición a su autoridad canónica."""
    return is_fallback_acquisition_error(error)
