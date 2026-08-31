# 12 — Qué hacer cuando llegue el API de StatsBomb

> El proyecto funciona hoy **sin** acceso al API, usando fechas derivadas y eras
> investigadas a mano. Este documento explica exactamente qué se sustituye
> cuando llegue el acceso, en qué orden, y qué NO cambia.
>
> Está escrito para que alguien —persona o IA— pueda ejecutar la migración sin
> haber participado en el proyecto.

---

## 1. Lo que falta hoy y por qué

| falta | consecuencia actual | criticidad |
|---|---|---|
| `match_date` | fechas **sintéticas** derivadas de `match_id` (ADR-26) | alta |
| entrenador por partido | `coach_eras.csv` investigado a mano en Wikipedia | alta |
| los otros 16 equipos | el prior son los rivales, no la liga | media |
| datos 360 (freeze frames) | Fase 5 (defensa) imposible | baja |

**Ninguna bloquea el proyecto.** Todas lo mejoran.

---

## 2. Prioridad 1 — preguntar antes de programar

Antes de escribir código, **manda un correo a los organizadores** con estas tres
preguntas. Cada una puede ahorrar una tarde entera:

1. **¿El endpoint de partidos expone `manager` o `managers`?**
   La API de StatsBomb incluye información de entrenador en el objeto de
   partido. Si está disponible en su suscripción, el archivo `coach_eras.csv`
   deja de ser investigación documental y pasa a ser un `groupby`. Elimina de un
   golpe la limitación §7.1 de `02_STATE_OF_PLAY.md` (el prior son rivales,
   no la liga).

2. **¿Hay acceso a todas las competencias de la ventana?**
   Los datos actuales cubren Liga MX regular y liguilla. Si hay Copa, Concachampions
   o Leagues Cup, los `match_id` de esas competencias podrían romper el supuesto
   de bloques del derivador (ADR-26).

3. **¿Se puede publicar agregados?**
   `08_REPRODUCIBILITY.md` §4.2 propone publicar las matrices de conteo en vez
   de los eventos. Una matriz 84×84 sobre 120,000 eventos no es reidentificable,
   pero conviene tener el permiso por escrito.

**Una respuesta afirmativa a la pregunta 1 vale más que todo lo demás de este
documento.**

---

## 3. Prioridad 2 — fechas reales

### Cómo bajarlas

```bash
uv pip install statsbombpy
export SB_USERNAME=...  SB_PASSWORD=...

# 1. ver qué competencias hay disponibles
python scripts/fetch_match_dates.py --list

# 2. bajar todas las temporadas de Liga MX
python scripts/fetch_match_dates.py --auto --out data/match_dates.csv
```

El script emite `(match_id, match_date, home_team, away_team, competition,
season)`. Solo las dos primeras columnas son necesarias.

### Qué NO hay que cambiar

**Nada aguas abajo.** El formato de salida es idéntico al de
`01_derivar_fechas.py`, y `eras.load_match_dates` solo pide `match_id` y
`match_date`. Toda la maquinaria de `eras.py` sigue igual.

Fue una decisión de diseño deliberada: el apaño vive en un solo script y es
reemplazable sin efecto colateral.

### Verificación obligatoria tras el cambio

```bash
dtdecoder phase0 --src eventos_completos_america.csv \
  --eras data/coach_eras.csv --match-dates data/match_dates.csv \
  --club "América" --outdir data/processed
```

Comparar la tabla de cobertura contra la que produjeron las fechas derivadas:

| DT | con fechas derivadas | con fechas reales |
|---|---|---|
| Jardine | 93 | ? |
| Solari | 39 | ? |
| Ortiz | 26 | ? |
| Herrera | 17 | ? |

**Las diferencias esperadas son de 2–3 partidos**, concentradas en Apertura 2022
(el cambio Solari→Ortiz a media temporada). Si alguna era cambia en más de 5
partidos, algo está mal en el CSV de eras, no en las fechas.

**Este contraste es material de reporte**: demuestra que el método de derivación
funcionaba, con su error cuantificado.

---

## 4. Prioridad 3 — el entrenador desde el API

### Si el API expone `manager`

```python
import polars as pl
from statsbombpy import sb

m = sb.matches(competition_id=CID, season_id=SID, creds=creds)
# `home_managers` / `away_managers` suelen venir como lista de dicts
# con 'name', 'nickname', 'dob', 'country'
```

Con eso, `coach_eras.csv` se genera automáticamente: agrupar por entrenador,
tomar el primer y el último partido de cada racha continua, y emitir
`(coach, start_date, end_date)`.

**Cuidado con dos cosas:**

1. **Rachas no contiguas.** Joaquín Moreno dirigió Cruz Azul en dos periodos
   separados. `eras.load_eras` **rechaza eras solapadas** y una era es por
   definición un periodo continuo, así que hay que emitirlas como
   `Moreno I` y `Moreno II`.
2. **Interinatos de un partido.** Gilberto Adame dirigió al América una vez.
   Filtrar por debajo del umbral de potencia (`05_VALIDATION.md` §4.7) o
   quedarán eras con dos posesiones.

### Si el API NO lo expone

El procedimiento manual está probado y funciona: se investigó Wikipedia para
ambos clubes y la cobertura resultante coincide con el registro documental
(ver `02_STATE_OF_PLAY.md` §3).

Formato:

```csv
coach,start_date,end_date
Miguel Herrera,2017-01-01,2021-12-05
Santiago Solari,2021-12-15,2022-10-09
```

Reglas:
- Sin acentos en los nombres (consistencia con `eras.AMERICA_ERAS`).
- Sin solapamientos: `load_eras` lanza `ValueError`.
- Los huecos entre eras están permitidos; esos partidos salen como
  `unmapped_matches`.
- **Verificar las fechas de cese**, no solo las de nombramiento. Wikipedia suele
  dar el año, no el día.

Coste real medido: una tarde por club. Cruz Azul, con once entrenadores en la
ventana, fue el caso difícil.

---

## 5. Prioridad 4 — los 18 equipos

### Lo que realmente se gana

**No es lo que parece.** El beneficio principal NO es más datos para estimar,
porque λ se elige por validación cruzada sobre el **foco**, no sobre el prior, y
la curva de CV es una meseta (§7.2 de `02_STATE_OF_PLAY.md`).

Lo que se gana es **validez**:

1. **Muere la amenaza 4.3 de `05_VALIDATION.md`.** Hoy el prior son los 17
   rivales que el América enfrentó, con la composición de su calendario. No es
   una muestra aleatoria de la liga. Con los 18 equipos, sí lo es.

2. **λ\* cambia de significado.** La lectura actual —*"el América se parece
   bastante a sus rivales"*— **no sobrevive** al cambio de prior. Hay que
   recalcularla y reescribir esa frase.

3. **Posiblemente una malla más fina.** Los criterios de esparsidad
   (`frac_below_min`, `params_per_obs`) miden el sobreajuste del **EMV crudo**,
   pero el proyecto usa el estimador **encogido**, que toma prestada fuerza del
   prior. Con un $q$ mucho mejor estimado se podría encoger más y sostener 6×4
   con la misma muestra. **Los criterios actuales son conservadores por
   construcción.** Merece repetir el barrido midiendo el error del estimador
   encogido en vez de contar parámetros.

4. **40–60 eras de entrenador** en vez de 12.

   > **PREGUNTA YA CONTESTADA (2026-08-26).** Se midió con las doce eras
   > actuales: $\tau = 0.596$ acciones/posesión contra un suelo de detección
   > de 0.247 — **2.4× por encima**. Hay variación real **entre eras**, y es
   > pequeña (ICC 0.9%). Ojo con la etiqueta: esa varianza contiene al
   > entrenador **y también** plantel y contexto, y este diseño no los separa
   > (`10_RESULTADOS.md` §25.5). Ver también ADR-49.
   >
   > Lo que el escalado aporta ahora es **potencia**, y con un argumento
   > cuantitativo: la simulación mostró que la detección la manda el **número
   > de unidades**, no su tamaño. Con 4 eras el estimador devuelve cero el
   > 32% de las veces habiendo variación real; con 12, el 7%; con ~50, el 0%.
   > **El beneficio de los 18 equipos no es más datos por unidad: son más
   > unidades.**

### Lo que NO se arregla

**La rotación de Liga MX.** El mallado lo limita la **era más corta que quieras
analizar**, no el volumen total. Un DT con 15 partidos no es analizable con
ninguna malla razonable, tengas 2 clubes o 18. Eso no es un defecto del método:
es un hallazgo sobre el fútbol mexicano y conviene reportarlo como tal.

### El coste real

**No son las corridas: son los CSV de eras.** Dieciocho clubes son dieciocho
tardes de investigación documental, salvo que el API exponga `manager` (§4).

### Procedimiento

```bash
# por cada club nuevo
python scripts/01_derivar_fechas.py --events eventos_<club>.csv \
  --club "<Club>" --out data/match_dates_<club>.csv
dtdecoder phase0 --src eventos_<club>.csv --eras data/coach_eras_<club>.csv \
  --match-dates data/match_dates_<club>.csv --club "<Club>" \
  --outdir data/processed_<club>
bash scripts/generar_todo.sh
python scripts/12_reporte_html.py
```

Añadir el club a `CLUBES` en `12_reporte_html.py` y `app.py`, y su paleta a
`TEMA` en el HTML.

---

## 6. Lo que NO conviene hacer

### No agrupar entrenadores por clustering para ajustar λ

Suena razonable —encoger hacia técnicos de estilo parecido en vez de hacia
"todos los demás"— y formalmente es un modelo jerárquico con grupos. Pero tiene
una trampa: **agruparías usando las mismas matrices que luego vas a encoger**.
El grupo de Jardine se define en parte por Jardine, así que su prior lo
contendría.

Es **exactamente ADR-06 (fuga de prior) en una forma más sutil y más difícil de
detectar**. Se puede hacer bien —excluyendo al foco al construir el clúster—
pero es maquinaria nueva con su propia validación para un beneficio incierto.

Además, **λ ya es personalizado por entrenador**: `cv_lambda` corre sobre las
transiciones del foco.

### No comparar entrenadores entre clubes como resultado principal

La distancia de variación total compara cualquier par de distribuciones sobre el
mismo espacio de estados; matemáticamente no hay obstáculo. El problema es de
interpretación: la distancia entre Jardine (América) y el DT del Mazatlán
absorbe diferencia de plantilla, presupuesto y calendario. Es el confusor que
ADR-16 evita al comparar dentro del mismo club.

**Si aun así se quiere cruzar clubes**, la forma correcta es comparar *cuánto se
desvió cada técnico de la línea base de su propio club* (diferencias en
diferencias). Pero arrastra dos problemas:

- La línea base de un club **contiene a sus propios entrenadores**. Jardine es
  el 53% de las transiciones del América, así que "el América histórico" *es en
  buena parte Jardine*. Habría que excluir al foco de su propia base.
- Las TV **no son comparables entre clubes sin su nula**. Un club con eras más
  cortas tendrá TV mayor por ruido de muestreo, no por táctica (ADR-30).

### No usar la matriz agregada del club como titular

El reto pide un **entrenador**. La matriz del club sirve como línea base, no
como resultado. Ya está disponible: `dtdecoder phase1 --unit team --value "América"`.

---

## 7. Datos 360 y la Fase 5

Los *freeze frames* y el polígono `visible_area` **no están en el volcado
actual**: hay que traerlos por separado del API.

Habilitan la fase defensiva (`00_ROADMAP.md` §5), que requiere un proceso de
Poisson no homogéneo con corrección por adelgazamiento para la censura del área
visible.

**Advertencia**: StatsBomb 360 son instantáneas en el momento de cada evento,
**no tracking**. No hay velocidades ni trayectorias. Es la razón por la que se
descartó el enfoque de GNN (ADR-17), y sigue siendo válida.

---

## 8. Checklist de migración

- [ ] Preguntado a los organizadores por `manager` en el endpoint de partidos
- [ ] `SB_USERNAME` / `SB_PASSWORD` exportadas
- [ ] `data/match_dates.csv` bajado del API
- [ ] Cobertura por era comparada contra la de fechas derivadas (§3)
- [ ] Diferencias de más de 5 partidos investigadas
- [ ] `coach_eras.csv` regenerado desde el API o verificado a mano
- [ ] `dtdecoder phase0` recorrido, `unmapped_matches` revisado
- [ ] `bash scripts/generar_todo.sh` recorrido
- [ ] **λ\* recalculado y su interpretación reescrita** si cambió el prior
- [ ] `10_RESULTADOS.md` actualizado: las magnitudes van a cambiar
- [ ] `02_STATE_OF_PLAY.md` §3: la sección de fechas derivadas pasa a histórica
- [ ] ADR-26 marcada como superada, no borrada
