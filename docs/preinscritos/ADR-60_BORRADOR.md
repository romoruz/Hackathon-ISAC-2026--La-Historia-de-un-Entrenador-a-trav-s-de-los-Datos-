# ADR-60 — Relevos: cuánto cambia el uso del campo y qué parte viene del plantel

> **BORRADOR PREINSCRITO, 2026-09-21.** Escrito antes de `scripts/42_relevos.py`
> y de `scripts/43_mapa_estilos.py`. Se commitea solo, antes del código
> (paquete h2_33).
>
> **Declaración de contaminación.** Nadie ha calculado todavía las cantidades
> de §3 (T, C, U). Lo que sí se vio es el barrido exploratorio
> (`41_barrido_eras.py`, 2026-09-18): las distancias entre eras en el plano
> PC1–PC2, los jugadores compartidos y el elenco de cinco historias, elegido
> viéndolas. Las predicciones P1 a P4 de §6 están informadas por ese barrido;
> se declaran así y valen menos que P5 y P6. El mapa de §5 reproduce el
> barrido y entra como nivel C, sin contrastes.

## 1. Pregunta

Cuando cambia el técnico de un club, ¿cuánto cambia la forma en que el equipo
ocupa la cancha? Y de ese cambio, ¿qué parte corresponde a **quién juega**
(composición) y qué parte a **cómo juegan los que siguieron** (uso)?

Es una descomposición contable, no causal. No dice que el técnico "provocó" el
cambio de uso ni que el club "impuso" la composición.

## 2. Unidades y familia

**Familia F60 (m = 21), fijada aquí:** todas las parejas de
`did_h4_v1 › pares` en los clubes de las cinco historias que incluyen al
técnico de la historia. La lista es la misma que usa la sección 3.1 del
informe (adenda 2 §4):

| club | pareja (saliente → entrante, por primer torneo) |
|---|---|
| América | Solari → Ortiz · Solari → Jardine · Ortiz → Jardine |
| Atlético San Luis | Jardine → Torrent · Jardine → Abascal · Jardine → Leal |
| Cruz Azul | Reynoso → Larcamón · Anselmi → Larcamón |
| León | Holan → Larcamón · Larcamón → Berizzo |
| Monterrey | Vucetich → Ortiz · Ortiz → Torrent · Ortiz → Demichelis |
| Santos Laguna | Fentanes → Ambriz |
| Tigres UANL | Herrera → Pizarro · Herrera → Siboldi · Herrera → Paunovic |
| Tijuana | Herrera → Osorio · Herrera → Abreu |
| Toluca | Ambriz → Mohamed · Ambriz → Paiva |

Si el script encuentra otro número de parejas, aborta: la familia no se
recalcula viendo los datos.

**Control negativo, fuera de la familia:** Cocca I → Cocca II (Atlas), el
mismo técnico en dos etapas del mismo club.

## 3. Cantidades

Insumo: `data/processed_api_<club>/transitions.parquet` de los 18 clubes.
Acciones de la cadena del propio equipo (estado de origen transitorio), malla
5×4, igual que el mapa de zonas del informe.

**Ocupación en exceso de la liga.** Para una era *e*:

- `p_e(z)` es la fracción de las acciones del club en la zona *z* bajo la era *e*;
- `L_t(z)` es la misma fracción para la liga del torneo *t*, **sin el club**;
- `L̄_e` es la media de `L_t` ponderada por las acciones de la era en cada
  torneo.

La ocupación en exceso es `p*_e = p_e − L̄_e`. Restar la liga del mismo torneo
es lo que protege de la deriva del proveedor (ADR-53).

**T · cuánto cambió el uso del campo.** Para la pareja *a → b*:

- Δ = `p*_b − p*_a` (20 zonas);
- T = ½‖Δ‖₁, una distancia de variación total, entre 0 y 1.

**Descomposición composición / uso.** Cada era es la suma de sus jugadores:
`p_e = Σ_j w_{j,e} · z_{j,e}`, donde `w` es la fracción de acciones del jugador
y `z` su ocupación. En exceso, `z*_{j,e} = z_{j,e} − L̄_e`. Como `Σ_j w = 1` en
cada era, Δ se reparte exactamente en dos partes:

- **U (uso)** = `Σ_{j ∈ S} w̄_j · (z*_{j,b} − z*_{j,a})`, con *S* los jugadores
  compartidos y `w̄` la media de sus dos pesos;
- **C (composición)** = Δ − U: la entrada y salida de jugadores, el cambio de
  peso de los compartidos y el resto.

**Compartido** significa **al menos 200 acciones en cada una de las dos eras**
(umbral fijado aquí). Los jugadores bajo el umbral se agrupan en un "resto"
por era y cuentan como composición. Si una pareja tiene menos de 3
compartidos, U no se estima y se declara.

Se publican ½‖C‖₁, ½‖U‖₁ y **φ_U = ‖U‖₁ / (‖U‖₁ + ‖C‖₁)**, la parte del cambio
que corresponde al uso. C y U pueden compensarse zona a zona; por eso se
publican las dos normas y el mapa de cada una, no solo φ_U.

**Sensibilidad, sin familia:** la distancia de Jensen–Shannon entre las
matrices Q de las dos eras, en crudo y sin corregir la deriva. Va en el
plegable de método, con esa advertencia.

## 4. Inferencia

- **Nula de T (ADR-30):** se permutan las etiquetas de era **entre los
  partidos del club**, manteniendo el número de partidos de cada era. Cada
  partido conserva su propia referencia de liga (la de su torneo), así que la
  nula respeta la deriva. B = 4999 permutaciones; p = (1 + #{T_perm ≥ T}) / (B + 1).
- **Familia:** Benjamini–Hochberg al 5% sobre los 21 p de T.
- **Intervalos:** bootstrap por partido dentro de cada era, B = 2000, percentil
  95%, para T, ½‖C‖₁, ½‖U‖₁ y φ_U. Semilla fija en el JSON.
- **Niveles:** T es **A** ("el uso del campo cambió", con q; o nulo con
  margen). C, U y φ_U son **B**: con intervalo y sin familia.
- La distribución de distancias entre todas las eras es **contexto**, nunca
  criterio de rechazo (protocolo §7).

## 5. Mapa de estilos (3.3) y lo que viaja (3.4)

`43_mapa_estilos.py` recalcula desde los JSON (no desde los CSV del barrido)
el PCA de 53 eras × 9 métricas de `41_barrido_eras.py`, con la misma
estandarización y el mismo signo. Los nombres de los ejes, "dominio con balón"
(PC1) y "rotación" (PC2), se eligieron **viendo las cargas** y así se declara.

- Todo el mapa es **nivel C**: puntos, una flecha por pareja de F60 y una por
  cada traslado de los técnicos de las historias.
- **Sin elipses.** Cinco de las nueve métricas no tienen réplicas por partido
  guardadas; unas elipses construidas con los intervalos marginales
  inventarían una covarianza. Se descarta.
- La distancia de cada traslado se da con su percentil entre las distancias de
  todas las parejas de eras (contexto, nivel C).
- Un test compara el mapa con `reports/barrido/eras.csv` y falla si alguna
  coordenada difiere en más de 1e-6.

## 6. Predicciones (antes de calcular T, C y U)

| # | predicción | informada por el barrido |
|---|---|---|
| P1 | Tijuana, Herrera → Osorio (15 compartidos): T rechaza tras BH y φ_U ≥ 0.5 | sí |
| P2 | León, Holan → Larcamón: T **no** rechaza | sí |
| P3 | Santos, Fentanes → Ambriz: T rechaza | sí |
| P4 | San Luis, Jardine → {Torrent, Abascal, Leal}: rechazan a lo sumo 1 de 3 | sí |
| P5 | En las parejas de F60 con U estimable, la correlación de Spearman entre compartidos y φ_U es > 0 | no |
| P6 | Control: Cocca I → Cocca II no rechaza (p > 0.05 sin corregir) | no |

Se cuentan en el marcador del cierre, con las que fallen a la vista.

## 7. Redacción

- "Tras el relevo, el uso del campo cambió" (A) o "no detectamos un cambio mayor
  a X" (nulo), nunca "el técnico cambió el equipo".
- La descomposición se dice como reparto: "de ese cambio, X corresponde a los
  jugadores que siguieron y cambiaron de zonas; Y a quién jugó".
- **Frases prohibidas nuevas:** "se debe a", "por culpa de", "gracias al
  plantel". Se añaden a `frases_prohibidas.py`.

## 8. Qué entra al informe

- **3.1:** T de cada pareja de la historia (nivel A), junto al ΔE[T] que ya está.
- **3.2:** C contra U por pareja y los mapas de Δ, C y U (nivel B).
- **3.3:** el mapa de estilos (nivel C).
- **3.4:** la distancia de sus traslados con percentil (nivel C).
- Cierre: P1 a P6 en el marcador.

## 9. Límites

- Jugadores con menos de 200 acciones en una era no tienen uso propio: van a
  composición.
- La nula por permutación supone que los partidos son intercambiables dentro
  del club bajo H0; no corrige por rivales.
- La composición no separa fichajes de lesiones, de convocatorias ni de
  calendario.
- Nada es causal.
