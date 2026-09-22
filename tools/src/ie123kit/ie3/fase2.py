"""CLI compatible de fase 2; el algoritmo vive en el núcleo común IE3."""

from ie123kit.ie3.comun.emision import auditar, cargar_pares, compilar, guardar, main, piloto, resolver

__all__ = ["auditar", "cargar_pares", "compilar", "guardar", "main", "piloto", "resolver"]

if __name__ == "__main__":
    raise SystemExit(main())
