# 19 — Traspaso de cierre: lo que se hizo, dónde está y qué falta para el entregable

> Escrito el 2026-09-17, al final de la sesión que migró el proyecto al API y
> corrió ADR-53 a ADR-58. **Es el documento con el que arranca el próximo
> chat.** Vive en `docs/traspaso/` (fuera del alcance de `verificar_docs.py`,
> porque cita ADR-58 y ADR-59, que aún no están en `06_DECISIONS.md`).
>
> **Regla para quien lo lea (persona o IA):** toda cifra de este documento
> salió de una salida de terminal pegada en la sesión. Antes de citarla en el
> informe, **verifícala contra su JSON** (la fuente va en cada tabla).

---

## 0. Resumen en cinco líneas

1. El proyecto corre sobre el **API de Hudl StatsBomb**: Liga MX, fase regular,
   10 torneos (A2021 a C2026), 18 clubes, **1,524 partidos** en el universo y
   **53 eras** de entrenador analizables.
2. Toda comparación es **contra la liga del mismo torneo, sin el club**, porque
   el proveedor cambió su anotación durante la ventana (ADR-53).
3. Se corrieron seis análisis preinscritos: **H4** (duración de la posesión),
   **D1** (presión), **balón parado**, **contexto**, **casos** y **jugadores**.
   Cada uno tuvo su ADR commiteada **antes** del código.
4. **Protagonista: André Jardine (América).** Contrapuntos: Ortiz y Solari.
   Prueba de generalidad: 9 técnicos con eras en varios clubes (ADR-57).
5. **Falta**: documentar ADR-58, tres verificaciones técnicas (sección 7) y
   **el entregable** (ADR-59): reescribir `reporte.html` y la portada.

---

## 1. El reto (lo que califica el jurado)

Enunciado: *"La historia de un entrenador a través de los datos"* (ISAC 2026).
Pregunta central: principios en fase ofensiva y defensiva, cómo se
manifiestan en el tiempo y **cómo ajusta el entrenador según el contexto**
(rival, marcador, localía, momento). Componentes: 5.1 estilo (ofensiva y
defensiva), 5.2 consistencia y contexto, 5.3 uso de jugadores, 5.4 balón
parado, 5.5 evidencia cuantitativa (xG, OBV, pases progresivos, presión,
*field tilt*, métricas propias), 5.6 framework analítico. Entrega a fines de
noviembre. **Principio: alguien que no vio los partidos debe entender cómo
juega el equipo.**

| componente | estado | dónde |
|---|---|---|
| 5.1 ofensiva | ✅ | ADR-53 (`did_h4_v1.json`) |
| 5.1 defensiva (presión) | ✅ · orientación de zonas por verificar | ADR-54 (`did_presion_v1.json`) |
| 5.2 contexto | ✅ | ADR-56 (`contexto_v1.json`) |
| 5.3 jugadores | ✅ · falta documentar | ADR-58 (`jugadores_v1.json`) |
| 5.4 balón parado | ✅ | ADR-55 (`balon_parado_v1.json`, `balon_parado_v2.json`) |
| 5.5 métricas del proveedor | 🟡 xG y *field tilt* usados; falta un panel descriptivo por era | sección 7 |
| 5.6 framework | ✅ en `docs/`; **falta llevarlo al entregable** | ADR-59 |
| entregable | ❌ | ADR-59 |

---

## 2. Arquitectura nueva (scripts 30 a 38)

```
data/processed_api_<club>/   18 directorios (phase0 por club, min_actions_defense = 1)
data/prior_liga/             artefacto de liga (min_actions = 2): SOLO prior y ADR-53
data/api/eventos_api_ligamx/ eventos del API (184 columnas; location y freeze frame como JSON)
data/raw_api/indice_partidos.csv   local/visitante, fecha, etapa
data/raw_api/lineups/        alineaciones (positions con reloj ACUMULADO)
        │
        ├─ 30_did_contemporaneo.py  ADR-53  → reports/did_h4_v1.json
        ├─ 33_did_presion.py        ADR-54  → reports/did_presion_v1.json
        ├─ 35_balon_parado.py       ADR-55  → reports/balon_parado_v1.json (ADR-52)
        │                                    reports/balon_parado_v2.json (+ familia casos)
        ├─ 36_contexto.py           ADR-56/57 → reports/contexto_v1.json
        ├─ 38_jugadores.py          ADR-58  → reports/jugadores_v1.json
        ├─ 31_backfill_club.py      rellena `club` en ic_* y plantel_*
        ├─ 32_docs_adr53.py         documentación de ADR-53 (motor de reemplazos)
        ├─ 37_docs_resultados.py    documentación de ADR-54 a 57 (reusa 32)
        └─ 34_sonda_*.py            sondas de solo lectura (cierre, vista defensora,
                                    contexto, alineaciones) → reports/sonda_*.txt
```

**Piezas comunes (una sola ruta para cada cosa):**
- `derivadas` de `08` (E[T], P(gol), P(remate) con α).
- `p_basic`, `ic_basic`, `semilla`, `normaliza_filas` de `30`.
- `partidos_completos` de `33`.
- `casos_desde`, `invierte_marcador` de `36`.
- `torneo_cols` de `24`: etiqueta **y** orden cronológico. **No** la de `25`,
  que solo da la etiqueta.

**Vista defensora (D54-10).** La unión, sobre los 18 directorios, de las filas
con `team != club`. Cada acción aparece una sola vez, en el directorio de
quien defiende, con `min_actions_defense = 1`. Es la fuente de D1, balón
parado (cadena), contexto y jugadores.

**Universo (D54-12).** Los partidos con sus dos lados en la vista: **1,524**.
Salen 3919090, 3972016, 3972023, 3972072, 3972119 y 4038911, partidos de
interinos absorbidos (`eras_api/absorbidos.csv`).

**Inferencia, igual en todos.**
- Bootstrap **por partido**; la base se remuestrea estratificada por torneo y
  se comparte dentro del club.
- IC basic; p por inversión del IC.
- BH al 5% por familia.
- B = 4000 (H4), 6000 (D1, balón parado, jugadores), 16,000 (contexto).
- Cada script avisa si el piso del p (2/(B+1)) supera α/m.

**Familias.**
- **ADR-52**: las 21 eras de América, León, Atlas, Atlético San Luis,
  Monterrey y Cruz Azul.
- **Casos** (ADR-57): 24 eras.

---

## 3. Registro de preinscripciones (git)

| commit | qué |
|---|---|
| `2af2ab2` | ADR-54 preinscrita (D1) |
| `3574966` | ADR-53 con resultados, bug #19 |
| `9aa5524` | ADR-54 adenda 1 (vista defensora, bug #20) y ADR-55 preinscrita |
| `599a395` | ADR-54 adenda 2 (universo de partidos completos) |
| `1e68467` | ADR-55 adenda 1 (S₁₀ y S_fase exploratorios, bug #21) |
| `8eee7ef` | ADR-56 preinscrita (contexto) |
| `f23b125` | ADR-57 preinscrita (casos) |
| `c5cb96c` | ADR-56 adenda 1 (B = 16,000) |
| `827ec4b` | ADR-54 a 57 con resultados en `06` y `10`; bugs #20 y #21 |
| `db715ef` | ADR-58 preinscrita (jugadores) |

Los borradores están en `docs/preinscritos/`. **ADR-58 con resultados no está
todavía en `06_DECISIONS.md`**, y `38_jugadores.py` y su test no están
commiteados (sección 7).

**Bugs.** Veinte encontrados, numerados hasta el #21 (el #13 se evitó):
- **#19**: la línea base de H4 no entraba en el contraste.
- **#20**: la base de D1 truncaba distinto que la unidad (`min_actions`).
- **#21**: el freeze frame del API es JSON y `xg_remate.features` devolvía
  `None` en silencio.

Todos fueron silenciosos.

---

## 4. Resultados, con su fuente

### 4.1 H4 · duración de la posesión (ADR-53, `did_h4_v1.json`)

60 pares, 53 eras. Rechazan 44 corregidos contra 47 crudos. **15 cambian de
signo al corregir.** Firma temporal (el entrenador posterior tiene posesiones
más largas): crudo 37/47, corregido 23/44. **Predicciones: 4/4.** Ningún par
demuestra equivalencia al 3%; el menor margen demostrable es 4.02% (Toluca,
Mohamed–Paiva).

| par | crudo | corregido | IC 95% | q |
|---|---|---|---|---|
| Jardine vs Solari | +31.42% | **+17.59%** | [+12.70, +22.43] | 0.0010 |
| Ortiz vs Solari | +16.50% | **+13.57%** | [+8.18, +18.71] | 0.0010 |
| Jardine vs Ortiz | +12.81% | +3.54% | [+0.12, +7.05] | 0.0562 (no) |
| Cocca I vs Cocca II | −7.01% | **+4.89%** (signo invertido) | [+0.45, +9.62] | 0.0389 |
| Berizzo vs Larcamón | +0.13% | **−7.02%** | [−10.75, −3.19] | 0.0010 |

**Desviación contra la liga del mismo torneo** (E[T], eras del América):
Jardine +24.56% [+22.32, +26.88] · Ortiz +20.29% · Solari +5.92%. Jardine en
San Luis: −9.96%. Ortiz en Monterrey: +16.17%.

**Lectura**: Jardine sostiene la posesión más que Solari y más que la liga. No
detectamos que la sostenga más que Ortiz.

### 4.2 D1 · presión (ADR-54, `did_presion_v1.json`)

27 pares, 135 contrastes. Rechazan **6** corregidos contra **24** crudos. 20
cambian de veredicto. **Predicciones: 2/4** (fallan P1, firma temporal, y P3,
Cocca; P2 está contaminada, declarado).

Sobreviven:
- **América, Ortiz vs Solari**: E1 geografía y E2 nivel en k ≥ 3, **+5.21 pp**
  (Ortiz presiona más). Etapa 2: zonas 3 y 6.
- **Cruz Azul, Reynoso vs Anselmi**: E1 y E2, **−9.60 pp** (Anselmi presiona
  más), en 13 zonas.
- **Cruz Azul, Reynoso vs Larcamón**: E1 y E2, **−7.71 pp**, en 10 zonas.

**Jardine no difiere de forma detectable de Ortiz ni de Solari** en ningún
contraste de presión. Antes de redactar dónde presiona alguien, hay que
verificar la orientación de las zonas (sección 7).

### 4.3 Balón parado (ADR-55, `balon_parado_v1.json` y `v2.json`)

| cantidad (liga) | valor |
|---|---|
| secuencias: córner / tiro libre indirecto / banda | 14,859 / 14,330 / 23,547 |
| P(remate \| secuencia): córner / TL / banda | **0.396** / 0.209 / 0.140 |
| P(gol \| secuencia): córner / TL / banda | 0.0334 / 0.0197 / 0.0107 |
| córner, remate en los primeros 10 s (exploratorio) | 0.335 |
| córner, remate dentro de la fase del proveedor (exploratorio) | 0.381 |
| cadena, posesión de córner: P(remate) / P(gol) / E[T] | 0.199 / 0.0170 / 2.17 |
| P(remate) empírica por posesión · producto de las dos capas | 0.385 · 0.030 |
| modelo: remates / goles | 9,850 / 775 |
| AUC: base / con geometría / StatsBomb | 0.744 / **0.770** / 0.775 |
| ΔAUC por geometría | **+0.026 [+0.015, +0.038]** |
| β cabeza (estandarizado) | **−0.444 [−0.525, −0.367]** |
| con interacción: cabeza / distancia × cabeza | +0.066 / **−0.612** |
| `goal_open`: córner / juego abierto | **0.662 / 0.776** |

**Predicciones: 5/7.** Falla P2 (0.396 fuera de [0.18, 0.30]). Falla P5: la
cadena subestima el peligro del balón parado a la mitad, que es el rechazo de
Markov de §7.1.

**Familias.** ADR-52: 0/84. Casos: 2/96.
- Mora (Querétaro), C2 ofensivo: 0.057 contra 0.086 xG por remate, q = 0.016.
- Ambriz (Santos), C1 defensivo: 53.4% contra 38.5% de remate concedido,
  q = 0.016.

**Lecturas.**
- Un cabezazo cerca del arco vale lo que un remate con el pie; lejos vale
  mucho menos.
- La foto del remate (freeze frame) mejora el modelo y lo deja casi a la par
  del xG del proveedor.
- Ningún técnico del América se separa de la liga en córners.

### 4.4 Contexto (ADR-56, `contexto_v1.json`)

**La liga ajusta** (A contra B):

| contexto | acciones/posesión | P(remate) | presión (defensa) |
|---|---|---|---|
| perdiendo vs ganando | 5.86 vs 5.05 | 12.6% vs 10.7% | 23.1% vs 20.0% |
| local vs visitante | 5.70 vs 5.36 | 12.5% vs 10.5% | 22.0% vs 21.0% |
| min ≥ 60 vs < 60 | 5.22 vs 5.70 | 12.6% vs 10.9% | 21.4% vs 21.5% |
| rival fuerte vs débil | 5.30 vs 5.77 | 10.5% vs 12.4% | 20.7% vs 21.9% |
| perdiendo vs ganando, min ≥ 60 | 5.75 vs 4.77 | 13.6% vs 11.0% | 23.4% vs 19.8% |

**Las eras casi no se separan de ese ajuste**: 1/336 (ADR-52) y 0/384
(casos). El único rechazo: Abascal (San Luis), localía · P(remate),
−4.74 pp [−6.97, −2.32], q = 0.042. **Predicciones: 5/6** (falla P6).

**América.** Ninguno de los 48 contrastes sobrevive a BH; seis intervalos
excluyen el cero **antes** de corregir:
- Jardine: marcador · P(remate) concedido −2.70 pp; momento · P(remate)
  +2.05 pp; rival · presión −3.62 pp.
- Ortiz: localía · acciones +0.84; marcador · presión −4.76 pp.
- Solari: rival · acciones −1.48.

Frase correcta: *"ningún técnico del América ajusta al contexto de forma
detectablemente distinta a la liga"*.

### 4.5 Casos (ADR-57)

Jardine (América, San Luis) · Ortiz (América, Monterrey) · Solari ·
Larcamón (Cruz Azul, León, Puebla) · Herrera (Tigres, Tijuana) · Torrent
(San Luis, Monterrey) · Vucetich (Mazatlán, Monterrey) · Ambriz (Santos,
Toluca) · Fentanes (Necaxa, Santos) · Paunovic (Guadalajara, Tigres) · Mora
(Atlas, Querétaro) · San José (Atlas, Mazatlán).

**P1: 3/9 falla.** Solo Mora, Paunovic y Vucetich mantienen el signo del
ajuste al marcador. El script imprimió 5/11 porque incluyó a Jardine y a
Ortiz; la documentación lo corrige. **El ajuste al marcador no viaja con el
entrenador en la mayoría.**

Lo que viaja en E[T] es **descriptivo**. Ejemplos: Jardine +24.6% en América
y −10.0% en San Luis; Herrera +18.3% en Tigres y −12.8% en Tijuana.

### 4.6 Jugadores (ADR-58, `jugadores_v1.json`) — falta documentar

Diagnóstico: reloj de `positions` **acumulado**; 1,524 partidos con
alineación; 1,859 primeros cambios tácticos y 325 por lesión en la franja.

**C · tras el primer cambio táctico.** 0/84 y 0/96. **Predicciones 4/4**:
- en la liga, perdiendo, tras el cambio: **+2.15 pp** de P(remate) (n = 448) y
  **+8.68 pp** de *field tilt* (n = 449);
- tras un cambio por lesión, |Δ| = 0.72 pp (n = 66).

Jardine: acciones +0.51 [−0.46, +1.49]; P(remate) +3.73 pp [−0.76, +8.27];
P(remate) concedido −2.25 pp; *field tilt* +1.65 pp. Nada detectable.

**A · rotación (descriptivo, percentil en la liga del torneo):**

| era | torneo | N80 (pct) | continuidad del once (pct) | jugadores distintos (pct) | cambios tácticos/partido (pct) |
|---|---|---|---|---|---|
| Jardine | A2023 | 15 (0.82) | 0.61 (**0.00**) | 30 (0.85) | 1.35 (0.03) |
| Jardine | C2024 | 15 (0.76) | 0.53 (**0.00**) | 27 (0.68) | 1.82 (0.29) |
| Jardine | A2024 | 16 (0.97) | 0.70 (**0.15**) | 32 (0.94) | 2.18 (0.76) |
| Jardine | C2025 | 14 (0.44) | 0.66 (**0.12**) | 27 (0.62) | 2.00 (0.50) |
| Jardine | A2025 | 14 (0.74) | 0.68 (**0.06**) | 25 (0.32) | 1.53 (0.15) |
| Jardine | C2026 | 16 (0.94) | 0.68 (**0.12**) | 27 (0.74) | 1.82 (0.44) |
| Ortiz | A2022 | 12 (0.32) | 0.74 (0.09) | 27 (0.97) | 1.24 (0.06) |
| Ortiz | C2023 | 14 (0.88) | 0.86 (**0.91**) | 23 (0.09) | 0.82 (0.00) |
| Solari | A2021 | 15 (0.91) | 0.64 (**0.00**) | 27 (0.68) | 0.65 (0.00) |

(C2022 de Ortiz y de Solari son parciales, fuera del percentil.)

**Lectura correcta.** El percentil de continuidad **bajo** significa que el
once cambia **más** que en casi toda la liga. **Jardine cambia su once titular
más que casi todos los equipos en sus seis torneos**, y reparte minutos entre
más jugadores (N80 alto en cinco de seis). Ortiz en C2023 es lo contrario:
un once casi fijo.

**Confusor a declarar**: el América juega competiciones que no están en los
datos (Concachampions, Leagues Cup), y el calendario cargado empuja a rotar.

Los jugadores con más minutos bajo Jardine: portero, central derecho, medio
defensivo izquierdo, extremo derecho y lateral derecho.

---

## 5. Lo que ya NO se puede afirmar (retirados y prohibidos)

- Todo lo del volcado anterior y las eras previas al bug #14 (la portada ya lo
  marca 🔴).
- **"Jardine sostiene más que Ortiz"**: no sobrevive (q = 0.056).
- **"Un técnico difiere de sí mismo"** contado con el signo del crudo (Cocca).
- **Berizzo–Larcamón como par nulo.**
- Cualquier afirmación causal ("sus cambios provocan…", "su éxito se debe a…").
- **"Heredó y estabilizó la presión"**: los datos solo dicen que no
  detectamos diferencias.
- Citas no verificadas (Casal, Lucey, Rathke, Myers…).
- Magnitudes crudas en lugar de las corregidas.

---

## 6. El entregable (ADR-59): qué debe mostrar y en qué cambia

### 6.1 Diferencias con el reporte anterior

| antes | ahora |
|---|---|
| volcado viejo, 2 clubes, eras con el bug #14 | API, 18 clubes, 53 eras, eras verificadas |
| comparación contra otras eras del club | **contra la liga del mismo torneo** (deriva fuera) |
| insumos en `reports/_pre_api` | `did_h4_v1`, `did_presion_v1`, `balon_parado_v2`, `contexto_v1`, `jugadores_v1` |
| sin contexto, jugadores ni balón parado | secciones propias para 5.2, 5.3 y 5.4 |
| titulares con efectos grandes | titulares con su IC, **y los nulos redactados con su margen** |
| sin preinscripción visible | **marcador de predicciones** (aciertos y fallos) |
| demo pública con datos sintéticos | el real va a los organizadores; la demo sigue sintética |

### 6.2 Estructura propuesta (una crónica, no un tablero)

1. **La pregunta y el instrumento.** Qué es una posesión, la cadena, E[T], xT;
   por qué se compara contra la liga del mismo torneo (la deriva, con la
   figura de la firma temporal: 37/47 → 23/44).
2. **Jardine con el balón (5.1).** Posesión más larga que la liga
   (+24.6%) y que Solari (+17.6%); indistinguible de Ortiz.
3. **Jardine sin el balón (5.1).** Presión indistinguible de la de sus
   predecesores. Cruz Azul (Anselmi) como ejemplo de lo que sí se detecta.
4. **¿Se sostiene en el tiempo? (5.2).** La serie por torneo de la desviación
   contra la liga (en `did_h4_v1.json`, campo `serie_por_torneo`).
5. **¿Ajusta al contexto? (5.2).** Lo que ajusta la liga (tabla 4.4) y que el
   América ajusta como la liga. Márgenes por contraste.
6. **El plantel (5.3).** Rotación: continuidad baja y N80 alto en los seis
   torneos, con el confusor del calendario. Lo que pasa tras los cambios: la
   liga sube su remate y su *field tilt* cuando pierde; el América, como la
   liga.
7. **Balón parado (5.4).** Embudo cobro → remate → gol; la cabeza y la
   distancia; la foto del remate (`goal_open`) y los escenarios del proyecto
   previo (`05_visualizacion.py`, adaptado al API); el América, como la liga.
8. **¿Sirve para cualquier entrenador? (casos, ADR-57).** Tabla de los nueve;
   lo que viaja y lo que no; Mora y Ambriz como detecciones.
9. **¿El método distingue de verdad?** El marcador de predicciones (sección
   6.4); 15 pares que cambian de signo; los 20 bugs silenciosos y cómo se
   atraparon.
10. **Framework (5.6) y límites.** Definiciones, supuestos, lo que no captura
    (360 posicional, rechazo de Markov en longitudes y balón parado, rotación
    de Liga MX, competiciones fuera de los datos, no causalidad).

### 6.3 Figuras mínimas

- Firma temporal, crudo contra corregido (H4).
- Desviación de E[T] contra la liga por torneo: Jardine, Ortiz, Solari.
- Tabla de pares del América, crudo contra corregido, con IC.
- D1: bosque de E2 de los 27 pares, crudo contra corregido. Zonas de Cruz Azul
  **solo después** de verificar la orientación.
- Contexto: barras de lo que ajusta la liga, y bosque de θ del América.
- Plantel: percentiles de continuidad y N80 por torneo (tres técnicos);
  mapas de zonas de los titulares de Jardine.
- Balón parado: embudo; curva de xG por distancia, cabeza contra pie;
  `goal_open` de córner contra juego abierto; 2–3 escenarios de freeze frame.
- Casos: tabla "lo que viaja".
- Marcador de predicciones.

### 6.4 Marcador de predicciones preinscritas

| ADR | aciertos |
|---|---|
| 53 · H4 | 4/4 |
| 54 · D1 | 2/4 (P2 contaminada) |
| 55 · balón parado | 5/7 |
| 56 · contexto | 5/6 |
| 57 · casos | 0/1 |
| 58 · jugadores | 4/4 |
| **total** | **20/26** |

Mostrar los fallos es parte del argumento: son la prueba de que las
predicciones se escribieron antes.

### 6.5 Reglas del informe

- **Cada cifra con su fuente** (JSON y campo) y su etiqueta 🟢🟡🔴⚪.
- **Los nulos** se redactan como "no detectamos una diferencia mayor a X".
- **Sin lenguaje causal.**
- **HTML autocontenido**, sin CDN (ADR-38).
- **Verificado** con `verifica_reporte.py` y `humo_reporte.py`
  (`15_REPORTE_HTML.md`).
- **Nombres de club** tal como vienen en los datos ("América", no
  "Club América") en todo filtro.

---

## 7. Pendientes técnicos antes del informe (honestos)

1. **Commit de `38`** (inmediato):
   `git add scripts/38_jugadores.py tests/test_jugadores.py && git commit -m "ADR-58: uso de jugadores (38) y su test"`.
2. **Documentar ADR-58**: ADR-58 en `06`, §33 en `10`, 58 ADRs en `13` y en
   `docs/README.md`. Se hace extendiendo `37_docs_resultados.py` o con un
   `39_docs_jugadores.py` que reuse su motor. No hay bugs nuevos.
3. **Orientación de las zonas de D1**: correr `scripts/13_verificar_ejes.py`
   (y `14_verificar_ejes_def.py`) sobre los datos del API **antes** de redactar
   geografía de presión.
4. **Panel descriptivo 5.5** (recomendado): por era y contra la liga del
   torneo, xG a favor y en contra por partido, OBV, pases progresivos y
   *field tilt* del partido completo. Descriptivo, sin familia; no requiere
   ADR con predicciones, pero sí una nota en ADR-59.
5. **Validaciones por replicar con el API** (opcional, o declarar como límite):
   bondad de ajuste de la longitud (`03_bondad_ajuste_longitud.py`),
   auto-transiciones (`05`), cobertura de los IC (`07`).
6. **Huellas (`09`)**: las actuales usan una línea base desconocida y
   probablemente sin la corrección temporal. **No usarlas** en el informe sin
   recalcular con `--baseline opponents` o con la liga del torneo.
7. **ADR-59**: preinscribir la estructura del informe (qué va y qué no) y
   reescribir `12_reporte_html.py` para que consuma los JSON nuevos.

---

## 8. Cómo trabajar en el próximo chat (lecciones de esta sesión)

- **Paquetes numerados.** El siguiente es **h2_26**. Nunca se reutiliza un
  número: `~/Descargas` ya tiene h2_01 a h2_25.
- **Instalación siempre verificando la huella antes de descomprimir**, en un
  directorio nuevo:
  `echo "<sha256>  F" | sha256sum -c - && D=$(mktemp -d …) && tar xzf F -C "$D" && bash "$D/…/INSTALAR.sh"`.
- **Preinscripción**: el documento se commitea **solo** y antes del código.
  Los instaladores lo hacen en ese orden y abortan si ya existe.
- **`grep -q` detrás de una tubería con `pipefail` falla al azar** (SIGPIPE,
  código 141). Usar `grep … >/dev/null`.
- **`less` atrapa la terminal** (se sale con `q`) y se come los comandos
  pegados después. Usar `head -60`.
- **Corridas largas**: `nohup python -u … > logs/x.log 2>&1 &`, y esperar con
  `while pgrep -f … ; do tail -1 …; sleep 30; done`. **No pegar el bloque de
  resultados hasta que termine.** Verificar con `pgrep` antes de lanzar, para
  no correr dos veces.
- **`head` cortando la salida mata el script** (SIGPIPE): redirigir a un log
  y leer el log.
- **Documentación**: todo cambio pasa por `verificar_docs.py` sobre una vista
  previa. Las cifras se generan desde los JSON, nunca tecleadas. Las frases
  interpretativas son condicionales a los resultados.
- **Humos sintéticos** con un `dtdecoder` falso para la fontanería, y humos
  reales con B = 200 antes de cada corrida completa. **Las cifras del humo no
  se citan** (salvo las que no dependen de B, que sí son las reales).
- **Las críticas de otra IA se evalúan con los números**, no con las citas.
  Esta sesión tuvo varias lecturas invertidas (percentiles, intervalos, "las
  cuatro condiciones se cumplieron").

---

## 9. Qué mandar al próximo chat

1. **Este documento.**
2. `docs/13_CONTEXTO_IA.md`, `docs/18_PROTOCOLO_SESION.md`,
   `docs/15_REPORTE_HTML.md`.
3. `docs/06_DECISIONS.md` (al menos ADR-53 a 57) y `docs/10_RESULTADOS.md`
   (§27 a §32).
4. `docs/preinscritos/ADR-58_BORRADOR.md`.
5. `scripts/12_reporte_html.py`, `scripts/verifica_reporte.py`,
   `scripts/humo_reporte.py` y `scripts/37_docs_resultados.py`.
6. **Los seis JSON de resultados**, que son solo agregados: `did_h4_v1.json`,
   `did_presion_v1.json`, `balon_parado_v2.json`, `contexto_v1.json`,
   `jugadores_v1.json` y `deriva_proveedor.json`.
7. El enunciado del reto y `ROADMAP_CIERRE_RETO.md`.
8. Si se usan los escenarios de freeze frame: `05_visualizacion.py` del
   proyecto de córners.

**Primer mensaje sugerido:** *"Retomo dt-decoder. Lee
`19_TRASPASO_CIERRE.md` primero. Tareas en orden: (1) documentar ADR-58
reusando `37`; (2) verificar la orientación de las zonas; (3) panel 5.5;
(4) preinscribir ADR-59 y reescribir `reporte.html` con la estructura de su
sección 6. El siguiente paquete es h2_26."*
