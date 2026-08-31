# 13 — Contexto para una IA

> Escrito para que un modelo de lenguaje que nunca ha visto este proyecto pueda
> retomarlo sin adivinar. Si eres una IA leyendo esto: **empieza aquí, no por el
> código**.

---

## 1. Qué es este proyecto, sin rodeos

Un sistema que responde *"¿cómo juega este entrenador?"* usando solo datos de
eventos de fútbol. El modelo es una **cadena de Markov absorbente** sobre
estados (zona del campo × fase de juego). El entregable es un **reporte HTML
autocontenido** para un jurado no técnico.

No es un modelo predictivo. No valora jugadores. No dice quién es mejor
entrenador. **Describe estilo y mide la incertidumbre de esa descripción.**

---

## 2. La regla que gobierna todo

> **En este dominio, los errores no producen excepciones: producen números
> plausibles pero equivocados.**

**Doce bugs encontrados, doce silenciosos.** Ninguno lanzó un error. Todos
dieron resultados que parecían correctos. Ejemplos:

- `phase2` modelaba a un entrenador y rotulaba las figuras con el nombre de
  otro. Se detectó porque un número cambió 5% entre dos corridas del mismo
  comando.
- Una semilla fija sobre `unique()` de polars, cuyo orden no está garantizado:
  tres corridas idénticas, tres resultados distintos en el cuarto decimal.
- Un filtro que eliminaba las absorciones terminales inflaba $E[T]$ un 30%, y
  los cocientes lo ocultaban porque afectaba a ambas eras por igual.

**Consecuencia práctica para ti**: si escribes código para este proyecto,
*"corre sin error"* no significa nada. Necesitas un test que verifique **el
número**, no la ejecución.

---

## 3. Orden de lectura

Con presupuesto de contexto limitado, en este orden:

| # | Documento | Por qué |
|---|---|---|
| 1 | `02_STATE_OF_PLAY.md` | dónde estamos, qué está validado, los doce bugs |
| 2 | `10_RESULTADOS.md` | los hallazgos con etiqueta 🟢🟡🔴⚪ y sus caveats |
| 3 | `06_DECISIONS.md` | 51 ADRs. **No reabrir debates cerrados** |
| 4 | `11_MATEMATICA_APLICADA.md` | qué es cada objeto y por qué funciona |
| 5 | `01_ARCHITECTURE.md` | qué hace cada archivo |
| 6 | `04_DATA_CONTRACT.md` | trampas del formato StatsBomb |
| 7 | `05_VALIDATION.md` | antes de reportar cualquier número |
| 8 | `15_REPORTE_HTML.md` | **antes de tocar el entregable** |
| 9 | `12_API_STATSBOMB.md` | qué cambia cuando llegue el acceso |

**No cites ningún número sin leer su fila en `10_RESULTADOS.md`.** Cada hallazgo
tiene una etiqueta y un caveat, y varios fueron retirados tras investigarlos.

---

## 4. Qué archivos necesitas y cuáles no

### Para entender el proyecto
Solo los `.md` de `docs/`. Son autocontenidos.

### Para tocar el modelo
```
src/dtdecoder/
  possessions.py   ← la Fase 0. AQUÍ se originan casi todos los bugs
  grid.py          ← el espacio de estados
  estimate.py      ← EMV, encogimiento, validación cruzada
  absorbing.py     ← N, B, ν
  inference.py     ← LRT, bootstrap, FDR
  eras.py          ← mapeo partido → entrenador
  cli.py           ← orquestación de fases
config/default.yaml ← TODO parámetro vive aquí, nada hardcodeado
```

### Para tocar los análisis
`scripts/*.py`. Son **standalone**: importan de `dtdecoder` pero no forman parte
del paquete. Cada uno responde una pregunta y escribe un JSON en `reports/`.

### Lo que NUNCA debes pedirle al usuario
Los CSV de eventos (`eventos_completos_*.csv`). Son **datos licenciados de
StatsBomb**, pesan cientos de MB y no se versionan. Si necesitas ver el formato,
mira `04_DATA_CONTRACT.md` o pide una muestra de 100 filas.

---

## 5. El flujo de datos, en orden

```
eventos_completos_<club>.csv          (licenciado, no versionar)
        │
        │  ingest.load()               esquema completo, infer_schema_length=None
        ▼
   LazyFrame normalizado
        │
        │  possessions.build_transitions()
        ▼
data/processed/transitions.parquet     ← el artefacto central
        │  columnas: poss_uid, match_id, team, event_index, phase,
        │            score_state, score_state_club, action_type,
        │            player_id, player, under_pressure,
        │            from_state, to_state, is_absorbing, coach,
        │            match_date, coach_faced
        │  OJO: `from_state`/`to_state` son ENTEROS, no cadenas.
        │  estado = (ix*NY + iy)*n_fases + fase  ← igual que `mapa_zonas`
        │
        ├─► phase1  → P_matrices.npz + phase1_report.json
        ├─► phase2  → phase2.npz + figuras
        ├─► phase3  → fingerprint.parquet + context_contrast.parquet
        └─► scripts/*.py → reports/*.json
                              │
                              ▼
                    12_reporte_html.py → reporte.html
```

**Dos artefactos derivados que hacen falta y no salen del pipeline:**

- `data/coach_eras*.csv` — investigado a mano en Wikipedia. Ver
  `12_API_STATSBOMB.md` §4.
- `data/match_dates*.csv` — generado por `scripts/01_derivar_fechas.py` a partir
  del patrón de `match_id`, porque el volcado no trae fechas.

---

## 6. Trampas concretas que ya costaron tiempo

| trampa | qué pasa | cómo evitarla |
|---|---|---|
| `"Club América"` vs `"América"` | el filtro devuelve vacío y la app dice "faltan datos" | el nombre de display no es el valor de `team` |
| `player_id` es `Float64` en el CSV | `pl.concat` revienta contra `Int64` | cast explícito con `strict=False` |
| Absorciones terminales sin `player_id` | filtrar por `is_not_null()` las elimina y $E[T]$ se infla 30% | conservarlas siempre para cantidades de la cadena |
| `unique()` de polars | orden no garantizado; la semilla no controla nada | ordenar antes de barajar |
| `synth.py` incompleto | los tests validan menos de lo que aparentan | el generador debe reproducir el esquema real |
| Umbrales distintos entre scripts | el reporte lista unidades sin artefactos | `MIN_POSESIONES` = `MIN_POSS` |
| Ruta con espacios | `/home/rodrigo/Rodrigo Moreno/...` | siempre comillas |
| venv sin activar | el `python` del sistema no tiene las dependencias | `source .venv/bin/activate` |
| Eje Y de StatsBomb | `y` crece HACIA ABAJO: `y=0` es la izquierda del atacante | `13_verificar_ejes.py` tras tocar `grid.py` |
| `from_state` es un ENTERO | una regex sobre nombres marca todo como absorbente y el simulador sale en 0.00 | usar la fórmula de `mapa_zonas`, no inventar otra |
| Los absorbentes no traen etiqueta | por frecuencia se intercambian remate y balón fuera | criterio físico: gol y remate son ~0 en campo propio |
| Redondear casillas por separado | 20 casillas suman 101% y parece un error de la matriz | método de los restos mayores |
| El espacio de estados por era | una era corta no visita algún estado y la malla no cuadra | derivar el tope del CLUB, no de la era |
| Un generador sintético incompleto | el humo pasa y la página real falla | reproducir el esquema Y los casos límite |

---

## 7. Lo que NO debes hacer

- **No reabrir ADR-17 (GNN) ni ADR-18 (Poincaré).** Descartadas con argumento.
- **No proponer clustering para ajustar λ** (ADR-36): λ ya es por entrenador, y
  agrupar con las mismas matrices que vas a encoger es fuga de prior.
- **No comparar entrenadores entre clubes** como resultado principal (ADR-37).
- **No añadir dependencias externas al HTML** (ADR-38): ni CDN, ni fuentes
  remotas. Su virtud es funcionar sin internet.
- **No difuminar los mapas de calor.** El modelo estima una probabilidad
  constante por zona; suavizar sugiere resolución continua que no existe.
- **No subir la resolución de la malla** mientras la era más chica siga en el
  análisis.
- **No reportar magnitudes con λ>0 sin declarar la atenuación** (ADR-22).
- **No reportar ninguna distancia sin su nula** (ADR-30). Se violó tres veces y
  las tres la conclusión estaba mal.
- **No afirmar la nula.** "No detectamos un efecto mayor a X", nunca "no hay
  efecto".
- **No versionar los CSV de eventos.**
- **No forzar a cero una probabilidad porque «no tiene sentido».** Se propuso
  anular los remates desde campo propio; existen (0.01–0.03%) y forzarlos
  habría ocultado que las etiquetas de los absorbentes estaban mal.
- **No citar una cifra de lift sin su soporte** ni el modo gol de una era con
  menos de 100 goles (§3 bis de `15_REPORTE_HTML.md`).
- **No llamar «el promedio de la liga» a los rivales enfrentados**: cada
  posesión rival se jugó CONTRA este club y la cifra habla también de él.

---

## 8. Cómo trabajar

```bash
cd "~/Hackathon2026"
source .venv/bin/activate
pytest -q          # deben pasar todos antes de tocar nada
```

Al modificar:

1. Cambio pequeño y localizado.
2. **Test que capture el cambio.** Si es un contrato entre dos módulos, el test
   cruza los dos lados (`test_npz_contract.py` existe por eso).
3. `pytest -q` en verde.
4. Documentar: `06_DECISIONS.md` si es una decisión, `02_STATE_OF_PLAY.md` si es
   un arreglo, `10_RESULTADOS.md` si produce un hallazgo.

---

## 9. El perfil del usuario

Estudiante de matemáticas aplicadas, ITAM. Ha llevado análisis, probabilidad,
inferencia (IC, EMV, contrastes), procesos estocásticos, simulación (bondad de
ajuste, Monte Carlo, remuestreo, reducción de varianza) y programación lineal
(simplex, dualidad, KKT).

**No ha visto**: estadística bayesiana formal, aprendizaje automático, redes
neuronales.

Implicaciones:

- El encogimiento se presenta como estimador frecuentista tipo James–Stein
  primero; la equivalencia Dirichlet es la segunda lectura.
- Conectar con sus cursos: la matriz fundamental es álgebra lineal más serie de
  Neumann; el LRT es contraste simple vs compuesta; el KS con bootstrap
  paramétrico es su tema de bondad de ajuste; Wasserstein es transporte a costo
  mínimo con interpretación dual.
- **Si no puede explicar por qué funciona, no va en la presentación.**

**El usuario pide parar cuando falta verificar algo.** Ha detenido la generación
de documentación dos veces para correr un diagnóstico antes. Respétalo: es la
razón de que el proyecto esté validado.

---

## 10. Plantilla de mensaje para retomar

> Estoy retomando `dt-decoder` (decodificador táctico de entrenadores con
> cadenas de Markov absorbentes sobre eventos StatsBomb de Liga MX). He leído
> `docs/13_CONTEXTO_IA.md`, `02_STATE_OF_PLAY.md` y `10_RESULTADOS.md`.
>
> Entiendo que:
> - Fases 0–3 validadas sobre América **y** Cruz Azul; el entregable es
>   `reporte.html`.
> - Los **doce** bugs del proyecto fueron **silenciosos**; el #13 se
>   **evitó** diagnosticando el esquema antes de estimar (ADR-42).
> - Markov de primer orden fue **rechazado** por sobredispersión; ADR-21 explica
>   por qué se mantiene.
> - λ está débilmente identificado: significancia con λ\*, magnitudes con λ=0.
> - Las fechas de partido son **sintéticas derivadas** (ADR-26).
> - El "núcleo estable" del control de plantel es **circular** (ADR-33); el
>   argumento válido es el intra-jugador (ADR-34).
> - Ninguna distancia se reporta sin su nula (ADR-30).
> - La orientación del eje Y está **verificada** (bug #12, P-09 cerrada):
>   `y` crece hacia abajo. Reverificar con `13_verificar_ejes.py` tras
>   cualquier cambio en `grid.py`.
>
> Quiero trabajar en [X]. Antes de modificar código voy a activar el venv y
> correr `pytest -q`.
