# fantasy-nfl

Recomendador semanal para una liga de fantasy NFL en ESPN (8 equipos, PPR):
alineación, reemplazos condicionales y agencia libre, con intercambios y un modelo
propio validado contra ESPN en las fases siguientes.

- Qué y por qué: [`PROYECTO.md`](PROYECTO.md)
- Diseño: [`docs/superpowers/specs/2026-09-26-sistema-fantasy-design.md`](docs/superpowers/specs/2026-09-26-sistema-fantasy-design.md)
- Reporte publicado: https://mariocgaitan.github.io/fantasy-nfl/

**Estado: provisional, sin validar.** Decide la proyección de ESPN; el modelo propio
solo mandará cuando le gane a ESPN en un backtest 2024–2025 sin fuga de datos.

## Uso

    uv sync
    uv run pytest
    uv run fantasy reporte --tipo martes --salida salida --sin-correo

Con `--instantanea <carpeta>` corre sin red a partir de datos guardados.
