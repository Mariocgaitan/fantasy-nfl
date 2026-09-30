# Fantasy NFL — documento maestro

> Definido en la sesión padre del 2026-09-23/24, abierta en la raíz de `Repositorios`.
> Aquí está el **qué**. El **cómo** (stack, arquitectura, spec, plan) le toca a la
> sesión que se abra dentro de esta carpeta.
>
> **Diseño (el cómo):** `docs/superpowers/specs/2026-09-26-sistema-fantasy-design.md`.

## Objetivo

Ganar cada enfrentamiento semanal de la **CACHORRITAS LEAGUE** (ESPN, temporada 2026)
con un sistema que recomiende **alineación, agencia libre e intercambios** usando data
science, machine learning y estadística, y que se vaya adaptando conforme avanza la
temporada, mirando hacia adelante y no solo a la semana en curso.

Mario no conoce la NFL. El sistema no pretende enseñarle: tiene que decidir bien y
decir qué hacer. Además es **proyecto de portafolio**: el código, la validación y la
documentación tienen que poder mostrarse.

## La restricción que lo define

**La temporada ya está corriendo y el modelo no puede mandar sin haberse validado.**

La temporada regular de la liga son 12 semanas (NFL semanas 3–14, playoffs 15–17).
Cada semana sin sistema se decide a mano, pero Mario exige que el modelo le gane a
ESPN en un backtest antes de usarlo. De ahí la entrega por etapas: una versión
provisional, marcada **"sin validar"**, para la semana 4 o 5, y el modelo validado la
sustituye solo cuando pase la validación.

Encima de eso: **cero costo** y **nada se ejecuta en ESPN sin autorización de Mario**.

## Preguntas que el sistema debe contestar cada semana

1. **Alineación:** ¿a quién pongo de titular esta semana y quién va de reemplazo si
   alguien queda inactivo?
2. **Agencia libre:** ¿a quién pido de la agencia libre y a quién suelto? ¿Quién viene
   ganando rol antes de que el mercado lo note?
3. **Intercambios:** ¿qué oferta me conviene, y a qué rival le conviene un intercambio
   conmigo? (Por ejemplo, mis RB de sobra por un WR.)
4. **A futuro:** ¿cómo se ve mi equipo en las próximas semanas: descansos, calendario de
   rivales, lesiones, playoffs?

## Decisiones cerradas

| # | Tema | Decisión |
|---|---|---|
| 1 | Qué decide | Alineación, agencia libre e intercambios. **Sin parte educativa.** |
| 2 | Cómo se usa | **Reporte automático + sesiones con Claude** para lo que se salga de lo normal (lesión de último momento, oferta de intercambio, decisión reñida). |
| 3 | Acceso a datos | La liga se hizo **pública** el 2026-09-24. Se lee sin cookies. **Verificado**: la API respondió con los 8 equipos, las plantillas, la configuración y los enfrentamientos. |
| 4 | Ejecución | **Recomienda siempre y ejecuta solo con autorización explícita de Mario**, acción por acción. Nunca actúa por su cuenta. |
| 5 | Dónde se ve | **Notificación al teléfono + página web** con el detalle y un botón para autorizar cada acción. |
| 6 | Cuándo | **Tres reportes por semana** (hora de Sídney): martes o miércoles (agencia libre, intercambios, alineación preliminar), viernes en la mañana (antes del partido del jueves) y domingo en la noche (alineación final). Los horarios exactos quedan abiertos. |
| 7 | Riesgo de madrugada | Los inactivos se anuncian ~90 min antes de cada partido; los del domingo empiezan ~3 AM en Sídney. Solución: **(a)** alineaciones que evitan a los jugadores en duda cuando la diferencia de proyección es pequeña, **y (b)** reemplazos condicionales que Mario autoriza en el reporte del domingo ("si X sale inactivo, entra Y"). La regla (b) es autorización previa, caso por caso, y no rompe la decisión 4. |
| 8 | Validación | **Requisito:** (B) las proyecciones del sistema tienen que ser más precisas que las de ESPN, y (C) un backtest en 2024–2025 sin fuga de datos del futuro tiene que mostrarlo. **Seguimiento:** (A) puntos dejados en la banca frente a la alineación óptima, y (D) victorias, puntos a favor y lugar en la tabla. |
| 9 | Entregas | Por etapas: versión provisional "sin validar" para la semana 4 o 5 y, en paralelo, el modelo serio. El modelo solo manda cuando pasa la validación. |
| 10 | Alcance | **Solo esta liga y esta temporada** (termina en diciembre de 2026), y además **portafolio**. |
| 11 | Costo | **Cero.** Solo datos y herramientas gratis. La lectura de noticias y contexto con IA queda para las sesiones con Claude (suscripción de Mario), no para el reporte automático. |
| 12 | Dónde corre | **GitHub Actions** en un repo público (gratis, con horario cron, y el código queda visible como portafolio). El cron puede retrasarse de 5 a 30 min, así que nada puede depender del minuto exacto. (2026-09-24) |
| 13 | Notificación | **Correo desde Gmail con contraseña de aplicación** (SMTP), guardada como secreto de GitHub junto con la cuenta remitente y el destino (Hotmail de Mario). Reemplaza al reenvío de ntfy.sh, que desde entonces exige cuenta (`anonymous email sending is not allowed`, verificado 2026-09-28). Contenido no confidencial. (2026-09-28) |
| 14 | Horarios | Hora de Sídney: **martes 19:00** (el partido del lunes ya terminó y el martes ESPN no procesa waivers), **viernes 08:00** (después del reporte de práctica del jueves; el partido es ~10:15) y **domingo 20:00** (con los estados finales del sábado, ~7 h antes del primer partido). Se calculan en hora de Sídney, no en UTC fijo, por el cambio de horario (4-oct AU, 1-nov EE. UU.). La liga procesa waivers todos los días menos el martes; **verificado el 2026-09-30: a las 17:00 de Sídney (horario estándar)**, es decir 07:00 UTC. Con el horario de verano de Sídney pasa a las 18:00. (2026-09-24) |
| 15 | Versión provisional | **Deciden las proyecciones de ESPN** (la referencia a superar) con reglas de riesgo encima, y el modelo aparece al lado como **"segunda opinión — sin validar"**; cada reporte lo dice arriba. Así se respeta la decisión 9. Incluye: alineación óptima, evitar jugadores en duda cuando la diferencia es pequeña, reemplazos condicionales, agencia libre (pedir y soltar, quién viene ganando rol) e **intercambios**. **Sin botón de autorizar**: Mario ejecuta en la app de ESPN. Si los intercambios no llegan a tiempo, sale primero alineación + agencia libre. (2026-09-24) |
| 16 | Agresividad en intercambios | **Agresivo**: busca la mayor ganancia según el modelo aunque el intercambio se vea desigual en ESPN. Siempre tiene que salir **ganador según el modelo**. El riesgo de veto se muestra como dato, no como filtro. (2026-09-24) |
| 17 | Valor para los rivales | **Fama + ESPN + necesidad:** mezcla del nombre (ADP, como en el simulador del draft) y la proyección de ESPN, ajustada por lo que a cada rival le falta o le sobra por posición. Se recalibra con los intercambios y movimientos que hagan los rivales en la temporada. (2026-09-24) |
| 18 | Referencia del requisito B | **Las proyecciones semanales de ESPN de 2023, 2024 y 2025 sí se recuperan** (`leaguedefaults/3`, `statSourceId=1`, `statSplitTypeId=1`, semanas 1–18, ~295 de los 300 jugadores más usados por semana). **Verificado** el 2026-09-24. Pendiente al construir: confirmar que es la proyección previa al partido y pedir la lista completa de jugadores (no solo el top 300 del final de la temporada) para evitar sesgo de supervivencia. |
| 19 | Criterio de "le gana a ESPN" | **MAE** en puntos PPR por jugador y semana, solo con jugadores relevantes (los que podrían ser titulares en una liga de 8). Gana si la diferencia de MAE (modelo − ESPN) es negativa y su **intervalo bootstrap del 95%, remuestreando por semanas**, no incluye el cero. Además no puede perder en ninguna posición. (2026-09-24) |
| 20 | Backtest | Semana por semana (walk-forward), **semanas 3–17**. El modelo se desarrolla y ajusta **solo con 2024** (y 2023 como historia). **2025 queda sellado**: se corre una sola vez al final y ese resultado decide. Contra la fuga: cada predicción usa solo datos anteriores al inicio del partido, y un chequeo en tiempo de ejecución detiene el backtest si aparece un dato posterior. (2026-09-24) |
| 21 | Autenticación para escribir | Las cookies `espn_s2` y `SWID` de Mario se guardan como **secretos cifrados del repo en GitHub** (nunca en el código ni en los logs). Si ESPN las rechaza, el sistema avisa por correo y Mario las vuelve a copiar desde el navegador. ESPN no tiene API oficial de escritura: el endpoint puede cambiar sin aviso. (2026-09-24) |
| 22 | Flujo de autorización | Cada acción de la página tiene un botón que abre un **issue de GitHub ya lleno** ("AUTORIZO acción #N"). Un workflow comprueba que el autor es la cuenta de Mario, ejecuta en ESPN y responde en el issue con el resultado, además de un correo de confirmación. Los **reemplazos condicionales** se autorizan igual en el reporte del domingo, y un vigilante corre cada ~10 min en las ventanas de inactivos y los aplica solo si se cumple la condición aprobada. (2026-09-24) |

## La liga

- **ESPN**, `leagueId = 898754986`, pública. Mario es el **equipo 5, "BanKAI"**.
- 8 equipos · H2H por puntos · **PPR completo** · snake · 14 jugadores (7 titulares, 7 de banca, 1 lugar de IR).
- **Titulares:** QB, RB×2, WR×2, TE, FLEX (RB/WR/TE). **Sin K ni D/ST.**
- Puntuación = PPR estándar de ESPN (0.04/yd pase, 4 TD pase, −2 INT, 0.1/yd carrera y recepción, 6 TD, 1 por recepción, −2 fumble perdido).
- **Agencia libre:** por waivers, periodo de 1 día; la prioridad se reinicia cada semana en orden inverso a la tabla; sin límite de movimientos.
- **Intercambios:** sin límite; fecha límite 2026-12-02; periodo de revisión de 1 día; **3 votos vetan un intercambio**.
- **Temporada regular:** 12 enfrentamientos (NFL semanas 3–14). **Playoffs:** 4 equipos, primera ronda de 1 semana y final de 2.
- Mario vive en **Sídney**, así que todos los horarios de la NFL le quedan corridos (partido del jueves ≈ viernes 10:15 AM, domingo ≈ lunes 3 AM).

## Material heredado del draft (2026-09-23)

El draft se hizo con el pick 1, en vivo, en la sesión padre. Del prototipo quedó
`prototipo_draft/`. Es **desechable**: sirve de referencia, no es la base del código.

| Archivo | Qué es |
|---|---|
| `modelo.py` | v1: puntos esperados por uso (xFP) con una regresión en 2025 semana a semana (targets, acarreos, air yards; R² 0.66–0.68 en RB/WR/TE, 0.50 en QB), combinados con proyecciones de expertos mediante shrinkage bayesiano; valor sobre reemplazo para 8 equipos. |
| `modelo2.py` | v2: añade la proyección semanal de ESPN (sem 3–17, con descansos), el estado de lesiones de ESPN, ajustes de contexto hechos a mano y VOR por juegos disponibles. |
| `sim.py` | Monte Carlo de los picks rivales (0.6·log ADP + 0.4·log rank ESPN + ruido, con límites por posición) → probabilidad de que un jugador siga disponible en el siguiente turno. |
| `draft.py`, `sig.py` | Asistente interactivo y traductor de iniciales + equipo. |
| `ranking*.csv`, `estado.json` | Resultados y estado del draft. |

**Fuentes de datos gratis que ya funcionaron:**
- `nflverse-data` releases: `stats_player/stats_player_week_{2025,2026}.csv`, `snap_counts/snap_counts_2026.csv`.
- API de ESPN: `lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/...`
  - `leaguedefaults/3?view=kona_player_info` con header `X-Fantasy-Filter`: proyección por semana, lesiones, ranking, ADP y comentarios de sus analistas.
  - `leagues/898754986?view=mTeam&view=mRoster&view=mSettings&view=mMatchup`: la liga.

**Hallazgos que conviene no perder:**
1. **El rol se estabiliza rápido y la eficiencia no.** Con 2 partidos, targets, acarreos y
   porcentaje de snaps predicen mejor que los puntos. Los TD y las yardas por acarreo son ruido.
2. **El contexto que el modelo no ve decidió varios casos**, y se resolvió leyendo
   los comentarios de ESPN:
   - un QB suplente deprimió los números de un WR (London en ATL);
   - la ausencia de un compañero infló los de otro (Schultz con Collins fuera);
   - el cambio de QB titular (Winston por Dart en NYG) cambia el panorama de todos sus receptores;
   - un stinger con resonancia pendiente (Barkley).

   El sistema necesita esa capa, ya sea automatizada o en la sesión con Claude.
3. **El ranking de ESPN en la sala de draft estaba desactualizado** (parece de pretemporada)
   y **los rivales eligen por nombre**: tres QBs en los primeros 9 picks, Travis Hunter en
   el 10 con ESPN #187, y QBs de repuesto en rondas medias. Eso crea valor en los jugadores
   que ESPN subestima, y probablemente también en la agencia libre y en los intercambios.
4. **La API de ESPN guarda proyecciones semanales de 2025** (`statSourceId=1`, `seasonId=2025`)
   junto a los resultados reales. Parece que se puede usar como referencia para el requisito B,
   pero no se verificó (ver preguntas abiertas).

## Linaje

Linaje de **técnicas**, no de código. Qué se reutiliza lo decide la sesión del proyecto.
- [[analisis-apuestas-basketball]] — predicción de estadísticas por jugador, API de ESPN,
  prevención de fuga de datos verificada en tiempo de ejecución, modelos por tipo de jugador.
- [[analisis-mundial-predicciones]] — backtest con corte temporal estricto contra un modelo
  de referencia (el requisito C) y simulación Monte Carlo.

## Preguntas abiertas (para la sesión de implementación)

Están abiertas porque nadie las ha contestado. **No se rellenan con supuestos:
se le preguntan a Mario.**

**Bloque 1 — Etapa provisional (urgente: semana 4 o 5)**
*(cerrado — ver decisiones 12 a 15)*

**Bloque 2 — Validación (requisito para que el modelo mande)**
*(cerrado — ver decisiones 18 a 20)*

**Bloque 3 — Ejecución autorizada**
*(cerrado — ver decisiones 21 y 22)*

**Bloque 4 — Intercambios**
*(cerrado — ver decisiones 16 y 17)*
