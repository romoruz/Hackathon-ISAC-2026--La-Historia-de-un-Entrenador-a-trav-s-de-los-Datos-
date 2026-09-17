# ADR-59 — El informe: qué se afirma, con qué evidencia y cómo se redacta

> **BORRADOR PREINSCRITO, 2026-09-17.** Escrito después de cerrar la Fase 0
> (commit `f439688`) y **antes** de reescribir `12_reporte_html.py` y el guion
> del pitch. Se commitea solo. Integra la nota D59-P (panel 5.5,
> `PANEL_55_BORRADOR.md`, commit `f14bc71`).
>
> **Declaración de contaminación.** No es una ADR de predicciones: todos los
> resultados ya se vieron. Lo que se preinscribe es **el plan de reporte**:
> qué titulares entran, con qué intervalo, cómo se redactan los nulos y qué
> queda fuera. Fijarlo antes de escribir el HTML impide elegir, al maquetar, las
> cifras que mejor cuentan la historia.

## 1. Pregunta y protagonista

El reto pide cómo juega **un equipo bajo un entrenador**. Protagonista: **André
Jardine en el América** (100 partidos, 6 torneos, A2023–C2026). Contrapuntos del
mismo club: Ortiz (43) y Solari (25). Prueba de generalidad: los técnicos con
eras en varios clubes (ADR-57), y en particular **Jardine en Atlético San Luis
(48)**.

La pregunta que ordena el informe tiene dos partes:

1. ¿Cómo juega el América de Jardine? (5.1 a 5.5)
2. ¿Qué de eso es de Jardine y qué es del América? (el diferenciador)

## 2. Tres niveles de evidencia, que nunca se mezclan en una frase

| nivel | qué es | cómo se redacta | ejemplos |
|---|---|---|---|
| **A · probado** | contraste preinscrito, IC por bootstrap, sobrevive a BH en su familia | "difiere", con IC y q | Jardine contra Solari en duración de posesión |
| **B · medido** | diferencia contra la liga con IC, sin familia (H4 contra liga, panel D59-P) | "por encima / por debajo de la liga", con IC; nunca "significativo" | Jardine +24.6% de posesión contra la liga; field tilt +11 pp |
| **C · descriptivo** | percentiles, perfiles, roles, "lo que viaja" | "en X de Y torneos…", sin IC ni lenguaje de hallazgo | rotación del once; contraste América–San Luis |

Regla: una frase lleva **un** nivel. Si junta dos, se parte en dos.

## 3. Redacción

**Prohibido** (causal, de rendimiento o de intención):
- "el éxito de…", "gracias a…", "permite sostener…", "para sobrevivir al
  calendario", "se apoya en…", "provoca", "explica", "mejor/peor técnico".
- "firma táctica", "ADN" y cualquier metáfora que suponga un rasgo fijo del
  técnico: el propio informe muestra que el perfil cambia con el club.
- "no hay efecto". Un nulo se escribe "no detectamos una diferencia mayor a X",
  con X = el extremo del IC más lejano al cero.
- "significativo" para cualquier cifra de nivel B o C.
- "se adapta" o "impone" como hecho: solo "es compatible con…" (nivel C).
- Citas bibliográficas no verificadas contra la fuente.

**Obligatorio:**
- "Bajo Jardine, el América…" (asociación con la era), no "Jardine hace…".
- "Tras sus primeros cambios, el equipo…" (ADR-58).
- Cada cifra con su fuente (JSON y campo) y su nivel.
- Magnitudes a λ = 0 y contra la liga del mismo torneo sin el club.

**Reformulación de la tesis del Proyecto.** La frase "una rotación
excepcionalmente alta permite sostener el rendimiento frente a un calendario
saturado" es causal y además no medimos rendimiento. Se sustituye por:

> "Bajo Jardine, el América tuvo posesiones más largas y más dominio territorial
> que la liga, y al mismo tiempo cambió su once más que casi cualquier equipo.
> Las dos cosas ocurrieron juntas en los seis torneos. No medimos si una sostiene
> a la otra."

## 4. Estructura del informe HTML (una crónica, no un tablero)

Cada sección declara qué componente del reto responde.

### §1 · Cómo leer este informe (5.6)
Tres preguntas sobre cada posesión: **dónde se juega, cuánto dura y con qué
probabilidad termina en remate o gol**. Definiciones de posesión, acción,
transición, fase y cadena; la comparación contra la liga del mismo torneo y por
qué (deriva del proveedor: firma temporal 37/47 sin corregir → 23/44 corregida,
`did_h4_v1.json` › `firma_temporal`). La cadena de Markov y sus fórmulas van en
un bloque plegable.

### §2 · El América de Jardine con el balón (5.1 ofensiva)
Titulares:
- **B** Posesiones **+24.6%** más largas que la liga [+22.3, +26.9]
  (`did_h4_v1` › unidades › `rel_E_T_vs_liga`).
- **A** Más largas que con Solari: **+17.6%** [+12.7, +22.4], q = 0.001
  (`did_h4_v1` › pares › `did.E_T`).
- **Nulo A** Contra Ortiz: +3.5% [+0.1, +7.1], q = 0.056 → "no detectamos una
  diferencia que sobreviva a la corrección; si existe, es menor a 7%".
- **B** Progresión: **+3.7 pases progresivos por partido** [+1.8, +5.5]
  (`metricas_v1` › global › `prog_pases`).
- **B** Ocasiones: **+0.30 npxG por partido** [+0.12, +0.47] sobre una liga de
  1.15; OBV a favor +0.43 [+0.18, +0.70].
- **B** Dominio territorial: **field tilt +11.0 pp** [+8.0, +14.2].
- Mapa de zonas de la cadena (orientación verificada, §33.4 de 10).

### §3 · El América de Jardine sin el balón (5.1 defensiva)
- **B** Concede **−0.32 npxG por partido** [−0.42, −0.22].
- **Nulo A** Presión contra Ortiz: nivel −2.0 pp [−4.2, +0.3], E2 sin rechazo →
  "no detectamos una diferencia de nivel de presión mayor a 4.2 pp".
- **Nulo A** Contra Solari: +3.3 pp [+0.3, +6.1], q = 0.30 → no sobrevive a BH.
- **A** Lo que el método sí detecta en el mismo club: Ortiz presiona más que
  Solari, +5.2 pp [+2.0, +8.4], q = 0.041 (`did_presion_v1`).
- Transiciones: E4 (posesiones rivales de una acción en juego abierto) como
  proxy declarado; sin transiciones en segundos (límite de §10).

### §4 · ¿Se sostiene en el tiempo? (5.2 consistencia)
- **B** Posesión sobre la liga en los seis torneos: +38.2, +21.3, +18.3, +24.2,
  +16.3, +30.1% (`did_h4_v1` › `serie_por_torneo`).
- **C** Field tilt entre el percentil 0.82 y 1.00 de la liga en los seis
  torneos; npxG entre 0.65 y 1.00 en los cinco primeros y **0.18 en C2026**
  (`metricas_v1` › por_torneo). Se redacta como evolución, sin explicarla.

### §5 · ¿Ajusta al contexto? (5.2 variabilidad)
- **B** Lo que ajusta la liga: perdiendo contra ganando, localía, minuto 60 y
  rival (tabla de ADR-56).
- **Nulo A** El América ajusta como la liga: 0 de 48 contrastes sobreviven a BH.
  Tres intervalos de Jardine excluyen el cero antes de corregir (marcador ·
  remate concedido −2.7 pp; minuto 60 · remate +2.1 pp; rival · presión
  −3.6 pp) y se muestran como tales, marcados "no sobrevive".
- Márgenes: cada nulo con su extremo de IC (bosque de θ).

### §6 · El plantel (5.3)
- **C** Rotación: continuidad del once en el 15% inferior de la liga en **6 de
  6** torneos; N80 alto en 5 de 6 (`jugadores_v1` › A). Confusor declarado:
  competiciones fuera de los datos.
- **C** Roles: los cinco jugadores con más minutos, posición y zona (B).
- **Nulo A** Tras el primer cambio táctico: nada detectable. Remate
  +3.7 pp [−0.8, +8.3]; field tilt +1.7 pp [−7.4, +10.5]. Liga, perdiendo:
  remate +2.2 pp y field tilt +8.7 pp tras el cambio.

### §7 · Balón parado (5.4)
- **B** Embudo de la liga: P(remate | córner) 0.396, tiro libre 0.209, banda
  0.140; P(gol | córner) 0.033.
- **B** Cabeza y distancia; geometría del remate (`goal_open` 0.662 en córner
  contra 0.776 en juego abierto); ΔAUC +0.026 [+0.015, +0.038].
- **Nulo A** El América no se separa de la liga en córners: Jardine ofensivo
  +0.3 pp [−4.1, +4.6], defensivo −2.6 pp [−6.8, +1.8].
- Zonas de remate a favor y en contra (vulnerabilidad).

### §8 · ¿Qué es de Jardine y qué del América? (el diferenciador)

| era | posesión vs liga | field tilt | npxG a favor | continuidad del once (torneos en el 15% inferior) |
|---|---|---|---|---|
| Jardine · América | **B** +24.6% | **B** +11.0 pp [+8.0, +14.2] | **B** +0.30 [+0.12, +0.47] | **C** 6 de 6 |
| Jardine · San Luis | **B** −10.0% [−12.2, −7.7] | **B** −7.6 pp [−12.3, −3.2] | **B** −0.15 [−0.33, +0.02] | **C** 0 de 3 |
| Ortiz · América | **B** +20.3% [+16.9, +23.7] | **B** +11.1 pp [+6.9, +15.0] | **B** +0.41 [+0.22, +0.60] | **C** 1 de 2 |
| Ortiz · Monterrey | **B** +16.2% [+12.7, +19.6] | **B** +3.8 pp [−0.8, +8.2] | **B** −0.04 [−0.22, +0.15] | **C** 1 de 2 |

Lectura preinscrita, **nivel C**:
- En el América, los dos técnicos muestran el mismo perfil: posesión larga y
  dominio territorial.
- Fuera del América, **el perfil de Jardine se invierte** en las tres métricas.
  **Ortiz conserva la posesión larga** y pierde casi todo el dominio territorial.
- Lo que viaja depende del técnico y de la métrica; el dominio territorial
  parece más del contexto América que de quien lo dirige.
- **No separa plantel, presupuesto y calendario**: los tres cambian con el club.
  Con dos técnicos no hay regla.
- La tabla de los nueve técnicos con varios clubes (ADR-57, P1: 3 de 9
  mantienen el ajuste al marcador) se muestra como apoyo, también nivel C.

**No se dice** que "la calidad del plantel domina sobre el entrenador": ni se
midió el plantel ni el rendimiento.

### §9 · ¿El método distingue de verdad? (credibilidad)
- **Bosque crudo contra corregido**: duración de posesión (47 → 44 pares que
  rechazan; 15 cambian de signo) y presión (24 → 6 contrastes; 20 cambian de
  veredicto).
- **Marcador de predicciones preinscritas**: 20 de 26, con los seis fallos a la
  vista (ADR-53 4/4, 54 2/4, 55 5/7, 56 5/6, 57 0/1, 58 4/4). D59-P no tiene
  predicciones.
- Los 20 bugs silenciosos, en anexo.

### §10 · Framework y límites (5.6)
Definiciones completas; supuestos; lo que no captura:
- Markov rechazado en longitudes (y en balón parado, ADR-55 P5).
- Sin tiempo en segundos: transiciones y contragolpes solo por proxy.
- Sin 360 posicional: organización defensiva por proxy.
- Competiciones fuera de los datos.
- Fronteras de era con error de ±1 partido.
- Nada causal.

**Simulación (componente 06, opcional): no se incluye.** Simular desde una
cadena con la distribución de longitud rechazada propagaría el sesgo (ADR-21).

## 5. Figuras (mínimas)

1. Tres preguntas de la posesión (esquema, §1).
2. Mapa de zonas del América de Jardine (§2).
3. Bosque de pares del América, crudo contra corregido (§2, §9).
4. Serie por torneo: posesión y field tilt contra la liga (§4).
5. Bosque de θ de contexto del América (§5).
6. Percentiles de continuidad y N80 por torneo (§6).
7. Embudo de balón parado y curva cabeza/pie (§7).
8. Tabla-figura América contra San Luis (§8).
9. Marcador de predicciones (§9).

## 6. Verificación antes de publicar

- Toda cifra del HTML se genera desde los JSON; ninguna se teclea.
- `verifica_reporte.py` y `humo_reporte.py` en verde.
- Un test que recorra el texto generado y falle con cualquier frase de la lista
  prohibida de §3.
- Los JSON de `reports/` no se versionan: el informe declara el commit del
  código y la fecha de cada corrida.
