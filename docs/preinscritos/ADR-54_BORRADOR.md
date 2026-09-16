# ADR-54 — El bloque defensivo D1 se normaliza por la liga del mismo torneo

> **BORRADOR, 2026-09-16.** Escrito ANTES de programar
> `scripts/33_did_presion.py` y antes de ver ningún número de esa corrida.
> Va a `docs/preinscritos/` (fuera del alcance de `verificar_docs.py`, que
> exige que toda ADR citada esté definida) y **se hace commit solo**, antes de
> escribir código: así git fecha la preinscripción, que es lo que ADR-53 no
> pudo demostrar.

## Contexto

**1. La tasa de presión deriva, y a saltos.** `reports/deriva_proveedor.json`,
media de los 18 clubes por torneo:

| torneo | A2021 | C2022 | A2022 | C2023 | A2023 | C2024 | A2024 | C2025 | A2025 | C2026 |
|---|---|---|---|---|---|---|---|---|---|---|
| π liga | .2129 | .2134 | **.1922** | .2048 | .2056 | .1958 | .2022 | **.2181** | .2049 | .2033 |

Los saltos son sincronizados, que es la firma de deriva que declara la regla D2
de `22_deriva_proveedor.py`:
- C2022→A2022: sube en 3 de 18 clubes, cambio mediano −2.5 pp;
- A2024→C2025: sube en **18 de 18**, +1.7 pp;
- C2025→A2025: sube en 3 de 18, −1.5 pp.

La amplitud (±1.3 pp alrededor de 0.205) es del orden de los efectos de D1:
Δ zonales de 2 a 4 pp. No es una tendencia, así que un ajuste por pendiente no
la quita: hace falta la normalización torneo a torneo de ADR-53.

**2. Las nulas actuales incluyen la deriva.** Los scripts 18, 19 y 20 permutan
la etiqueta de era entre partidos. Bajo esa nula, dos eras que vivieron torneos
con distinta anotación **no** son intercambiables, y el test detecta estilo más
deriva. Es el bug #19 con otro estimando.

**3. `18_campo_presion.py` reporta magnitudes encogidas.** Usa
π\*(λ) con λ = 50 y 200 hacia el pool de las otras eras **del mismo club**.
Eso contradice ADR-22 (las magnitudes van a λ=0) y además encoge hacia periodos
distintos.

**4. La familia vigente es la de ADR-52.** 27 parejas × 24 contrastes = 648, con
32 sobrevivientes (`reports/fdr_presion.json`). Esos 32 **no se han leído** al
escribir esto.

## Decisión

### Unidad y base

- **Unidad**: (club, entrenador) **defendiendo**, es decir, las acciones reales
  (sin `TERMINAL`) de los rivales en los partidos de esa era, en el marco del
  club (`mirror_zone`, ADR-40).
- **Base**: todas las acciones de la liga en los torneos de la unidad,
  **excluyendo todos los partidos del club**, en los dos sentidos. Se excluye
  también el club atacando: la presión que recibe un equipo depende de los dos.
- **Estandarización**: la base se pondera a la composición de la unidad por
  **(torneo × zona)**. Así, un rival que juega más abajo contra este club no se
  confunde con presión.

### Estimandos

Todos son **por acción** (ADR-48) y se expresan en **puntos porcentuales**.

| # | contraste por par (a, b) | definición |
|---|---|---|
| E1 | geografía (ómnibus) | $T = \sum_z \big(\Delta_z / \mathrm{se}_z\big)^2$ sobre las zonas testeables, con $\Delta_z = [\pi_a(z)-\pi_{base,a}(z)] - [\pi_b(z)-\pi_{base,b}(z)]$ |
| E2 | nivel en k ≥ 3 | DiD de π restringido a k ≥ 3 |
| E3 | pendiente | DiD de la pendiente de π(k), k = 2…12 (misma regresión que `19`) |
| E4 | L = 1, juego abierto | DiD de π en posesiones de una acción, fases `open`/`transition` |
| E5 | L = 1, balón parado | ídem, fases `restart`/`set_piece`; se excluye si π = 0 en las dos eras (regla de `22_fdr_presion.py`) |

- **Magnitudes con π crudo (λ=0).** Una zona es testeable si la unidad tiene al
  menos 100 acciones en ella; si no, no entra en E1 y se declara.
- **Escala principal: diferencia en pp.** Es la escala que lee el jurado y la de
  ADR-48, y con π entre 0.14 y 0.41 las escalas aditiva y logística casi
  coinciden.
- **Sensibilidad: diferencia en logit.** Un contraste que sobrevive en pp y
  cambia de signo en logit se marca 🟡.

### Incertidumbre

- **Bootstrap por partido** (la unidad de dependencia de D1: φ de Cochran de
  1.7–1.8 sobre partidos) para la unidad, y **por partido estratificado por
  torneo** para la base.
- **Las réplicas de la base se comparten dentro de cada club.** Las dos eras de
  un par usan la misma base, así que su variabilidad se cancela en parte en
  Δ. Remuestrearla por separado exageraría la varianza.
- **IC basic** (ADR-10). E2–E5 obtienen su p invirtiendo el IC, como en ADR-53.
- **E1 se contrasta con un bootstrap centrado**:
  $T^* = \sum_z \big((\Delta^*_z-\Delta_z)/\mathrm{se}_z\big)^2$ y
  $p = (1+\#\{T^*\ge T\})/(B+1)$, con $\mathrm{se}_z$ tomado de las mismas
  réplicas.
- **B = 6000.** Con m = 135 contrastes, $2/(B+1) = 0.00033 < \alpha/m = 0.00037$,
  así que un par aislado puede rechazar (D53-8).

### Familia, en dos etapas (patrón de ADR-25)

- **Etapa 1**: E1–E5 de las 27 parejas de los seis clubes de ADR-52, es decir
  ≤ 135 contrastes, con BH al 5%. Es la familia de descubrimiento.
- **Etapa 2**: solo en las parejas cuyo E1 rechaza en la etapa 1, las zonas
  (Δ_z con su IC y su p), con BH **dentro de cada pareja**. Se declara como
  procedimiento condicional, no como test único.
- **El crudo** (mismos estimandos sin restar la base, mismas réplicas) se
  calcula como comparación, nunca como hallazgo (D53-3).

### Lo que no cambia

- **D1-calibración** (`21_calibracion_presion.py`, ADR-48). Mide una
  asociación **dentro** de cada era, y una deriva común a toda la era apenas la
  toca. No se recalcula aquí.
- **La salvedad de censura de E2** (condiciona a sobrevivir hasta k = 3), que
  se sigue declarando.
- **El caveat de asociación**: StatsBomb anota presión cuando un defensor se
  acerca, y se acerca más cuando el rival ya está en problemas.

## Reglas preinscritas

| | |
|---|---|
| D54-1 | Familia nueva: E1–E5 de las 27 parejas de ADR-52, BH 5% |
| D54-2 | Zonas solo en la etapa 2, condicionadas a E1 |
| D54-3 | Magnitudes en pp con π crudo; logit como sensibilidad |
| D54-4 | Base sin ningún partido del club, estandarizada por torneo × zona |
| D54-5 | Bootstrap por partido; base compartida dentro del club; B = 6000 |
| D54-6 | Clave compuesta (club, entrenador) en todo diccionario y archivo |
| D54-7 | Candado H4-8 vigente |
| D54-8 | Se reporta el crudo con las mismas réplicas; no es hallazgo |
| D54-9 | Si el artefacto de la liga no trae `under_pressure`, `event_index`, `match_id` y las filas `TERMINAL`, el script aborta: no se reconstruye la base con los directorios por club sin una ADR aparte |

## Predicciones, escritas antes de programar

**Declaración de contaminación.** Antes de escribir esto vi:
- la serie de π por torneo de arriba;
- el JSON crudo de Jardine vs Ortiz (`nivel_calibracion_…json`: nivel −0.46 pp,
  p = 0.70; `campo_presion_…json`: 0 zonas tras BH);
- y la forma en que ADR-53 cambió H4.

**No** he visto los 32 sobrevivientes actuales ni ningún otro par.

1. **No hay firma temporal que corregir.** Como π no tiene tendencia, entre los
   contrastes E2 que rechazan en el crudo la fracción con la era posterior más
   presionante debe quedar **entre 35% y 65%**, y seguir en ese rango con el
   DiD. Si el crudo sale fuera de ese rango, la predicción falla y se reporta.
2. **Jardine vs Ortiz, E2.** El DiD sale **más negativo** que el crudo. Con la
   serie de arriba, las eras de Ortiz caen sobre torneos de π bajo (A2022) y las
   de Jardine incluyen C2025. La diferencia de base ronda los +0.3 pp; es una
   cuenta burda, ponderada por partidos y no por acciones ni por zona.
3. **Cocca I vs Cocca II, E1–E5.** Cambian **poco** del crudo al DiD (menos de
   0.5 pp en E2): las medias de base de sus torneos difieren en unos 0.2 pp.
   Es lo contrario de lo que pasó en H4, y por eso es informativo.
4. **La corrección pesa menos que en H4.** El número de contrastes de la etapa 1
   cuyo veredicto cambia entre crudo y DiD es **menor que el 25%** de los
   evaluados. En H4, contra la v5, cambió el 38% (12 dejaron de rechazar y 11
   empezaron: 23 de 60).

## Consecuencias

- `reports/fdr_presion.json` (familia de ADR-52) queda como **crudo con la
  deriva dentro**; no se borra.
- La adenda de ADR-52 se mantiene como registro de lo que se corrió.
- Todo titular defensivo del reporte sale de la etapa 1 de esta ADR o se marca
  como exploratorio.
- **Coste estimado**: 21 unidades × 6000 réplicas. Las réplicas de base se
  calculan una vez por club. Del orden de una hora; se corre con
  `nohup python -u`.

## Anexo — nota sobre ADR-53

`30_did_contemporaneo.py` remuestrea la base **por separado para cada
unidad**. Las bases de dos eras del mismo club se solapan mucho: es la misma
liga sin el mismo club, en torneos a menudo compartidos. Tratar esas réplicas
como independientes sobreestima la varianza de $D_a - D_b$. Los IC de ADR-53
son, por tanto, **conservadores** en su componente de base. No cambia ningún
veredicto en la dirección de "más rechazos"; se declara.

## Decisiones que confirma Rodrigo

1. Seis clubes (familia de ADR-52) y no los 16 con pares.
2. Escala principal en pp, logit como sensibilidad.
3. Familia en dos etapas con E1 ómnibus.
