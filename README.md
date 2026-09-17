# dt-decoder

Decodificador táctico de entrenadores mediante cadenas de Markov absorbentes
sobre eventos Hudl StatsBomb de Liga MX.

**Reto**: ISAC 2026, *"La historia de un entrenador a través de los datos"*.

### ▶ [![Vista del reporte](docs/img/portada.png)](https://romoruz.github.io/Hackathon-ISAC-2026--La-Historia-de-un-Entrenador-a-trav-s-de-los-Datos-/reporte.html)

Reporte generado con datos sintéticos (`synth.py`), sin ningún dato licenciado.
El reporte con datos reales se entrega a los organizadores del ISAC y no se
publica aquí por la licencia de Hudl StatsBomb.

> **Reto**: ISAC 2026, *"La historia de un entrenador a través de los datos"*.
>
> 🤖 **Nota para Agentes de IA**: Antes de modificar cualquier archivo en este repositorio, lee obligatoriamente [AGENTS.md](AGENTS.md) y [docs/13_CONTEXTO_IA.md](docs/13_CONTEXTO_IA.md). Son la autoridad sobre el proyecto y sus reglas de preservación.

---

## 1. Titulares y Hallazgos Principales

> 🔴 **RETIRADOS (2026-09-15).** Las tablas de esta sección y el control de plantel se calcularon con el volcado anterior y con eras previas al bug #14 (la etiqueta «Solari» mezclaba tres entrenadores). **No son citables.** Tras la migración al API y la corrección de la deriva del proveedor (ADR-53), los contrastes vigentes están en [docs/README.md](docs/README.md) y en `docs/10_RESULTADOS.md` §27. Esta portada se reescribirá con el reporte.

### Bloque Ofensivo (Fases 0–3)

| Hallazgo | Magnitud | IC 95% |
|---|---|---|
| Jardine sostiene posesiones más que Solari | +22.4% | [+18.6, +26.4] |
| Anselmi sostiene más que Reynoso | +25.6% | [+21.4, +29.7] |
| Anselmi genera más remates que Reynoso | +44.6% | [+30.1, +59.2] |
| Jardine genera menos remates que Ortiz | −12.5% | [−23.9, −1.5] |
| **Sánchez vs Ferretti** | **+1.6%** | **[−3.3, +6.8]** ← sin efecto |

> **Ninguna diferencia en la probabilidad de gol *estimada por la cadena* ($B_{\cdot,\text{GOAL}}$) es significativa.** Sobre la *tasa empírica* de gol por posesión sí aparece una, entre Jardine y Herrera (+0.73 pp, q=0.029), en una era de 17 partidos marcada por sobreajuste. Son cantidades distintas: la primera es una probabilidad de absorción del modelo, la segunda una proporción observada. Duración de posesión y generación de peligro siguen siendo dimensiones separables del estilo.
>
> Que el método distinga entre cambios de entrenador con efecto y sin efecto es lo que lo hace creíble.

### Bloque Defensivo (Presión)

| Hallazgo | Magnitud | q |
|---|---|---|
| La presión acorta posesiones (4 eras, 2 clubes) | +11 pp | 0.0020 |
| Anselmi sostiene la presión desde el 3er toque | +4.71 pp | 0.0414 |
| Anselmi concede posesiones más cortas que Reynoso | −0.61 acciones | 0.0042 |
| Anselmi concede menos remates que Reynoso | −3.61 pp | 0.0042 |

> Y el matiz que invierte la lectura fácil: **Anselmi no es un entrenador de presión alta.** La presión extra está en el tercio propio (+2.56 pp) y el medio (+2.92 pp), casi nada arriba (+0.80 pp).
>
> Toda cifra de presión declara si es **por posesión** o **por acción** (ADR-48). Los dos estimandos difieren en signo, y tres afirmaciones previas se retiraron por confundirlos: ver [docs/10_RESULTADOS.md](docs/10_RESULTADOS.md) §16.

---

## 2. Los Seis Pilares de Validación

> Los pilares 5 y 6 no dependen de las eras. Los pilares 1 a 4 se midieron con el volcado anterior y están **pendientes de replicar** con el API.

1. **Bondad de ajuste**: Markov de primer orden rechazado por sobredispersión (KS≈0.09, p=0.005), replicado en tres unidades.
2. **Auto-transiciones**: El 40% de la duración esperada es permanencia en zona. Medido, no oculto.
3. **Invariancia a la resolución**: Los efectos grandes no cambian entre 12 y 30 zonas.
4. **Replicación**: Todo se reproduce en un club independiente con ocho entrenadores.
5. **Cobertura de los IC**: 0.944 contra 0.95 nominal.
6. **Nulas empíricas**: Ninguna distancia sin su distribución de referencia.

### Control de Plantel
**9 de 17 jugadores** que jugaron con Jardine y con Ortiz cambiaron su patrón de juego de forma detectable, cuando por azar se esperaría uno. Jardine heredó el 67% de las acciones de ese plantel.

> ⚠️ **Advertencia**: Veinte bugs encontrados, veinte silenciosos (numerados hasta el #21; el #13 se evitó). Ninguno lanzó una excepción; todos produjeron números plausibles pero incorrectos. En este dominio *"corre sin error"* no es evidencia de nada. Ver [docs/02_STATE_OF_PLAY.md](docs/02_STATE_OF_PLAY.md) §8.

---

## 3. Instalación

Se requiere Python 3.12 y [`uv`](https://github.com/astral-sh/uv).

```bash
# Clonar e inicializar el entorno virtual
make setup

# Activar el venv
source .venv/bin/activate

# Verificar la instalación corriendo la suite de tests
make test
```

---

## 4. Reproducir el Entregable (`reporte.html`)

Si se cuenta con los datos licenciados de StatsBomb (`eventos_completos_america.csv` y `eventos_completos_cruz_azul.csv` en la raíz):

```bash
source .venv/bin/activate

# 1. Derivar fechas y procesar transiciones por club
python scripts/01_derivar_fechas.py --events eventos_completos_america.csv \
  --club "América" --out data/match_dates.csv
dtdecoder phase0 --src eventos_completos_america.csv \
  --eras data/coach_eras.csv --match-dates data/match_dates.csv \
  --club "América" --outdir data/processed

python scripts/01_derivar_fechas.py --events eventos_completos_cruz_azul.csv \
  --club "Cruz Azul" --out data/match_dates_cruz_azul.csv
dtdecoder phase0 --src eventos_completos_cruz_azul.csv \
  --eras data/coach_eras_cruz_azul.csv \
  --match-dates data/match_dates_cruz_azul.csv \
  --club "Cruz Azul" --outdir data/processed_cruzazul

# 2. Generar todos los análisis (~40 min)
bash scripts/generar_todo.sh

# 3. Compilar el reporte interactivo autocontenido
python scripts/12_reporte_html.py     # -> genera reporte.html
```

---

## 5. Índice de Documentación (`docs/`)

| # | Documento | Para quién | Cuándo leerlo |
|---|---|---|---|
| 00 | [Roadmap](docs/00_ROADMAP.md) | Equipo | Planear qué sigue |
| 01 | [Arquitectura](docs/01_ARCHITECTURE.md) | Desarrollador / IA | Antes de tocar código |
| 02 | [Estado actual](docs/02_STATE_OF_PLAY.md) | Todos | **Empezar aquí** |
| 03 | [Métodos](docs/03_METHODS.md) | Jurado técnico | Formalización matemática |
| 04 | [Contrato de datos](docs/04_DATA_CONTRACT.md) | Desarrollador | Antes de la ingesta |
| 05 | [Validación](docs/05_VALIDATION.md) | Todos | Antes de reportar números |
| 06 | [Decisiones (48 ADRs)](docs/06_DECISIONS.md) | Equipo / IA | Antes de reabrir un debate |
| 07 | [Traspaso a IA](docs/07_AI_HANDOFF.md) | IA | Al retomar el proyecto |
| 08 | [Reproducibilidad](docs/08_REPRODUCIBILITY.md) | Equipo | Antes de publicar |
| 09 | [Glosario](docs/09_GLOSSARY.md) | Humanos | Cuando un término no cuadre |
| 10 | [Resultados](docs/10_RESULTADOS.md) | Todos | **Antes de citar una cifra** |
| 11 | [Matemática aplicada](docs/11_MATEMATICA_APLICADA.md) | Jurado / IA | Para defender elecciones |
| 12 | [API de StatsBomb](docs/12_API_STATSBOMB.md) | Equipo | Cuando llegue el acceso |
| 13 | [Contexto para IA](docs/13_CONTEXTO_IA.md) | IA | **Empezar aquí si eres IA** |

### Rutas de lectura recomendadas
- **IA que retoma**: 13 → 02 → 10 → 06 → 01
- **Humano que entiende la matemática**: 09 → 11 → 03 → 05
- **Modificar código**: 01 → 04 → 06 → tests correspondientes
- **Preparar presentación**: 10 → 11 → 02

---

## 6. Licencia y Reporte Demo (`reporte.html`)

> 🔒 **Nota sobre los datos licenciados**: Los eventos crudos de Hudl StatsBomb (`eventos_completos_*.csv`) están bajo propiedad intelectual licenciada y **NUNCA** se redistribuyen ni se versionan en este repositorio git.
>
> 📊 **Reporte público**: Para permitir la inspección completa del entregable interactivo sin violar licencias, este repositorio incluye **[reporte.html](reporte.html)**. Se genera mediante datos sintéticos (`make demo` o `python scripts/humo_reporte.py`) y demuestra el funcionamiento exacto de la interfaz y las visualizaciones.
