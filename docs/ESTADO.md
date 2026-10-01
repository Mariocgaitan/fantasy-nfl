# Estado del proyecto — 2026-10-01

Documento de arranque para la próxima sesión. Léelo después de `PROYECTO.md` (el **qué**)
y antes de la spec (`docs/superpowers/specs/2026-09-26-sistema-fantasy-design.md`, el
**cómo**).

## Dónde estamos

| Fase | Estado | Qué hace |
|---|---|---|
| 0. Reporte provisional | **En producción** | Martes 19:00, viernes 08:00 y domingo 20:00 (Sídney): alineación óptima, reemplazos por inactivo, agencia libre y "ganando rol". Página en GitHub Pages + correo por Gmail. |
| 1. Intercambios + modelo v1 | **En producción** | El reporte del martes propone hasta 5 intercambios (uno por rival). La agencia libre no suelta jugadores con ADP < 60. |
| 2. Ejecución autorizada | **Sin empezar** | Botones → issue de GitHub → escribir en ESPN; vigilante de inactivos. |
| 3. Modelo serio + validación | **Hecha; el modelo NO pasó** | Modelo v2 (ridge sobre la corrección a ESPN calibrada, con contexto del partido). La corrida sellada de 2025 se hizo una vez y falló (ver abajo). |

Decide **ESPN** (sin calibrar en el reporte, porque no hay modelo validado). El modelo v2
aparece como columna "Modelo" (segunda opinión).

## Resultado de la validación sellada (2025, una sola vez, 2026-10-01)

`validacion/2025.json`: MAE modelo **6.366** contra ESPN calibrada **6.305** (k = 0.92);
delta **+0.061**, IC95 [−0.007, +0.137]. Solo QB quedó ligeramente mejor (6.39 vs 6.41);
RB, WR y TE peor. **No pasa** la decisión 19. La mejora de 2024 (−0.02) era ruido.

Por la decisión 23, el plan B es la **validación en vivo 2026** con el mismo modelo
congelado (`modelos/modelo_v2.joblib`, huella en `validacion/registro.json`).

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
4. **Mejorar el modelo** solo si la validación en vivo también falla, y con un registro
   nuevo (nunca reusar 2025, ya está gastada).

## Menores pendientes (de las revisiones)

- Intercambios y agencia libre no se coordinan (un mismo libre puede salir en ambos).
- La lesión solo cuenta en la semana objetivo; las futuras confían en ESPN.
- El riesgo de veto casi siempre sale "bajo".
- `fantasy evaluar` truena con años distintos de 2024; `comparar` calcula un bootstrap que no usa.
- La población en vivo (plantillas + top 150 libres) es menor que la histórica (top 1500).
- `validar-en-vivo` no exige que 2025 se haya corrido (ya se corrió, así que no importa).
- El archivo de jugadores de nflverse está repetido 3 veces (93 KB c/u).

## La liga (rápido)

- ESPN `leagueId = 898754986`, BanKAI = equipo 5. Waivers: **17:00 Sídney** (07:00 UTC),
  todos los días menos martes; la prioridad solo se mueve cuando un pedido se concreta.
- Plantilla al 2026-10-01: Shough y Bryce Young (QB), Gibbs, Jeanty, Cook (RB),
  Amon-Ra St. Brown, Parker Washington, Watson, Nabers, Golden (WR), McBride, Juwan
  Johnson (TE), Caleb Williams (QB, lesionado). Récord 1-0 (semana 3: 149.0 a 105.5).
- Intercambio hecho: Hall + Swift + Collins → Amon-Ra (con Chumpi, 2026-09-30).

## Comandos

    uv run pytest -q                       # ~150 pruebas, ~2.5 min
    uv run fantasy reporte --tipo martes --salida salida --sin-correo --forzar
    uv run fantasy historico | entrenar | evaluar --temporada 2024 | seleccionar
    uv run fantasy validar-en-vivo --datos <rama datos>
    # `fantasy validar --sellado-final` ya se corrió: se niega a correr otra vez.
