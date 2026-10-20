# Estado del proyecto — 2026-10-06

Documento de arranque para la próxima sesión. Léelo después de `PROYECTO.md` (el **qué**)
y antes de la spec (`docs/superpowers/specs/2026-09-26-sistema-fantasy-design.md`, el
**cómo**).

## Dónde estamos

| Fase | Estado | Qué hace |
|---|---|---|
| 0. Reporte provisional | **En producción** | Martes 19:00, viernes 08:00 y domingo 20:00 (Sídney): "Qué hacer" con urgencia (🔴/🟡/⚪), plantilla con lugares libres (respaldo o moneda de cambio), plan si alguien queda fuera, agencia libre e intercambios por semana, ganando rol (libres y banca de rivales). Página en GitHub Pages + aviso por Gmail. |
| 1. Intercambios + modelo v1 | **En producción** | El reporte del martes propone hasta 5 intercambios (uno por rival). La agencia libre no suelta jugadores con ADP < 60. |
| Empates en el reporte | **En producción al fusionar la rama `desempate`** | Sección "Decisiones parejas": empate (≤ 1 punto) y casi empate (1–2) entre un titular y su mejor suplente, con el total esperado de su equipo según las apuestas. Solo informa. |
| 2. Ejecución autorizada | **Sin empezar** | Botones → issue de GitHub → escribir en ESPN; vigilante de inactivos. |
| 4. Probabilidad de ganar | **Construida; falta la prueba única de 2025** | Ver "Probabilidad de ganar" abajo. |
| 3. Modelo serio + validación | **Hecha; el modelo NO pasó** | Modelo v2 (ridge sobre la corrección a ESPN calibrada, con contexto del partido). La corrida sellada de 2025 se hizo una vez y falló (ver abajo). |

Decide **ESPN** (sin calibrar en el reporte, porque no hay modelo validado). El modelo v2
aparece como columna "Modelo" (segunda opinión).

## Resultado de la validación sellada (2025, una sola vez, 2026-10-01)

`validacion/2025.json`: MAE modelo **6.366** contra ESPN calibrada **6.305** (k = 0.92);
delta **+0.061**, IC95 [−0.007, +0.137]. Solo QB quedó ligeramente mejor (6.39 vs 6.41);
RB, WR y TE peor. **No pasa** la decisión 19. La mejora de 2024 (−0.02) era ruido.

Por la decisión 23, el plan B es la **validación en vivo 2026** con el mismo modelo
congelado (`modelos/modelo_v2.joblib`, huella en `validacion/registro.json`).

## Probabilidad de ganar (decisión 25)

El reporte puede calcular la **probabilidad de ganar** contra el rival real (errores reales de
ESPN por posición, compañeros correlacionados, Monte Carlo) y, si pasa la prueba única de 2025,
alinear para maximizarla en decisiones parejas. Spec:
`docs/superpowers/specs/2026-10-05-prob-ganar-design.md`; plan:
`docs/superpowers/plans/2026-10-05-prob-ganar.md`.

- **Grupos por rol:** con la prueba justa (mínimo de 100 errores por celda al elegir k) la mayor
  mejora fue 0.4 % (< 1 % de empate) → **k = 1 en todas las posiciones** ("solo posición").
- **Ensayo 2024** (desarrollo, 200 ligas): **gana más ❌** (delta 0.0; la alineación cambió en 23
  de 24 000 enfrentamientos) · **porcentajes creíbles ✅** (máx. ±2.3 puntos por tramo).
- **Lo esperable en 2025:** que solo pase lo segundo → el reporte **muestra el porcentaje sin
  cambiar la alineación**. Coincide con la exploración del desempate: ni la historia ni el rol
  del jugador predicen si supera a ESPN.
- Mientras no exista `validacion/2025_pganar.json`, el reporte no muestra la sección.

## Empates y desempate por total de equipo (2026-10-19)

Spec: `docs/superpowers/specs/2026-10-19-desempate-design.md`. Exploración en 2023–2024 (2025
sin tocar): el sesgo por jugador respecto a ESPN no persiste; lo único que inclina el
resultado es el total esperado del equipo según las apuestas. Con proyecciones a ≤ 1 punto,
la de ESPN acierta 51.0 % (una moneda) y el mayor total de equipo 53.9 %; **en los pares en
conflicto** (lo que de verdad cambiaría una decisión) 52.9 % en 2023–2024 y **48.1 % en 2026,
semanas 1–6**. Por eso se construyó solo la marca de empates (sin desempatar). La regla queda
**registrada sin correr** (spec, sección 3); 2025 sigue sin usar para esta pregunta. Se puede
retomar si al final de 2026 la regla se recupera en vivo.

## Pendientes, en orden

1. **Validación en vivo 2026.** Con 8 semanas terminadas (semanas 5–12, hacia fines de
   noviembre): baja la rama `datos` y corre
   `uv run fantasy validar-en-vivo --datos <carpeta de la rama datos>`. El primer resultado
   con 8 semanas queda congelado en `validacion/2026_vivo.json`. **No cambies `src/` del
   modelo ni reentrenes** antes de eso (la huella lo detectaría y el modelo no mandaría).
   Las instantáneas desde la semana 5 ya traen `juegos` y las columnas nuevas de nflverse.
2. **El cron de GitHub no es confiable** (el 2026-09-29 disparó 1 de 4 corridas con 5.5 h
   de retraso y luego dejó de disparar). Acuerdo con Mario: **revisión manual** de cada
   reporte; si no salió, `gh workflow run reporte -f tipo=<martes|viernes|domingo> -f forzar=true`.
   Alternativa propuesta y no aceptada todavía: disparador externo gratis (cron-job.org).
3. **Fase 2 (ejecución en ESPN).** Empieza con una prueba corta: Mario guarda `espn_s2` y
   `SWID` en `C:\Users\mario\.fantasy-nfl\cookies.txt` (fuera del repo) y autoriza una
   acción concreta. Diseño en la spec, sección 5. Pendiente de brainstorming detallado.
4. **Prueba única de 2025 de la probabilidad de ganar** — solo con el visto bueno de Mario:
   `uv run fantasy varianza-registrar`, commit, y `uv run fantasy varianza-validar --sellado-final`.
5. **Mejorar el modelo** solo si la validación en vivo también falla, y con un registro
   nuevo. 2025 ya se usó para el modelo de puntos y (una vez) para la varianza.

## Menores pendientes (de las revisiones)

- `fantasy evaluar` truena con años distintos de 2024; `comparar` calcula un bootstrap que no usa.
- La población en vivo (plantillas + top 150 libres) es menor que la histórica (top 1500).
- `validar-en-vivo` no exige que 2025 se haya corrido (ya se corrió, así que no importa).

## Pendientes cerrados sin cambio de código

- "La lesión solo cuenta en la semana objetivo": no hace falta. ESPN ya pone en 0 las
  semanas en que espera la baja (Caleb Williams 0 en semanas 4–5 y ~17 desde la 6; Achane
  0 hasta la 18). Aplicar `p_jugar` a semanas futuras contaría la lesión dos veces.
- "El archivo de jugadores de nflverse está repetido 3 veces": no vale la pena. Ahorra
  ~190 KB y obliga a tocar `ingesta/historico.py`, que alimenta al modelo congelado hasta la
  validación en vivo; la copia del fixture debe quedarse (cada instantánea es autocontenida).

## La liga (rápido)

- ESPN `leagueId = 898754986`, BanKAI = equipo 5. Waivers: **17:00 Sídney** (07:00 UTC),
  todos los días menos martes; la prioridad solo se mueve cuando un pedido se concreta.
- Plantilla al 2026-10-01: Shough y Bryce Young (QB), Gibbs, Jeanty, Cook (RB),
  Amon-Ra St. Brown, Parker Washington, Watson, Nabers, Golden (WR), McBride, Juwan
  Johnson (TE), Caleb Williams (QB, lesionado), J.K. Dobbins (RB, desde el 2026-10-02).
- Récord **1-1**: semana 3 ganó 149.0 a 105.5 (Smashers); semana 4 perdió **101.7 a 149.5
  contra Norway Ass** (iba +22.1 proyectado, ≈75%; Nabers hizo 23.2 en la banca y aun con la
  alineación perfecta, 122.9, perdía). El enfrentamiento de la semana N es `matchupPeriodId == N`
  en ESPN (`espn.rival_de` lo hace bien).
- Intercambio hecho: Hall + Swift + Collins → Amon-Ra (con Chumpi, 2026-09-30).

## Sincronía reporte ↔ sesión

Cuando Mario pregunte qué hacer, la sesión corre este mismo reporte
(`uv run fantasy reporte --tipo <tipo> --salida <tmp> --sin-correo --forzar`) y parte de su
"Qué hacer". Si la sesión recomienda algo distinto, dice por qué (error del reporte o algo que
el reporte no sabe) y lo anota como pendiente.

## Comandos

    uv run pytest -q                       # ~255 pruebas, ~4 min
    uv run fantasy reporte --tipo martes --salida salida --sin-correo --forzar
    uv run fantasy historico | entrenar | evaluar --temporada 2024 | seleccionar
    uv run fantasy validar-en-vivo --datos <rama datos>
    # `fantasy validar --sellado-final` ya se corrió: se niega a correr otra vez.
    uv run fantasy varianza-construir      # grupos, errores y correlaciones (2023–2024)
    uv run fantasy varianza-ensayo         # ligas simuladas sobre 2024 (~25 min)
    uv run fantasy varianza-registrar      # congela el registro antes del sellado
    uv run fantasy varianza-validar --sellado-final   # 2025, una sola vez (visto bueno de Mario)
