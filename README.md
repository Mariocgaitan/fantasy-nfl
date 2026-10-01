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

## Fase 1: intercambios y modelo (preliminar)

El reporte del martes propone hasta 5 intercambios (uno por rival, nunca con el rival de la
semana), y la alineación muestra la proyección de un modelo propio junto a la de ESPN. El
modelo **no decide nada** hasta pasar la validación oficial de la fase 3.

Evaluación preliminar semana por semana en 2024 (semanas 3–17, entrenado con 2023 y las
semanas anteriores de 2024; error absoluto medio en puntos, jugadores relevantes):

```
MAE modelo 6.28 · ESPN 6.32 · delta -0.05 (IC95 -0.08 a -0.01)
  QB: modelo 6.64 · ESPN 6.63
  RB: modelo 6.12 · ESPN 6.22
  TE: modelo 5.60 · ESPN 5.56
  WR: modelo 6.55 · ESPN 6.61
```

**Lectura honesta:** la ventaja es solo aparente. El modelo predice en promedio ~0.5 puntos
por debajo de ESPN, y con el error absoluto eso ya basta para mejorar, porque los puntos de
fantasy tienen cola larga hacia arriba y el MAE premia apuntar a la mediana. Si a ESPN se le
aplica el mismo ajuste (multiplicarla por 0.923, calculado solo con 2023), su MAE baja a
6.27: **el modelo empata con una ESPN calibrada, no la supera**, y además no gana en QB ni
en TE. Por eso en el reporte la columna "Modelo" casi siempre queda cerca de ESPN y la ⚑
casi nunca aparece. Para la validación oficial (fase 3) la referencia justa es ESPN
calibrada, no ESPN tal cual. **2025 sigue sellado** para esa validación.

## Comandos

    uv run fantasy historico                  # baja 2023–2024 a historico/
    uv run fantasy entrenar                   # entrena y guarda modelos/modelo_v1.json
    uv run fantasy evaluar --temporada 2024   # walk-forward contra ESPN (2025 rechazado)

## Fase 3: modelo serio y validación

El modelo v2 predice la **corrección** a ESPN calibrada (ESPN × k, con k estimado en
temporadas anteriores) usando, además del uso reciente, el contexto del partido: los
puntos que las casas de apuestas esperan para el equipo, el spread, local o visitante, el
% de targets y de air yards, y lo que la defensa rival ha permitido a esa posición. Todo
con información anterior al partido; el equipo de cada jugador es el último conocido antes
de la semana que se predice.

Siete candidatos (ridge y gradient boosting con pérdida de error absoluto) se compararon en
el walk-forward de 2024 con una regla fijada de antemano (gana el menor MAE):

```
ridge(alpha=1)           MAE 6.253 · ESPN cal 6.273 · delta -0.021
ridge(alpha=10)          MAE 6.253 · ESPN cal 6.273 · delta -0.020
ridge(alpha=100)         MAE 6.253 · ESPN cal 6.273 · delta -0.020
hgb(depth=3,iter=100)    MAE 6.259 · ESPN cal 6.273 · delta -0.014
hgb(depth=2,iter=100)    MAE 6.276 · ESPN cal 6.273 · delta +0.003
hgb(depth=2,iter=300)    MAE 6.295 · ESPN cal 6.273 · delta +0.022
hgb(depth=3,iter=300)    MAE 6.311 · ESPN cal 6.273 · delta +0.037
Elegido: ridge(alpha=1) · k = 0.92
```

El elegido mejora a ESPN calibrada por solo **0.02 puntos por jugador y semana** en 2024: es
una señal muy débil y lo más probable es que **no** pase la validación oficial. El registro
congelado está en `validacion/registro.json`.

**Validación sellada sobre 2025 (corrida única, 2026-10-01): no pasó.** MAE del modelo
6.366 contra 6.305 de ESPN calibrada (delta +0.061, IC95 [−0.007, +0.137]); solo en QB
quedó ligeramente mejor. Resultado completo en `validacion/2025.json`. La mejora vista en
2024 era ruido: exactamente lo que el sellado existe para detectar. El modelo sigue como
segunda opinión y se valida en vivo con 2026 (`fantasy validar-en-vivo`, decisión 23).
