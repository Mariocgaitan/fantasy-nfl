# Reporte claro: "Qué hacer" con urgencia — diseño

Fecha: 2026-10-02. Rama: `reporte-claro`. Aprobado por Mario en la sesión (diseño en dos partes).

## Problema

El reporte del viernes 2026-10-02 no se entendía:

1. No dice qué hacer hoy: hay que deducirlo de cinco tablas.
2. "Ganancia" suma toda la temporada (+8.1 parece mucho y son 0.6 puntos por semana).
3. No muestra la banca ni los lugares libres (Mario tenía 13 de 14 y el reporte no lo decía).
4. "Sin respaldo útil" no explica por qué.
5. "Ganando rol" no explica Snaps / Oport. / Dueños %, ni dice si el jugador está libre en la liga.
6. La columna "Modelo" y el sello "SIN VALIDAR" meten ruido.

Y el más importante: **el reporte y la sesión no coincidían.** En la sesión se recomendó pedir a
J.K. Dobbins con el lugar libre (respaldo de RB y moneda de cambio); el reporte proponía soltar a
Young por Daniels (lesionado, +0.6 por semana). El reporte solo busca cambios pedir/soltar que
suben los puntos propios: no ve lugares vacíos ni el valor de un jugador para los rivales.

## Objetivo

Que el reporte diga lo mismo que la sesión y que cada cosa diga si es urgente o recomendación.
Mario lee **la página** (no el correo), no conoce la NFL y quiere saber qué hacer y antes de qué
hora.

## Decisiones de la sesión

- **Tres niveles de urgencia** (🔴 antes de [día hora] / 🟡 recomendado / ⚪ en el radar).
- **Lugar vacío, regla 3:** si un titular no tiene respaldo útil, primero respaldo; si no, moneda
  de cambio.
- **El correo solo avisa** ("Reporte del viernes: 1 urgente, 2 recomendadas" + enlace).
- **Ganando rol incluye la banca de los rivales** como objetivo de intercambio (comprar barato
  antes de que exploten).
- **Sincronía:** en la sesión se corre este mismo cálculo; si la sesión recomienda algo distinto,
  se dice por qué (error del reporte o algo que el reporte no sabe) y se anota.

## Arquitectura

Módulo nuevo `src/fantasy/decision/acciones.py`: recibe lo que ya calcula `armado.armar`
(alineación, reemplazos, agencia libre, intercambios, ganando rol) más lo nuevo (lugar vacío) y
devuelve una lista de `Accion`, ordenada por urgencia y hora límite:

```python
@dataclass(frozen=True)
class Accion:
    urgencia: str          # "urgente" | "recomendado" | "radar"
    texto: str             # qué hacer, en una línea ("Pide a J.K. Dobbins (RB)")
    porque: str            # por qué, en una línea
    limite: pd.Timestamp | None  # hora límite (UTC); se muestra en Sídney
    tipo: str              # "alineacion" | "inactivo" | "pedir" | "lugar" | "agencia" |
                           # "intercambio" | "rol"
```

`armado.Reporte` gana `acciones: list[Accion]`, `plantilla: list[dict]` (titulares, banca y
lugares libres) y `tope: int`. La lógica de urgencia vive solo en `acciones.py` (sin pandas
pesado; recibe lo ya calculado) y se prueba sin la página.

No se toca el código del modelo (`modelo/`, `ingesta/historico.py`): la validación en vivo sigue
intacta. La columna "Modelo" deja de mostrarse, pero `armado` la sigue calculando (sin cambios en
`prediccion_modelo`).

## Reglas de urgencia

Constante `GANANCIA_SEMANAL_MIN = 1.0` (puntos por semana). Semanas restantes =
`SEMANA_FINAL − semana + 1`. Ganancia semanal = ganancia total / semanas restantes.

### 🔴 Urgente (pierdes puntos esta semana si no actúas)

1. **Alineación no óptima** (`cambios` no vacío): "Mete a X de titular por Y". Límite: el inicio
   del primer partido entre los jugadores que cambian.
2. **Titular en duda con suplente:** si un titular de la alineación óptima está QUESTIONABLE o
   DOUBTFUL y tiene suplente en `reemplazos`: "Si X queda fuera, mete a Y". Límite: inicio del
   partido de X. (Los que están OUT/IR ya los saca la alineación óptima → regla 1.)
3. **Titular fuera sin reemplazo:** titular con p_jugar = 0 y sin suplente → pedir al mejor libre
   sano de su posición que juegue esta semana a la misma hora o después. Texto según
   disponibilidad:
   - `LIBRE`: "Pide a X (libre, entra al instante)". Límite: inicio del partido del titular.
   - `WAIVERS`: "Pide a X antes del [día] 17:00 (waivers)". Límite: próximo proceso de waivers
     (17:00 Sídney, todos los días menos martes) que sea antes del partido; si ninguno lo es, se
     busca un libre `LIBRE`.
   Si la plantilla está llena, el texto dice a quién soltar (el de menor proyección de aquí al
   final que no sea intocable ni esté bloqueado).

### 🟡 Recomendado

4. **Lugar vacío** (plantilla < `tope` = 14), regla 3:
   - **Respaldo** si algún titular no tiene respaldo útil (`reemplazos` sin suplente): se pide al
     libre sano que lo cubriría (posición elegible para ese lugar y que juega esta semana a la
     misma hora que el titular o después), el de más proyección de aquí al final; empate → más
     valor para los rivales. Porque: "X no tiene quien lo cubra si queda fuera". Si ningún libre
     cumple, se pasa a moneda de cambio.
   - **Moneda de cambio** si no hace falta respaldo: el libre sano con mayor suma de mejoras
     positivas a las alineaciones de los rivales (de aquí al final, con `Valuador`), como se
     calculó en la sesión. Porque: "le sirve a [rival] (+N) para un intercambio".
   - Una acción por cada lugar libre (con 2 libres, 2 acciones; la segunda no repite jugador y
     se recalcula con el primero ya agregado).
5. **Agencia libre** con ganancia semanal ≥ 1.0: "Pide a X, suelta a Y (+N por semana)". Solo la
   mejor por posición.
6. **Intercambios** (solo martes): cada propuesta es una acción 🟡 con "propón uno a la vez" y el
   riesgo de veto.

### ⚪ En el radar

7. **Agencia libre** con ganancia semanal < 1.0: una sola línea con la mejor ("el mejor cambio
   gana +0.6 por semana: no vale la pena").
8. **Ganando rol:**
   - Libres (`LIBRE`/`WAIVERS`): "X (WR) está ganando rol y está libre: pídelo si se abre un
     lugar".
   - **En la banca de un rival** (nuevo): "X (RB), banca de [rival]: objetivo para el próximo
     intercambio". Los titulares de rivales no se incluyen.

Si no hay 🔴 ni 🟡: el bloque dice **"Nada que hacer hoy."**

## Lugares vacíos y respaldo: detalle

- `tope` = suma de cupos de titulares + banca de la liga (hoy 14; se lee de
  `settings.rosterSettings.lineupSlotCounts`, sin contar IR). Lugares libres = `tope` − jugadores
  fuera de IR.
- "Respaldo útil" usa `alineacion.reemplazos` (misma posición elegible y juega a la misma hora o
  después). `reemplazos` gana el motivo cuando no hay suplente: `"sin_posicion"` (no hay nadie
  de esa posición en la banca) o `"horario"` (los hay, pero juegan antes).
- El valor para los rivales se calcula con `Valuador` sobre las tablas de aquí al final, igual
  que el análisis de la sesión: para cada libre sano (top 40 por proyección), suma de
  `max(0, valor(plantilla_rival ∪ {libre}) − valor(plantilla_rival))` sobre los rivales.

## Ganando rol: cambio

`agencia_libre.ganando_rol` hoy descarta a todo el que tiene dueño. Pasa a devolver también a
los que están en la **banca** de un rival (slot BANCA, no IR), con una columna nueva
`dueno` (nombre del equipo o vacío si libre). Mis propios jugadores siguen fuera.

## La página

Orden:

1. **Encabezado:** "BanKAI · semana 4 · reporte del viernes · generado vie 09:23".
2. **Qué hacer:** 🔴 / 🟡 / ⚪, cada acción con texto, porqué y límite en hora de Sídney
   ("antes del sáb 17:00"). "Nada que hacer hoy" si aplica.
3. **Tu plantilla:** titulares (lugar, jugador, posición, puntos esperados, estado, hora del
   partido), banca y "lugares libres: 1 de 14".
4. **Si alguien queda fuera:** titular → quién entra; si no hay, el motivo: "no tienes RB en la
   banca" o "tus suplentes juegan antes que él".
5. **Agencia libre:** pedir / soltar / ganancia **por semana**.
6. **Intercambios** (martes): como hoy, con ganancia por semana.
7. **Ganando rol:** jugador, dónde está (libre / banca de [rival]), snaps, oportunidades, dueños %;
   con una línea que explica cada columna:
   - Snaps: % de las jugadas de ataque de su equipo en que estuvo en la cancha (antes → ahora).
   - Oport.: veces por partido que el balón fue para él (pases + carreras).
   - Dueños %: % de ligas de ESPN en el mundo que lo tienen (bajo = el mercado no lo ha notado).
8. **Pie:** "Decide la proyección de ESPN." y los avisos.

Sin la columna "Modelo" ni el sello "SIN VALIDAR". Si el modelo llega a validarse, el pie dice
"Decide el modelo validado."

## El correo

`correo.resumen` pasa a una línea de conteo más las acciones 🔴 (si hay):

```
Reporte del viernes (semana 4): 1 urgente, 2 recomendadas.
🔴 Mete a X de titular por Y — antes del lun 04:00
```

más el enlace. Sin 🔴 ni 🟡: "Reporte del viernes (semana 4): nada que hacer."

## Pruebas

- `acciones`: cada regla con casos chicos armados a mano (alineación no óptima → 🔴 con el límite
  del primer partido; titular OUT sin suplente → 🔴 pedir libre / waivers con su hora; lugar
  vacío con titular sin RB de respaldo → 🟡 respaldo RB; lugar vacío sin faltantes → 🟡 moneda de
  cambio; agencia +0.6/semana → ⚪; agencia +1.2/semana → 🟡; sin nada → "Nada que hacer hoy").
- `reemplazos` devuelve el motivo `sin_posicion` / `horario`.
- `ganando_rol` incluye a un jugador en la banca de un rival y excluye a titulares rivales y a los
  míos.
- Reporte real del viernes (fixture nuevo `sem04_2026-10-02`, la instantánea de la rama `datos`):
  el lugar vacío pide un respaldo para un titular sin respaldo (Gibbs, Jeanty o Amon-Ra) y
  Daniels por Young no sale como 🟡.
- Correo: el conteo por urgencia y "nada que hacer".
- Las pruebas existentes del HTML se ajustan a la nueva estructura.

## Fuera de alcance

- Ejecutar en ESPN (fase 2).
- Cambiar el modelo o su validación.
- Noticias de último minuto que no estén en los datos de ESPN.
