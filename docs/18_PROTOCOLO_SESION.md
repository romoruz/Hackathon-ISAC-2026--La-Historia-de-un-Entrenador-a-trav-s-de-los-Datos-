# 18 — Protocolo de sesión: cómo se trabaja este repositorio con una IA

> Escrito el 2026-09-14, al final de la sesión que cerró H2 y H3. Su propósito
> es que un chat nuevo —o una persona nueva— retome sin reconstruir de memoria
> cómo se opera. `13_CONTEXTO_IA.md` explica **qué** es el proyecto; este
> explica **cómo** se trabaja en él.

---

## 1. La máquina y las rutas

```
repo:   /home/rodrigo/Rodrigo Moreno/Codigos Deportes/Hackathon2026
paquetes que llegan por chat:  ~/Descargas
```

**La ruta tiene espacios.** Siempre entre comillas. Es la primera línea de
cualquier bloque que se pegue en la terminal:

```bash
cd "/home/rodrigo/Rodrigo Moreno/Codigos Deportes/Hackathon2026"
```

> **La trampa más repetida de la sesión anterior**: tras instalar un paquete,
> la terminal se queda en `~/Descargas`. El prompt muestra `(Hackathon2026)`,
> que es el **nombre del venv**, no el directorio. Se ve así y engaña:
>
> ```
> (Hackathon2026) [rodrigo@Dell-Inspiron Descargas]$
>                                          ^^^^^^^^^ el directorio real
> ```
>
> Pasó cuatro veces. Todo bloque de comandos debe empezar con el `cd`, y todo
> `cp` hacia un directorio nuevo debe llevar `mkdir -p` delante.

## 2. Los dos entornos virtuales

Son **dos y no se mezclan**. Es la regla 2 de `16_MIGRACION_API.md` §9:
`statsbombpy` arrastra pandas y numpy, y meterlos en el entorno del pipeline
invita a deriva numérica.

| entorno | para qué | qué tiene |
|---|---|---|
| `.venv` | el pipeline, los tests, `dtdecoder` | polars, numpy, scipy, el paquete instalado |
| `.venv-sb` | bajar y adaptar datos del API | statsbombpy, pandas, pyarrow |

```bash
deactivate 2>/dev/null; source .venv/bin/activate      # pipeline
deactivate 2>/dev/null; source .venv-sb/bin/activate   # API
```

Síntoma de estar en el equivocado: `bash: dtdecoder: orden no encontrada` o
`No module named dtdecoder`. **No es un problema de `PYTHONPATH`**: el paquete
está instalado, pero en el otro entorno. Nunca "arreglarlo" con
`PYTHONPATH=src python src/dtdecoder/cli.py`: eso rompe los imports relativos y,
si arrancara, correría con el numpy equivocado.

El puente entre los dos entornos son **archivos en disco**, nunca imports.

## 3. Cómo llegan los cambios: paquetes

Todo cambio de código llega como un `.tar.gz` con esta forma:

```
paquete_h2_NN/
├── INSTALAR.sh      ← respalda, instala, y VERIFICA
├── LEEME.md         ← qué cambia y por qué
├── scripts/…
├── src/dtdecoder/…  ← solo si toca el paquete
└── tests/…
```

```bash
cd ~/Descargas && tar xzf paquete_h2_NN.tar.gz && bash paquete_h2_NN/INSTALAR.sh
```

Reglas de la convención, todas aprendidas a golpes:

- **Nada se sobrescribe sin respaldo.** Cada archivo reemplazado deja
  `<archivo>.anterior_AAAAMMDDHHMM`. Revertir es un `mv` inverso.
- **El instalador verifica**, no solo copia: compila, comprueba que los
  símbolos de `dtdecoder` que usan los scripts existen de verdad, y corre
  `pytest -q` si toca `src/`.
- **Revertir solo si la verificación falla.** En la sesión anterior se ejecutó
  el bloque de revert después de un resultado correcto, y dejó el árbol
  inconsistente: los archivos con respaldo volvieron atrás y los nuevos se
  quedaron, con `pytest` en rojo por imports rotos.
- **Los paquetes se numeran y no se reutilizan.** Si un paquete falla, el
  siguiente lleva el número siguiente, no una corrección silenciosa del mismo.

## 4. Disciplina de verificación

Es lo que distingue este proyecto. La regla de `13_CONTEXTO_IA.md` §2 —*los
errores no producen excepciones, producen números plausibles pero
equivocados*— gobierna también la operación, no solo el código:

1. **Pegar la salida real de la terminal, no el resumen.** Un «salió como
   esperabas» no es evidencia. En la sesión anterior, dos veces un `diff` dijo
   `OK` porque el comando anterior había fallado y no se regeneró nada.
2. **Antes/después con la misma fuente.** Toda regresión se corre sobre los
   mismos datos y las mismas entradas que produjeron el resultado original. Si
   cambian los datos, el diff no prueba nada sobre el código.
3. **Guardar el log**: `2>&1 | tee /tmp/loquesea.log`. Y para corridas largas,
   `nohup … &` con `tail -f`.
4. **Escribir a un directorio nuevo** cuando el resultado puede reemplazar a
   uno publicado. Elegir después cuál de dos corridas se publica es selección.
5. **Comprobar el código de salida.** `echo "salida: ${PIPESTATUS[0]}"` tras un
   `| tee`.

## 5. Mapa de datos y artefactos

```
data/
├── raw_api/                    ← del API. NO se versiona (licencia)
│   ├── indice_partidos.csv     ← metadatos: match_id, fecha, equipos, etapa
│   ├── matches/*.json.gz       ← incluye `managers`: la fuente de las eras
│   └── events/*.json.gz        ← 1,854 partidos
├── eras_api/                   ← SÍ se versiona
│   ├── eras_todas.csv          ← 134 eras, banderas, n_partidos, n_en_rango
│   ├── absorbidos.csv          ← 6 partidos de interinos dentro de otra era
│   └── asignacion_partidos.csv
├── eras_compat/                ← coach_eras_<slug>.csv, 3 columnas, para load_eras
├── eras_verificadas.csv        ← LO LLENA UN HUMANO. Destraba el candado
├── api/                        ← derivado, NO se versiona
│   ├── eventos_api_ligamx/     ← 13 partes parquet, 4,983,649 eventos
│   ├── eventos_api_america/    ← el club de la regresión
│   ├── clubes/<slug>/          ← subconjunto por club (filtro del de liga)
│   ├── match_dates_<slug>.csv  ← lo emite el adaptador, misma corrida
│   └── match_dates_ligamx.csv
├── prior_liga/                 ← `dtdecoder prior`. SOLO como prior q
└── processed_api_<slug>/       ← phase0 por club, 18 directorios
reports/                        ← los JSON que lee el reporte HTML
logs/                           ← un log por club del bucle de phase0
```

**`--src` es un DIRECTORIO**, no un archivo: el adaptador escribe por partes y
`ingest.scan_events` acepta directorios.

## 6. El pipeline, de principio a fin

```bash
cd "/home/rodrigo/Rodrigo Moreno/Codigos Deportes/Hackathon2026"

# --- entorno del API ---
source .venv-sb/bin/activate
python scripts/01_construir_eras.py --excluir-liguilla \
    --excluir-temporadas 351 --dump-asignacion
python scripts/02_adaptar_eventos.py --todos --formato parquet \
    --excluir-liguilla --excluir-temporadas 351

# --- entorno del pipeline ---
deactivate; source .venv/bin/activate
python scripts/03_subconjuntos_por_club.py
dtdecoder prior --src data/api/eventos_api_ligamx \
    --match-dates data/api/match_dates_ligamx.csv \
    --eras-dir data/eras_compat --outdir data/prior_liga
bash scripts/corre_phase0_todos.sh
python scripts/24_linea_base_contemporanea.py --indirs data/processed_api_* \
    --prior-from data/prior_liga --out reports/linea_base_contemporanea.json
python scripts/25_pares_h4.py --indirs data/processed_api_* \
    --prior-from data/prior_liga --out reports/pares_h4.json
python scripts/26_bitacora_h2h4.py --out docs/17_SECCION_H2H4.md
```

Duraciones medidas: adaptador de liga ~20–30 min · `dtdecoder prior` <1 min ·
los 18 `phase0` ~10 min · el barrido de pares ~20–60 min.

El alcance es **fase regular, sin temporada 351**: 1,530 partidos, 18 equipos,
10 torneos (C2022…C2026 en orden cronológico real, que **no** es el
alfabético).

## 7. Reglas preinscritas vigentes

No se renegocian sin escribirlo primero:

- magnitudes a λ=0, significancia a λ\* (ADR-22);
- ninguna distancia sin su nula (ADR-30);
- solo pares dentro del mismo club (ADR-16/37);
- malla fijada en **5×4 a priori**; el barrido es sensibilidad, no decisión;
- FDR sobre una familia declarada de antemano;
- ninguna era `PRIMERA_DE_VENTANA` sin verificar entra a un resultado;
- la nula de **muestreo** decide la significancia; la distribución empírica
  entre unidades de la liga es **contexto**, nunca criterio de rechazo.

## 8. Lo que está abierto

1. Verificar las 6 eras `PRIMERA_DE_VENTANA` analizables (Larcamón/Puebla 51,
   Lillini/Pumas 51, Herrera/Tigres 51, Ferretti/Juárez 34, Holan/León 32,
   San José/Mazatlán 26) y añadir Solari/América. Se verifican **por conteo de
   partidos** contra una fuente externa, no por fecha. Van a
   `data/eras_verificadas.csv` con `club,coach,n_esperado,fuente,fecha`.
2. Relanzar `25_pares_h4.py` a un **archivo nuevo** con las eras destrabadas.
3. **H5** con el diseño correcto: perfil absoluto con el efecto del club fuera.
   Los deltas contra predecesores distintos **no** sirven para esto.
4. **H6**: τ² y confiabilidad con 53 unidades en vez de 12.
5. **H7**: el reporte HTML, reescrito entero.
6. **Recalcular D1 (presión)**: `pressure_rate` pasó de 0.2104 a 0.2204 con los
   datos del API y no está en la tabla de retirados de `16_MIGRACION_API.md` §2.

## 9. Cómo debe comportarse la IA en este proyecto

Lo que funcionó y conviene exigir:

- **Parar cuando falte verificar algo.** Es la costumbre del usuario y es la
  razón de que el proyecto esté validado.
- **No dar por buena una cifra sin ver la salida** que la produjo.
- **Declarar lo que no se pudo ejecutar.** La IA no tiene los datos ni el
  entorno: lo que no corrió, se dice.
- **Reconocer los propios bugs y explicar la causa**, no solo el síntoma. En la
  sesión anterior se encontraron varios en código propio: orden alfabético de
  torneos, `possession` agrupado sin `match_id`, una unificación de esquema que
  dependía de la versión de pandas, una variable usada antes de definirse.
- **Preinscribir antes de medir.** Una predicción que falla y se reporta vale
  más que una regla ajustada después.
- **No aceptar una crítica solo por venir con citas.** En la sesión anterior
  hubo varias propuestas plausibles y equivocadas: validar `match_dates` por
  igualdad de conjuntos, refactorizar por un OOM que nunca ocurrió, filtrar
  exclusiones por `match_id` global. Se rechazaron con el código o los números
  delante, no por autoridad.
