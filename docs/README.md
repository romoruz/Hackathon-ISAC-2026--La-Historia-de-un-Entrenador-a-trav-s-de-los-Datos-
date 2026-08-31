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
| 06 | [Decisiones (51 ADRs)](06_DECISIONS.md) | equipo | antes de reabrir un debate |
| 07 | [Traspaso a IA](07_AI_HANDOFF.md) | IA | al retomar |
| 08 | [Reproducibilidad](08_REPRODUCIBILITY.md) | equipo | antes de publicar |
| 09 | [Glosario](09_GLOSSARY.md) | humanos | cuando un término no cuadre |
| 10 | [Resultados](10_RESULTADOS.md) | todos | **antes de citar una cifra** |
| 11 | [Matemática explicada](11_MATEMATICA_APLICADA.md) | jurado / IA | para defender elecciones |
| 12 | [API de StatsBomb](12_API_STATSBOMB.md) | equipo | cuando llegue el acceso |
| 13 | [Contexto para una IA](13_CONTEXTO_IA.md) | IA | **empezar aquí si eres IA** |
| 14 | [Limpieza del repositorio](14_LIMPIEZA_REPO.md) | agente de IA | antes de publicar |
| 15 | [El reporte HTML](15_REPORTE_HTML.md) | desarrollador | **antes de tocar el entregable** |

## Rutas de lectura

**IA que retoma**: 13 → 02 → 10 → 06
**Humano que entiende**: 09 → 11 → 05
**Modificar código**: 01 → 04 → 06 → tests
**Preparar presentación**: 10 → 11 → 02
**Migrar al API**: 12
**Tocar el reporte**: 15 → `verifica_reporte.py` → `humo_reporte.py`
**Limpiar y publicar**: 14 → 08

## Estado

**Fases 0–3 completas y validadas sobre dos clubes independientes** (Club
América y Cruz Azul, 333 partidos, 12 eras de entrenador). Todo titular lleva
intervalo de confianza, y los intervalos están validados por cobertura empírica
(0.944 contra 0.95 nominal).

El entregable es `reporte.html`: un archivo autocontenido, sin dependencias
externas, que se abre con doble clic.

`dtdecoder 0.6.0`

## Titulares

| hallazgo | magnitud | IC 95% |
|---|---|---|
| Jardine sostiene posesiones más que Solari | +22.4% | [+18.6, +26.4] |
| Anselmi sostiene más que Reynoso | +25.6% | [+21.4, +29.7] |
| Anselmi genera más remates que Reynoso | +44.6% | [+30.1, +59.2] |
| Jardine genera menos remates que Ortiz | −12.5% | [−23.9, −1.5] |
| **Sánchez vs Ferretti** | **+1.6%** | **[−3.3, +6.8]** ← sin efecto |

**Ninguna diferencia en probabilidad de gol es significativa.** Duración de
posesión y generación de peligro son dimensiones independientes del estilo.

Y la última fila importa: que el método distinga entre cambios de entrenador con
efecto y sin efecto es lo que lo hace creíble.

## Los seis pilares de validación

1. **Bondad de ajuste**: Markov de primer orden rechazado por sobredispersión
   (KS≈0.09, p=0.005), replicado en tres unidades.
2. **Auto-transiciones**: el 40% de la duración esperada es permanencia en zona.
   Medido, no oculto.
3. **Invariancia a la resolución**: los efectos grandes no cambian entre 12 y 30
   zonas.
4. **Replicación**: todo se reproduce en un club independiente con ocho
   entrenadores.
5. **Cobertura de los IC**: 0.944 contra 0.95 nominal.
6. **Nulas empíricas**: ninguna distancia sin su distribución de referencia.

## Y el control de plantel

**9 de 17 jugadores** que jugaron con Jardine y con Ortiz cambiaron su patrón de
juego de forma detectable, cuando por azar se esperaría uno. Jardine heredó el
67% de las acciones de ese plantel.

## Advertencia

**Doce bugs encontrados, doce silenciosos.** Ninguno lanzó una excepción; todos
produjeron números plausibles pero incorrectos. En este dominio *"corre sin
error"* no significa nada. Ver `02_STATE_OF_PLAY.md` §8.
