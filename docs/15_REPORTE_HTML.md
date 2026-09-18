# 15 — El reporte HTML: contrato del entregable

> `scripts/12_reporte_html.py` produce **el entregable**: la única pieza que el
> jurado va a ver. Leer esto ANTES de tocar el script.
>
> Última revisión 2026-09-18 (h2_31, ADR-59 adenda 2). Sustituye a la versión
> del 2026-08-26, que describía el tablero con simulador (retirado en h2_29).

---

## 1. Qué es y por qué es así

Un **único** archivo `reporte.html` con todos los datos embebidos como JSON, las
gráficas dibujadas en SVG por JavaScript en el navegador, y **cero dependencias
externas**: ni CDN, ni fuentes remotas, ni librerías (ADR-38). Se abre con doble
clic, sin internet, sin servidor y sin Python.

El principio que manda viene del reto:

> *"Su análisis debe permitir que alguien que **no vio los partidos** pueda
> entender con claridad cómo juega el equipo y cuáles son las ideas del
> entrenador."*

Por eso la incertidumbre se dice en palabras (`fuerza(q)`: *"muy sólido"*,
*"sólido, con margen estrecho"*, *"insuficiente tras corregir"*, *"no lo
distinguimos del azar"*). **q sí, p no** (adenda 1 §8): el valor de q se ve en
modo técnico; su lectura en palabras, siempre.

## 2. De dónde saca los datos

```
reports/did_h4_v1.json          duración de la posesión, pares del mismo club (ADR-53)
reports/did_presion_v1.json     presión E1–E5 por pares, seis clubes (ADR-54)
reports/balon_parado_v2.json    córners, modelo de xG (ADR-55)
reports/contexto_v1.json        θ por contexto, casos de ADR-57 (ADR-56/57)
reports/jugadores_v1.json       rotación, roles, primer cambio (ADR-58)
reports/metricas_v1.json        npxG, OBV, pases progresivos, field tilt (D59-P)
reports/deriva_proveedor.json   la deriva del proveedor, por torneo
data/processed_api_<club>/transitions.parquet   mapa de zonas de la era principal
```

- **Si falta un JSON, la sección no miente**: muestra el comando que lo genera.
- **Si falta el parquet**, el mapa de zonas dice qué ruta buscó, o que la ruta
  existe pero no hay filas con ese `team` y ese `coach`.
- **No lee `reports/barrido/`** (adenda 2 §2). Las distancias del barrido
  entran con ADR-60.
- Los archivos por pareja de la etapa vieja (`ic_*`, `plantel_*`, `huella_*`,
  `campo_presion_*`, `presion_indice_*`, `calibracion_*`) **no se usan**.

## 3. Estructura (ADR-59 adenda 2)

```
portada        cinco frases de la historia activa, en ranuras fijas, con enlace
acto 1         común: el marco
acto 2         por historia: cómo juega la era principal
acto 3         por historia: de dónde viene eso
cierre         común: credibilidad, límites, anexo
```

| id | sección | fuente | en h2_31 |
|---|---|---|---|
| `a1-1` | la posesión y sus tres preguntas | esquema | se pinta |
| `a1-2` | la cadena: transitorios y absorbentes | esquema | se pinta |
| `a1-3` | cómo se estiman las probabilidades | esquema | se pinta |
| `a1-4` | en qué confiar (semáforo) | esquema | se pinta |
| `a1-5` | por qué contra la liga del mismo torneo | `deriva_proveedor`, `did_h4 › firma_temporal` | se pinta |
| `a1-6` | dónde vive una posesión viva | ADR-61 | pendiente |
| `a1-7` | por qué no simulamos | texto; la curva es ADR-61 | se pinta, con hueco |
| `a2-1` | cuánto dura y dónde vive | `did_h4 › unidades`, parquet | se pinta |
| `a2-2` | progresión | ADR-61 | pendiente |
| `a2-3` | ocasiones y territorio | `metricas_v1 › global` | se pinta |
| `a2-4` | sin el balón | `metricas_v1`, `did_presion_v1` | se pinta; presión como hueco fuera de ADR-54 |
| `a2-5` | torneo tras torneo | `did_h4 › serie_por_torneo`, `metricas_v1 › por_torneo` | se pinta |
| `a2-6` | contexto | `contexto_v1` | se pinta |
| `a2-7` | balón parado | `balon_parado_v2` | se pinta |
| `a2-8` | jugadores y minutos | `jugadores_v1` | se pinta |
| `a3-1` | el club antes y después de él | `did_h4 › pares` | se pinta |
| `a3-2` | plantel contra uso | ADR-60 | pendiente |
| `a3-3` | mapa de estilos | ADR-60 | pendiente |
| `a3-4` | qué viaja y qué se queda | `did_h4`, `metricas_v1`, `jugadores_v1`, `contexto_v1` | se pinta |
| `c-1` | ¿el método distingue? | todos | se pinta |
| `c-2` | límites | texto | se pinta |
| `c-3` | anexo de errores | catálogo | pendiente |

### Las historias

`HISTORIAS` en el generador: Jardine, Larcamón, Ambriz, Herrera y Ortiz, en
ese orden. Las eras de cada una son las unidades con `coach` **igual** al del
técnico (nunca por subcadena: "Herrera" también es un jugador). La **era
principal** es la de más partidos. El selector cambia la historia y repinta la
página entera; `render()` no guarda estado parcial.

### Las cuatro capas

Toda sección de los actos 2 y 3 lleva los cuatro `data-capa`. Si falta una, se
declara con un bloque `hueco` que dice por qué:

1. frase con semáforo (`frase`, `nulo`);
2. figura (`fig`);
3. "en un partido" (`ejemplo`): cifras de la capa 1 en unidades de un partido.
   **No es una jugada real**;
4. "cómo lo medimos" (`plegable`): estimando, comparación, familia, y archivo
   y campo, citando las reglas del propio JSON.

### Semáforo e interruptor

- Verde = A, ámbar = B, gris = C. Un nulo A va en verde con la marca "nulo". Los
  tokens `--sem-a/b/c` **solo** se usan en las etiquetas de nivel; ninguna
  figura los toca.
- Modo **sencilla** (por defecto): se ocultan `.tec` (intervalos, `q = …`,
  huella de insumos) y se cierran los plegables de la capa 4. Modo
  **técnica**: todo visible, plegables abiertos. El margen de un nulo y la
  lectura de q **nunca** van en `.tec`; hay un test que lo comprueba.

## 4. Redacción

- Una frase, un nivel (ADR-59 §2). B sin intervalo no se construye.
- **Jardine** conserva las lecturas preinscritas de ADR-59 con sus guardas: si
  una deja de sostenerse, el script sale con `LECTURA PREINSCRITA ROTA` y no
  escribe nada.
- **Las otras cuatro** usan plantillas fijas (`cola_B`, `frase_contraste`): A
  "difiere" o nulo con margen; B "por encima / por debajo de la liga" o "no se
  separa de la liga: si hay diferencia, es menor a X"; C conteos y rangos.
  Ninguna frase se elige ni se omite por su resultado.
- Frases prohibidas: `scripts/frases_prohibidas.py` (ADR-59 §3 y adenda 2 §8).
  Si aparece una, el script termina sin escribir.
- Ninguna cifra tecleada: todo número del texto va en `M.c()` (o `M.cita()`
  para reglas copiadas del JSON) con su fuente. `test_cifras_trazables` lo
  verifica en las cinco historias.
- Macros LaTeX (`--tex`): solo salen de Jardine y del acto 1; no pueden chocar
  entre historias.

## 5. Reglas de diseño que NO se pueden romper

1. **Sin dependencias externas** (ADR-38).
2. **Los mapas no se difuminan** (ADR-38): probabilidad constante por zona.
3. **Escala compartida** entre mapas que se comparan (`vmax`).
4. **Tamaño idéntico** entre canchas que se comparan (`.grid par`, `W_MAPA`).
5. **Un solo tono** en las figuras: foco = `--a1`, comparación = aro. Ningún
   color escrito a mano en una figura (el humo busca hex en los lienzos).
6. **Contraste mínimo** 4.5:1; nada por debajo de 10px en un SVG. `.nota` es la
   clase única de texto pequeño.
7. **Vidrio en el chrome, contenido opaco**; `prefers-reduced-transparency`
   apaga el vidrio.
8. **Todo se puede tocar**: tooltips con `mouseover` y con `click`.
9. **Los porcentajes de las casillas suman 100** (restos mayores).

## 6. Trampas conocidas

| trampa | síntoma | causa |
|---|---|---|
| nombre por subcadena | un jugador "Herrera" se cuela en la historia | buscar por `in` en vez de `==` sobre `coach` |
| `"Club América"` vs `"América"` | el mapa de zonas dice 0 filas | `team` es el valor **de la columna** |
| par con otro orden | el signo sale al revés | `par()` devuelve si viene invertido; las frases citan el orden del JSON ("A frente a B") |
| clave `adn` en el JSON embebido | el filtro de frases prohibidas aborta | `\badn\b` es "ADN"; no nombrar así ninguna clave |
| número en prosa | `test_cifras_trazables` en rojo | escribir "primer acto", no "acto 1"; citar con `M.cita()` |
| `var(--x)` sin declarar | texto gris sin error | una `var()` inválida hereda; `verifica_reporte.py` lo detecta |
| `color-mix` | barra vacía en navegadores viejos | color plano antes del gradiente |

## 7. Cómo verificar un cambio

```bash
cd "/home/rodrigo/Rodrigo Moreno/Codigos Deportes/Hackathon2026"
source .venv/bin/activate
python scripts/verifica_reporte.py      # JS compila, CSS cuadra, variables declaradas
python scripts/humo_reporte.py          # datos sintéticos -> página -> DOM real (jsdom)
python -m pytest -q                     # la suite completa
```

El humo recorre las cinco historias y los dos modos. Comprueba, entre otras
cosas: las cuatro capas o su hueco en cada sección; cinco frases de portada con
ancla; los pendientes de ADR-60 y ADR-61; la presión declarada fuera de ADR-54;
que un homónimo no entra a una historia; que el interruptor oculta y abre lo
que debe; que no hay colores cableados ni texto SVG por debajo de 10px; y, sin
`contexto_v1.json`, que 2.6, 3.4 y el cierre muestran el comando que falta.

`node --check` solo dice que el JavaScript **compila**. Todos los bugs de este
proyecto compilaban. Lo que hay que comprobar es que la página **se pinta**.

## 8. Lo que el reporte NO dice, y debe seguir sin decir

- Quién es **mejor** entrenador. Describe estilo, no rendimiento.
- Ningún p-valor.
- Nada causal. "El club pesa más que el técnico" y "su idea viaja" tampoco.
- Ninguna cifra de presión sin decir que es **por acción del rival** (ADR-48).
- Ninguna distancia del barrido antes de ADR-60.

## 9. El generador sintético tiene que reproducir el esquema REAL

`humo_reporte.py` genera los datos con los que se renderiza la página. **Si su
forma no coincide con la de los JSON reales, la prueba valida menos de lo que
aparenta.** Al añadir un campo que el generador lee, añadirlo también al
sintético, **con los casos límite**: el vacío, el bloqueado, el que tiene cero,
el que sobrevive en una historia sin lectura preinscrita, el homónimo.
