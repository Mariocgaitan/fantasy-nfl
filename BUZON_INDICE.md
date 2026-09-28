# Buzón para el índice — Fantasy NFL

## 2026-09-24
- HITO: proyecto creado. Sistema de recomendación semanal (alineación, agencia libre,
  intercambios) para una liga de fantasy NFL en ESPN (8 equipos, PPR), temporada 2026 y
  portafolio. Validación contra las proyecciones de ESPN con backtest 2024–2025 como
  requisito. Cero costo. Stack pendiente (lo decide la sesión del proyecto); el prototipo
  del draft (`prototipo_draft/`) está en Python con pandas y NumPy, sobre datos de
  nflverse y la API pública de ESPN.
- HITO: draft del 2026-09-23 hecho en vivo con el prototipo: xFP por uso + shrinkage
  hacia ESPN y expertos + VOR + Monte Carlo de los picks rivales.
- LINAJE: técnicas (no código) de [[analisis-apuestas-basketball]] (predicción por
  jugador, API de ESPN, prevención de fuga de datos) y de [[analisis-mundial-predicciones]]
  (backtest con corte temporal estricto contra un modelo de referencia, Monte Carlo).

## 2026-09-26
- HITO: diseño cerrado. Las 11 preguntas abiertas quedaron resueltas (decisiones 12–22 en
  `PROYECTO.md`) y hay spec (`docs/superpowers/specs/2026-09-26-sistema-fantasy-design.md`)
  y plan de la fase 0 (`docs/superpowers/plans/2026-09-26-fase0-provisional.md`).
- HITO: stack definido: Python 3.12 + uv + pandas + Jinja2 + pytest, GitHub Actions (cron),
  GitHub Pages (rama `datos`) y correo vía ntfy.sh. Repo público:
  https://github.com/Mariocgaitan/fantasy-nfl
- HUECO RESUELTO: las proyecciones semanales históricas de ESPN (2023–2025) sí se pueden
  recuperar desde la API pública; son la referencia para validar el modelo.

## 2026-09-28
- HITO: fase 0 desplegada. GitHub Actions genera el reporte (alineación, reemplazos,
  agencia libre, ganando rol) martes 19:00, viernes 08:00 y domingo 20:00 (Sídney), lo
  publica en https://mariocgaitan.github.io/fantasy-nfl/ y avisa por correo. 68 pruebas,
  3 revisiones independientes. Primer reporte automático: martes 2026-09-29.
- ESTADO: diseño -> en producción (provisional, "sin validar"; decide la proyección de ESPN).
- HITO: cambio de stack en notificaciones: correo por Gmail (SMTP) en lugar de ntfy.sh, que
  dejó de permitir correo anónimo.
