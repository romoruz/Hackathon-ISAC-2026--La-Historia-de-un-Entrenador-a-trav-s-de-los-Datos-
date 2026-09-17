# dt-decoder — documentación

Decodificador táctico de entrenadores mediante cadenas de Markov absorbentes
sobre eventos Hudl StatsBomb de Liga MX.

**Reto**: ISAC 2026, *"La historia de un entrenador a través de los datos"*.

## Índice

| # | Documento | Para quién | Cuándo |
|---|---|---|---|
| 00 | [Roadmap](00_ROADMAP.md) | equipo | planear qué sigue |
| 01 | [Arquitectura](01_ARCHITECTURE.md) | desarrollador | antes de tocar código |
| 02 | [Estado actual](02_STATE_OF_PLAY.md) | todos | **empezar aquí** |
| 03 | [Métodos](03_METHODS.md) | jurado técnico | formalización |
| 04 | [Contrato de datos](04_DATA_CONTRACT.md) | desarrollador | antes de la ingesta |
| 05 | [Validación](05_VALIDATION.md) | todos | antes de reportar números |
| 06 | [Decisiones (58 ADRs)](06_DECISIONS.md) | equipo | antes de reabrir un debate |
| 07 | [Traspaso a IA](07_AI_HANDOFF.md) | IA | al retomar |
| 08 | [Reproducibilidad](08_REPRODUCIBILITY.md) | equipo | antes de publicar |
| 09 | [Glosario](09_GLOSSARY.md) | humanos | cuando un término no cuadre |
| 10 | [Resultados](10_RESULTADOS.md) | todos | **antes de citar una cifra** |
| 11 | [Matemática explicada](11_MATEMATICA_APLICADA.md) | jurado / IA | para defender elecciones |
| 12 | [API de StatsBomb](12_API_STATSBOMB.md) | equipo | cuando llegue el acceso |
| 13 | [Contexto para una IA](13_CONTEXTO_IA.md) | IA | **empezar aquí si eres IA** |
| 14 | [Limpieza del repositorio](14_LIMPIEZA_REPO.md) | agente de IA | antes de publicar |
| 15 | [El reporte HTML](15_REPORTE_HTML.md) | desarrollador | **antes de tocar el entregable** |
| 16 | [Migración al API](16_MIGRACION_API.md) | equipo | decisiones de alcance |
| 17 | [Bitácora de la migración](17_BITACORA_MIGRACION.md) | IA / equipo | al retomar |
| 18 | [Protocolo de sesión](18_PROTOCOLO_SESION.md) | IA / equipo | **antes de operar el repo** |

## Rutas de lectura

**IA que retoma**: 13 → 02 → 10 → 06
**Humano que entiende**: 09 → 11 → 05
**Modificar código**: 01 → 04 → 06 → tests
**Preparar presentación**: 10 → 11 → 02
**Migrar al API**: 12
**Tocar el reporte**: 15 → `verifica_reporte.py` → `humo_reporte.py`
**Limpiar y publicar**: 14 → 08

## Estado
<!-- h2_14 -->

**Migrado al API de Hudl StatsBomb** (Liga MX, fase regular, 10 torneos,
18 clubes). La unidad es `(club, entrenador)`: 53 eras analizables, 60 pares
dentro del mismo club.

Los contrastes entre eras **descuentan la deriva de anotación del proveedor**
comparando cada era contra la liga en sus mismos torneos (ADR-53). Sin esa
corrección, 15 de 60 pares
cambian de signo.

El entregable es `reporte.html`: un archivo autocontenido, sin dependencias
externas, que se abre con doble clic. Está **en regeneración**: sus insumos
se recalculan con las eras del API.

## Titulares

Duración esperada de la posesión, $E[T]$, corregida por la liga
contemporánea. Clubes con sección profunda en el reporte. La tabla completa de
los 60 pares está en `10_RESULTADOS.md` §27.

| club | par | crudo | DiD | IC 95% | q | |
|---|---|---|---|---|---|---|
| América | Andre Jardine vs Fernando Ortiz | +12.8% | **+3.5%** | [+0.1, +7.0] | 0.0562 | ⚪ |
| América | Andre Jardine vs Santiago Solari | +31.4% | **+17.6%** | [+12.7, +22.4] | 0.0010 | 🟢 |
| América | Fernando Ortiz vs Santiago Solari | +16.5% | **+13.6%** | [+8.2, +18.7] | 0.0010 | 🟢 |
| Atlas | Benat San Jose vs Benjamin Mora | -4.2% | **-7.9%** | [-12.0, -3.5] | 0.0010 | 🟢 |
| Atlas | Benat San Jose vs Diego Cocca I | +7.0% | **-3.2%** | [-6.9, +0.6] | 0.1301 | ⚪ ↺ |
| Atlas | Benat San Jose vs Diego Cocca II | -0.5% | **+1.6%** | [-3.0, +6.4] | 0.5503 | ⚪ ↺ |
| Atlas | Benjamin Mora vs Diego Cocca I | +11.7% | **+5.1%** | [+1.0, +9.4] | 0.0207 | 🟢 |
| Atlas | Benjamin Mora vs Diego Cocca II | +3.9% | **+10.2%** | [+4.9, +15.5] | 0.0010 | 🟢 |
| Atlas | Diego Cocca I vs Diego Cocca II | -7.0% | **+4.9%** | [+0.5, +9.6] | 0.0389 | 🟢 ↺ |
| León | Ariel Holan vs Eduardo Berizzo | +4.0% | **+19.2%** | [+14.5, +24.5] | 0.0010 | 🟢 |
| León | Ariel Holan vs Nicolas Larcamon | +4.1% | **+10.9%** | [+6.3, +15.5] | 0.0010 | 🟢 |
| León | Eduardo Berizzo vs Nicolas Larcamon | +0.1% | **-7.0%** | [-10.8, -3.2] | 0.0010 | 🟢 ↺ |

Signo positivo: el primer entrenador del par sostiene la posesión más que el
segundo. 🟢 significativo tras BH sobre los 60 pares ·
⚪ no significativo · ↺ el signo se invierte al corregir la deriva.

## El método no encuentra efectos en todas partes

16 de los 60 pares no
rechazan. Ninguno demuestra equivalencia al 3%, así que se redactan con su
margen:

| club | par | no detectamos una diferencia mayor a |
|---|---|---|
| Toluca | Antonio Mohamed vs Renato Paiva | 4.02% |
| Tigres UANL | Guido Pizarro vs Robert Siboldi | 4.75% |
| Tigres UANL | Guido Pizarro vs Miguel Herrera | 4.80% |

Y la corrección misma discrimina: entre los pares significativos, la fracción
con el entrenador posterior más largo pasa del
37/47
sin corregir al
23/44
corregido.

## Defensa, balón parado y contexto
<!-- h2_23 -->

- **Presión (ADR-54).** Contra la liga del mismo torneo, sobreviven
  6 de 135 contrastes (24 sin la
  corrección), en 3 pares: América: Fernando Ortiz vs Santiago Solari; Cruz Azul: Juan Reynoso vs Martin Anselmi; Cruz Azul: Juan Reynoso vs Nicolas Larcamon. `10_RESULTADOS.md` §28.
- **Balón parado (ADR-55).** 0 de 84 contrastes
  separan a una era de la liga (familia de casos: 2 de
  96). La cabeza y la geometría del remate cambian el xG. §29.
- **Contexto (ADR-56).** Cada era comparada con el ajuste de la liga a la
  localía, el marcador, el momento y el rival: se separan
  1 de 336 contrastes. §30.
- **Casos (ADR-57).** Las eras del América y los técnicos con varios clubes. El ajuste al marcador mantiene su signo en 3 de 9. §31.
- **Jugadores (ADR-58).** Tras el primer cambio táctico, se separan de la liga 0 de 84 contrastes. Torneos con la continuidad del once en el 15% inferior de la liga: Andre Jardine 6 de 6; Fernando Ortiz 1 de 2; Santiago Solari 1 de 1. §33. <!-- h2_27 -->

## Retirados

| afirmación | motivo |
|---|---|
| Jardine sostiene más que Solari, +22.4% | eras previas al bug #14; el contraste vigente está arriba |
| Anselmi sostiene más que Reynoso, +25.6%; genera más remates, +44.6% | eras y datos previos a la migración; pendiente de recalcular con ADR-53 |
| Jardine genera menos remates que Ortiz, −12.5% | eras previas al bug #14 |
| Control de plantel: 9 de 17 jugadores | eras previas al bug #14; pendiente |
| Sánchez vs Ferretti sin efecto | las dos eras quedan bajo el umbral de 25 partidos |
| Berizzo vs Larcamón como par nulo | con la deriva fuera, difieren (§27) |
| "Ninguna diferencia en P(gol) es significativa" | pendiente de reverificar: hoy P(gol) es descriptivo |

## Validación

Siguen en pie, porque no dependen de las eras: la **cobertura de los IC**
(0.944 contra 0.95, generador con parámetro conocido) y **ninguna distancia
sin su nula**. El rechazo de Markov de orden 1, la invariancia a la resolución
y las auto-transiciones se midieron con el volcado anterior y están
**pendientes de replicar** con el API.

## Advertencia

**Veinte bugs encontrados, todos silenciosos** (numerados hasta el #21; el
#13 se evitó). Ninguno lanzó una excepción; todos produjeron números plausibles
pero incorrectos. El #14 fue un
dato de entrada (las eras investigadas a mano) y el #19 una regla de diseño
que el código no cumplía. En este dominio *"corre sin error"* no significa
nada.
