# AGENTS.md — instrucciones para agentes de IA

> Este archivo vive en la **raíz** del repositorio. Antigravity, Claude Code,
> Cursor, Copilot Workspace y Codex lo leen automáticamente al abrir el
> proyecto. Si eres un agente y solo vas a leer un archivo, lee este.
>
> `dtdecoder 0.6.0` · última revisión 2026-08-26

---

## 0. La regla que gobierna este repositorio

> **En este dominio los errores no lanzan excepciones: producen números
> plausibles y equivocados.**

**Veinte bugs encontrados. Veinte silenciosos. Cero excepciones.** Uno más (#13) se
evitó porque se diagnosticó el esquema antes de estimar.

Consecuencia operativa, sin matices:

- *"El código corre"* **no es evidencia de nada** en este proyecto.
- Un cambio no está terminado hasta que existe un test que verifica **el
  número**, no la ejecución.
- Si el test cruza dos módulos, **debe probar los dos lados**. Existe
  `tests/test_npz_contract.py` porque un test verde probaba media mitad del
  contrato mientras el guardarraíl abortaba siempre.

Los dos bugs más instructivos del proyecto **no vinieron de código equivocado**,
sino de dos decisiones correctas por separado que juntas se anulaban (#10) y de
un patrón demasiado limpio para ser real (#11). Busca ese género.

---

## 1. Qué es esto en cinco líneas

Un sistema que responde *"¿cómo juega este entrenador?"* usando solo eventos de
fútbol de Hudl StatsBomb (Liga MX). El modelo es una **cadena de Markov
absorbente** sobre estados (zona del campo × fase de origen de la posesión). De
la cadena salen tres cantidades con significado futbolístico: cuánto dura una
posesión, dónde vive el equipo, y con qué probabilidad acaba en gol.

**El entregable es `reporte.html`**: un archivo autocontenido, sin CDN ni
fuentes remotas, que se abre con doble clic.

No es un modelo predictivo. No valora jugadores. No dice quién es mejor
entrenador. **Describe estilo y mide la incertidumbre de esa descripción.**

---

## 2. Orden de lectura, con presupuesto de contexto limitado

| # | Documento | Por qué |
|---|---|---|
| 1 | `docs/13_CONTEXTO_IA.md` | escrito para ti |
| 2 | `docs/02_STATE_OF_PLAY.md` | dónde estamos y qué está bloqueado |
| 3 | `docs/10_RESULTADOS.md` | **no cites ninguna cifra sin leer su fila** |
| 4 | `docs/06_DECISIONS.md` | 48 ADRs. **No reabrir debates cerrados** |
| 5 | `docs/11_MATEMATICA_APLICADA.md` | qué es cada objeto y por qué funciona |
| 6 | `docs/01_ARCHITECTURE.md` | qué hace cada archivo y qué rompe al tocarlo |
| 7 | `docs/04_DATA_CONTRACT.md` | trampas del formato StatsBomb |
| 8 | `docs/05_VALIDATION.md` | antes de reportar cualquier número |
| 9 | `docs/15_REPORTE_HTML.md` | antes de tocar el entregable |

Cada hallazgo de `10_RESULTADOS.md` lleva una etiqueta 🟢🟡🔴⚪ y un caveat.
**Varios fueron retirados tras investigarlos** — §16 del mismo documento lista
las retractaciones. Citar un número retirado es el peor error posible aquí.

---

## 3. Flujo obligatorio

```bash
cd "~/Hackathon2026"
source .venv/bin/activate     # el python del sistema es 3.14 y no tiene deps
pytest -q                     # debe estar en verde ANTES de tocar nada
```

Al modificar:

1. Cambio pequeño y localizado.
2. **Test que capture el número.** Si es un contrato entre módulos, cruza los
   dos lados.
3. `pytest -q` en verde.
4. Documentar: `06_DECISIONS.md` si es una decisión, `02_STATE_OF_PLAY.md` si es
   un arreglo, `10_RESULTADOS.md` si produce un hallazgo.
5. `python docs/verificar_docs.py` — comprueba que la documentación no se
   contradice a sí misma.

Si tocas el reporte HTML, además:

```bash
python scripts/verifica_reporte.py    # JS/CSS válidos, variables declaradas
python scripts/humo_reporte.py        # renderiza la página con datos sintéticos
```

---

## 4. Prohibiciones duras

Cada una tiene una ADR detrás. **No las reabras sin argumento nuevo.**

| No hacer | Por qué | Ref |
|---|---|---|
| Reabrir GNN o secciones de Poincaré | descartadas con argumento; StatsBomb 360 son instantáneas, no tracking | ADR-17, ADR-18 |
| Añadir dependencias pesadas (torch, tensorflow, pymc) | — | ADR-19 |
| Hardcodear cualquier parámetro | va a `config/default.yaml` con comentario | ADR-20 |
| Reportar magnitudes con λ>0 sin declarar la atenuación | el factor varía por renglón | ADR-22 |
| Reportar cualquier distancia (TV, Wasserstein) sin su nula | **se violó tres veces y las tres la conclusión estaba mal** | ADR-30 |
| Ordenar la huella táctica por G² o por z | ambos escalan con el tamaño de muestra; ordena por `TV_exceso` | ADR-25, ADR-28 |
| Afirmar la nula | la frase es *"no detectamos un efecto mayor que X"*, nunca *"no hay efecto"* | — |
| Usar `detect_regime_changes` para validar fronteras de era | probado por placebo, no funciona | 10 §12 🔴 |
| Subir la resolución de malla con eras chicas en el análisis | `params_per_obs` > 0.5 | ADR-25, ADR-46 |
| Agrupar entrenadores por clustering para ajustar λ | es fuga de prior en forma sutil | ADR-36 |
| Comparar entrenadores **entre clubes** como resultado principal | absorbe plantilla, presupuesto y calendario | ADR-37 |
| Añadir dependencias externas al HTML (CDN, fuentes) | su virtud es funcionar sin internet | ADR-38 |
| Difuminar los mapas de calor | el modelo estima probabilidad constante por zona | ADR-38 |
| Versionar los CSV de eventos | datos licenciados de StatsBomb | — |
| Citar una cifra de presión sin decir "por posesión" o "por acción" | son dos estimandos y difieren en signo | ADR-48, 10 §21 |

---

## 5. Trampas concretas que ya costaron tiempo

| trampa | qué pasa | cómo evitarla |
|---|---|---|
| `"Club América"` vs `"América"` | el filtro devuelve vacío y la app dice "faltan datos" | el nombre de display no es el valor de `team` |
| `play_pattern` | etiqueta la **posesión entera**, no el evento | leer `04_DATA_CONTRACT.md` §3.4 |
| `under_pressure` | es una **bandera**: 114,552 true / 0 false / 468,963 null. Filtrar por `is_not_null()` da π≈1 en todas partes, en silencio | `fill_null(False)`, ADR-42 |
| `infer_schema_length` de polars | por defecto 100 filas; columnas raras quedan `Null` y los filtros devuelven vacío sin error | `infer_schema_length=None` |
| Absorciones terminales sin `player_id` | filtrarlas infla $E[T]$ un 30% | conservarlas siempre |
| `unique()` de polars | el orden no está garantizado; la semilla no controla nada | ordenar antes de barajar |
| Eje Y de StatsBomb | `y` crece **hacia abajo**: `y=0` es la izquierda del atacante | `13_verificar_ejes.py` tras tocar `grid.py` |
| Ruta con espacios | `/home/rodrigo/Rodrigo Moreno/...` | siempre comillas |
| venv sin activar | `python` del sistema es 3.14 | `source .venv/bin/activate` |
| Umbrales distintos entre scripts | el reporte lista unidades sin artefactos | `MIN_POSESIONES` = `MIN_POSS` = 1500 |

---

## 6. El perfil del usuario, y qué implica

Estudiante de matemáticas aplicadas, 6º semestre, ITAM. Ha cursado análisis,
topología, probabilidad, inferencia (IC, EMV, EMM, contrastes simple vs
compuesta), sistemas dinámicos, simulación (bondad de ajuste, Monte Carlo, MCMC,
remuestreo, reducción de varianza), procesos estocásticos y programación lineal
(simplex, dualidad, KKT, Farkas).

**No ha visto**: estadística bayesiana formal, aprendizaje automático, redes
neuronales.

Cómo explicar, en consecuencia:

- El encogimiento va **primero** como estimador frecuentista tipo James–Stein;
  la equivalencia Dirichlet es la segunda lectura, no la primera.
- Conecta con sus cursos: la matriz fundamental es álgebra lineal más serie de
  Neumann; el LRT es contraste simple vs compuesta; el KS con bootstrap
  paramétrico es su tema de bondad de ajuste; Wasserstein es transporte a costo
  mínimo con interpretación dual.
- **Si no puede explicar por qué funciona, no va en la presentación.**

**El usuario pide que se pare cuando falta verificar algo.** Ha detenido la
generación de documentación dos veces para correr un diagnóstico antes.
Respétalo: es la razón de que el proyecto esté validado. Si te pide algo cuya
premisa no puedes comprobar, dilo antes de escribir código.

---

## 7. Qué NO debes pedirle nunca

Los CSV de eventos (`eventos_completos_*.csv`). Son datos licenciados de
StatsBomb, pesan cientos de MB y no se versionan. Si necesitas ver el formato,
lee `docs/04_DATA_CONTRACT.md` o pide una muestra de 100 filas.

---

## 8. Estado actual

**Fases 0–3 completas y validadas sobre dos clubes independientes** (Club
América y Cruz Azul; 333 partidos, 12 eras de entrenador). **Bloque defensivo
D1 (presión) completo** y ya integrado en el reporte HTML.

Todo titular lleva intervalo de confianza, y los intervalos están validados por
cobertura empírica (0.944 contra 0.95 nominal).

Lo que sigue, en orden de retorno: sensibilidad a `min_carry_length`;
validación externa contra xG/OBV; fechas reales del API; los 18 equipos; Fase 8
(Wasserstein).

---

## 9. Plantilla de mensaje para retomar

> Estoy retomando `dt-decoder` (decodificador táctico de entrenadores con
> cadenas de Markov absorbentes sobre eventos StatsBomb de Liga MX). He leído
> `AGENTS.md`, `docs/13_CONTEXTO_IA.md`, `docs/02_STATE_OF_PLAY.md` y
> `docs/10_RESULTADOS.md`.
>
> Entiendo que:
> - Fases 0–3 y el bloque defensivo D1 están validados sobre América **y** Cruz
>   Azul; el entregable es `reporte.html`.
> - Los veinte bugs del proyecto fueron **silenciosos**, y el #13 se evitó
>   diagnosticando el esquema antes de estimar.
> - Markov de primer orden fue **rechazado** por sobredispersión; ADR-21 explica
>   por qué se mantiene igual.
> - λ está débilmente identificado: significancia con λ\*, magnitudes con λ=0.
> - Las fechas de partido son **sintéticas derivadas** (ADR-26), no del API.
> - El "núcleo estable" del control de plantel es **circular** (ADR-33); el
>   argumento válido es el intra-jugador (ADR-34).
> - Ninguna distancia se reporta sin su nula (ADR-30).
> - Toda cifra de presión declara si es **por posesión** o **por acción**
>   (ADR-48): los dos estimandos difieren en signo.
> - Hay tres afirmaciones **retiradas** en `10_RESULTADOS.md` §16 que no deben
>   volver a citarse.
>
> Quiero trabajar en [X]. Antes de modificar código voy a activar el venv y
> correr `pytest -q`.
