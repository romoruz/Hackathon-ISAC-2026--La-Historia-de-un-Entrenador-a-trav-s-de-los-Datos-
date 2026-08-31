# dt-decoder v0.6.1 — proyecto completo

## Instalación

```bash
cd "/home/rodrigo/Rodrigo Moreno/Codigos Deportes/Hackathon2026"
source .venv/bin/activate
tar xzf ~/Descargas/dt-decoder-v0.6.1.tar.gz
bash dt-decoder-v0.6.1/instalar.sh
```

Hace backup, copia, retira obsoletos, sube la versión, protege los CSV
licenciados en `.gitignore`, corre `pytest` y revierte si falla.

## Contenido

| ruta | n | qué |
|---|---|---|
| `src/dtdecoder/` | 4 | `cli`, `estimate`, `possessions`, `synth` |
| `tests/` | 4 | procedencia, identidad de matrices, contrato npz, determinismo |
| `scripts/` | 13 | los 12 análisis + `generar_todo.sh` |
| `docs/` | 9 | incluye 3 nuevos: `11`, `12`, `13` |
| `data/` | 1 | eras de Cruz Azul |
| `app.py` | 1 | Streamlit, para explorar (el entregable es el HTML) |

### Documentos nuevos

- **`13_CONTEXTO_IA.md`** — para que una IA retome el proyecto sin adivinar:
  flujo de datos, trampas concretas, qué no hacer, plantilla de mensaje.
- **`12_API_STATSBOMB.md`** — qué se sustituye cuando llegue el acceso, en qué
  orden, y qué NO cambia. Incluye las tres preguntas que hay que mandar a los
  organizadores antes de programar nada.
- **`11_MATEMATICA_APLICADA.md`** — qué son los estados absorbentes, bajo qué
  distribución se calcula el EMV, qué significa λ exactamente, y por qué la CV
  no lo identifica.

## Reproducir el entregable

```bash
source .venv/bin/activate

# 1. transiciones por club
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

# 2. todos los análisis, todas las parejas (~40 min)
bash scripts/generar_todo.sh

# 3. el entregable
python scripts/12_reporte_html.py     # -> reporte.html

git add -A && git commit -m "v0.6.1: proyecto completo, 38 ADRs, 11 bugs documentados"
```

## Lo que queda pendiente

| # | qué | esfuerzo | riesgo si no se hace |
|---|---|---|---|
| 1 | Sensibilidad a `min_carry_length` | 2 h | medio |
| 2 | Validación externa contra `shot_statsbomb_xg` | una tarde | bajo |
| 3 | Fechas reales del API | ver `12_API_STATSBOMB.md` | medio |
| 4 | Los 18 equipos | alto | bajo |

## Corregido en esta versión

**El eje Y estaba espejeado** (bug #12). StatsBomb tiene `y` creciendo hacia
abajo, así que `y=0` es la izquierda del equipo que ataca. Verificado con
Zendejas (extremo derecho, 43.6% de sus acciones en `iy=3`).

`scripts/13_verificar_ejes.py` lo comprueba automáticamente contra tres
jugadores de banda conocida.
