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
