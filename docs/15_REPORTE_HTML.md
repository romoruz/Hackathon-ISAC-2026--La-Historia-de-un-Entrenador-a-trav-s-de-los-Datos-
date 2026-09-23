# 15 — El reporte HTML: contrato del entregable

> `scripts/12_reporte_html.py` produce **el entregable**: la única pieza que el
> jurado va a ver. Leer esto ANTES de tocar el script.
>
> Última revisión 2026-09-22 (h2_42: ADR-59 adendas 8 y 9 + ADR-63 en la página: las figuras traen los clubes dentro con escala compartida, la sección de jugadores en 3.1, y el tope de palabras escala con los clubes; h2_41: ADR-59 adenda 7, los clubes lado a lado sin selector, 2.2 compara sus clubes con ADR-61 adenda 1, la jugada de ejemplo al anexo; h2_40: ADR-61 adenda 1 y ADR-63 en los scripts; h2_39: ADR-59 adenda 6, los menús de la barra dejan de estar recortados, un botón por club sin «todos sus clubes», cuatro pies y el recorte al tope; h2_38: ADR-59 adenda 5, primero la historia y al final el método, barra fija con dos menús, selector de club dentro de la sección, espacio de estados explicado, simulador paso a paso, una sola línea de carrera, barras con intervalo en 2.2; h2_37: ADR-59 adenda 4, la carrera y las tres preguntas, sub-selector de club, simulador de flujos y jugadas, figuras de contexto, relevos, estilos y marcador; h2_36: ADR-59 adenda 3, cuerpo corto en lenguaje llano, anexo completo, simulador, sin interruptor; h2_35: ADR-61 en 1.2, 1.6, 1.7, 2.1 y 2.2; h2_34: control y placebo de la adenda 1 de ADR-60 en 3.1; h2_33: ADR-60 en 3.1 a 3.4; estructura de h2_31, ADR-59 adenda 2). Sustituye a la versión
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
reports/relevos_v1.json         T, composición contra uso, predicciones (ADR-60; scripts/42_relevos.py)
reports/estilos_v1.json         mapa de estilos y distancias (ADR-60 §5; scripts/43_mapa_estilos.py)
reports/placebo_v1.json         placebo exploratorio de T, nivel C (ADR-60 adenda 1 §4; scripts/44_placebo_T.py)
reports/progresion_v1.json      llegada a la franja del área, cuasi-estacionaria por era, jugada, predicciones (ADR-61; scripts/45_progresion.py)
reports/jugadores_zona_v1.json  toques por jugador y zona, y la resta entre dos técnicos del mismo club (ADR-63; scripts/47_jugadores_zona.py) — la página lo pinta desde h2_42
reports/simulador_v2.json       conteos 20 × 24 del juego abierto de la liga y de cada era de las cinco historias, y nombres de jugadores (adenda 4 §5-§6; scripts/46_simulador.py)
reports/supervivencia_v1.json   diagnóstico de fase, cuasi-estacionaria de la liga, supervivencia por torneo (ADR-61; scripts/45_progresion.py)
data/processed_api_<club>/transitions.parquet   mapa de zonas de la era principal
```

- **Si falta un JSON, la sección no miente**: muestra el comando que lo genera.
- **Si falta el parquet**, el mapa de zonas dice qué ruta buscó (hueco legítimo).
  **Si existe y no se puede usar** (Python sin polars, archivo roto, 0 filas con
  ese `team` y ese `coach`), el generador termina con `ZONAS ILEGIBLES` y no
  escribe nada (h2_32). Antes salía `zonas FALTA` con código 0 al correrlo
  fuera de `.venv`.
- **No lee `reports/barrido/`** (adenda 2 §2). Las distancias entran por
  `estilos_v1.json`, recalculado desde los JSON; un test lo compara con el barrido.
- Los archivos por pareja de la etapa vieja (`ic_*`, `plantel_*`, `huella_*`,
  `campo_presion_*`, `presion_indice_*`, `calibracion_*`) **no se usan**.

## 3. Estructura (ADR-59 adenda 3; sustituye a la de la adenda 2)

```
portada        nombre y clubes + «qué hicimos» en cinco líneas + las TRES CONCLUSIONES
               (las tres preguntas de 2.0, con enlace a su evidencia) + las cinco frases
leyenda        los tres niveles en palabras (probado, medido, descriptivo) + glosario plegado
primero        por historia: 2.0 a 2.7 («Cómo juega»)
luego          por historia: 3.1 y 3.2 («De dónde viene eso»)
después        común: 1.1, 1.2 y 1.3 («Cómo lo hicimos, si te interesa»)
al final       común: ¿nos creen? y límites
anexo          plegado: todas las secciones viejas COMPLETAS, sin cambiar una cifra
```

**El orden lo fija `ACTOS` en el JS** (`acto2, acto3, acto1, cierre`) y lo comprueba el humo
leyendo los `.acto` del DOM. Ninguna sección cambia de contenido por moverse.

**Portada (adenda 5 §2).** `que_hicimos(M)` es un bloque del modelo dentro de 1.1 marcado
`portada_solo`: los tests de cifras y de jerga lo recorren como cuerpo, `bloque()` no lo
pinta en la sección y `portada()` lo pinta en la cabecera. Las tres preguntas de 2.0 llevan
`| conc(1..3)` y suben a la portada con su enlace, además de quedarse en su sección.

**Regla de construcción.** El anexo de cada sección es la función vieja (h2_35) sin tocar;
el cuerpo es un extracto (`cuerpo_de`: frases de portada primero, las figuras nombradas, el
ejemplo, los huecos) o una función escrita aparte (1.1, 1.2, 3.1, 3.2, cierre). Así "nada
se borra" se cumple por construcción. Cada sección del cuerpo con anexo lleva el enlace
"cómo lo medimos, con todos sus números →".

| id | num | sección | cuerpo | anexo |
|---|---|---|---|---|
| `a1-1` | 1.1 | La cancha, la posesión y cómo termina | `c1_inicios`: «qué hicimos» (portada), 20 zonas × 4 inicios = **80 situaciones vivas** y 4 finales, por qué la malla es 5 × 4 (P-02), un ejemplo de probabilidad de paso desde `simulador_v2 › liga.C`, la frase de los bloques | `a1_posesion`, `a1_cadena` |
| `a1-2` | 1.2 | De dónde viene y a dónde va el balón | `c1_sim` (`simulador_v2`): tres vistas, una de ellas **paso a paso** | `a1_viva` (animación, λ₁ por bloque) |
| `a1-3` | 1.3 | Por qué comparamos contra la liga del mismo torneo | `a1_deriva` | — |
| `a2-0` | 2.0 | Su carrera, club por club | `c_carrera`: línea de tiempo por club + las tres preguntas por plantilla, nivel C (adenda 4 §2) | — |
| `a2-1` | 2.1 | Con el balón | frase de portada, mapa de zonas, ejemplo + **una sola línea de carrera** con todos sus clubes y una raya en cada cambio (`serie_por_torneo`) | `s21` |
| `a2-2` | 2.2 | ¿Llega a la **última franja del campo** sin perder el balón? | llegada y τ del club principal + barras con intervalo de **sus clubes** (`eras_todas`, ADR-61 adenda 1), las no principales marcadas descriptivas; sin jugada | `s22` (los cinco técnicos y la jugada, completos) |
| `a2-3` | 2.3 | Ocasiones y territorio | 2 frases, tarjetas | `s23` |
| `a2-4` | 2.4 | Sin el balón | 2 frases, npxG concedido | `s24` (con presión) |
| `a2-6` | 2.5 | ¿Cambia según el partido? | 1 frase, tabla | `s26` |
| `a2-7` | 2.6 | Balón parado | 1 frase, remate y gol | `s27` |
| `a2-8` | 2.7 | Jugadores y minutos | 2 frases, anillos | `s28` |
| `a3-1` | 3.1 | El club antes y después de él (+ **los mismos jugadores con otro técnico**, ADR-63) | `c31`: relevos contados, parte del uso (φ_U solo si estimable y estable), control, placebo, figura | `s31` |
| `a3-2` | 3.2 | ¿Se lleva su estilo a otro club? | `c32` = extracto de `s33` + `s34` | `s33`, `s34` |
| `c-1` | C.1 | ¿Nos creen? | `c_nos_creen` | `c_credibilidad` |
| `c-2` | C.2 | Límites | cinco líneas | `c_limites` |

Anexo suelto: estimación, semáforo, por qué no simulamos, torneo tras torneo (`s25`), plantel
contra uso (`s32`, id `x-plantel`) y el catálogo de errores (pendiente).

### Las historias

`HISTORIAS` en el generador: Jardine, Larcamón, Ambriz, Herrera y Ortiz, en
ese orden. Las eras de cada una son las unidades con `coach` **igual** al del
técnico (nunca por subcadena). La **era principal** es la de más partidos. El
selector cambia la historia y repinta la página entera, anexo incluido.

### Capas, niveles y lenguaje

- Cuerpo: **frase y figura** en cada sección, o un hueco que lo declare. "En un partido"
  donde existe. Los plegables van al anexo, abiertos.
- Las frases del cuerpo **no imprimen** intervalos ni q (se quitan los `.tec` y el tooltip
  de fuente); la lectura de q en palabras se queda. Los intervalos se ven en las figuras y
  en el anexo.
- Nivel en palabras: probado (A), medido (B), descriptivo (C); "sin diferencia" en un nulo.
- **Sin interruptor.** `body.tecnica` va siempre puesto para que el anexo muestre todo.
- **Jerga** (`tests/test_jerga.py` sobre el modelo y el humo sobre el DOM, con tooltips y
  aria-label): `ADR-\d`, `q =`, `p = 0.`, `IC [`, `N80`, `τ`, `λ`, `π`, `bootstrap`,
  `Benjamini`, `BH al`, `f = 0.`, `F\d\d`, `D\d\d-\d`, `h2_\d\d`, "era principal",
  "la base", "cuasi-estacionaria". Permitidos en el anexo.
- **Topes por historia** (humo): ≤ **2 900 + 200 × nº de clubes** palabras (adenda 9), ≤ 18 secciones y ≤ 30 figuras (adenda 8 §4); ninguna lista se apila en una columna de más de doce.

### Navegación (adenda 5 §3)

Una sola barra fija con tres cosas: el nombre del técnico, el menú **técnico** y el menú
**ir a**. No hay selector global de club.

**`.navin` NO lleva `overflow:hidden`** (adenda 6 §1). En h2_38 lo llevaba, para garantizar
que la barra no se desbordara, y recortaba los `.drop-menu`, que son absolutos y cuelgan por
debajo: los menús se abrían invisibles y la página parecía tener un solo técnico. La barra no
se desborda igualmente porque no envuelve (`flex-wrap:nowrap`) y porque el nombre del técnico
se encoge (`min-width:0` + `text-overflow:ellipsis`).

**El humo abre los menús.** Comprobar la hoja de estilo fue exactamente lo que dio falsa
seguridad: la regla verificada era la que causaba el fallo. Ahora el humo hace clic en cada
menú y comprueba que su primera opción existe, que el menú no está en `display:none` y que
**ningún ancestro lo recorta** (ningún `overflow`/`overflow-y` `hidden` o `clip` en la cadena
hasta `body`). El ancho real a 1920, 1440, 1280, 1024 y 900 se verifica aparte con un
navegador de verdad, porque jsdom no calcula disposición.

Todo control lleva `cursor:pointer` y realce al pasar el mouse y al enfocar con el teclado;
el humo lo comprueba sobre la hoja de estilo (ahí sí basta: no hay nada que la regla pueda
romper).

### La figura trae los clubes dentro (adenda 8 §1-§2)

Donde hay dato por club, **la figura compara** en vez de repetirse: 2.1 dibuja un
mapa 5 × 4 por club en fila (`mapasFila` → `.mapfila` → `.mf-uno[data-club]`), 2.3
pone una barra por club en cada tarjeta, 2.4 rotula su figura por club y 2.7
agrupa los medidores por club. 2.5 y 2.6 no lo hacen y lo declaran: cuatro paneles
por tres clubes son doce cajas, y el embudo de 2.6 es de la liga, no del club.

**Escala compartida.** `mapasFila` normaliza cada mapa a proporciones (suma 1) y
pasa a todos el mismo `vmax`, que queda en `data-escala`. Dos mapas comparados con
escalas distintas son una comparación falsa; el humo lo comprueba. **Cuando hay más de un mapa en la fila no se imprime el número de cada casilla**
(va en el tooltip): en mapas comparados el número por celda estorba —lo que se lee
es el patrón de color— y además contaba como palabra del tope. El mapa grande de
diferencia (`mapaDif`) sí conserva sus números, que es donde importan.

### Los clubes, lado a lado (adenda 7 §1; sustituye a las pestañas)

**No hay selector de club.** Cada sección con dato por club se pinta en dos zonas:
arriba, una fila con la MISMA frase de cada club (`.porclub` → `.pc-col[data-club]`),
en orden cronológico y con el club donde más dirigió marcado; debajo, a ancho
completo, el resto de esa sección para ese club, bajo el rótulo "lo que sigue es de
&lt;club&gt;". Repetir figuras y ejemplos por columna triplicaba la página (3 600
palabras y 27 figuras con tres clubes) y dejaba columnas vacías al lado de una
larga; por eso las columnas llevan solo la frase. El humo comprueba que no queda
ningún `[data-selclub]` y que hay una columna por club.

**Texto histórico (adenda 6 §2, ya sustituida).** Las pestañas eran **un botón por club**, en orden cronológico, y el del club donde más
dirigió lo dice («Puebla · donde más dirigió»). **No hay opción «todos sus clubes»**
(adenda 6 §2): no existe un agregado de varias eras y no puede existir, porque cada era se
compara contra la liga de sus mismos torneos (ADR-53). Un test comprueba que la cadena
«todos sus clubes» no aparece en ninguna parte de la página. En el simulador, donde sí se
suman conteos crudos sin comparar contra nada, la opción se llama «sus clubes juntos».

`por_club[club]` trae las secciones 2.1 a 2.7 **menos 2.0 y 2.2** de cada club que no es el
principal, construidas con las mismas funciones sobre `H` con `principal = club`,
`sub = True` y otro `id` (así no corren las guardas de las lecturas preinscritas de
Jardine). Sin anexo, sin enlace y sin anclas de portada. El JS pinta, dentro de cada
sección que tenga versiones por club, unas pestañas («todos sus clubes» + un botón por
club) y al cambiar mantiene la sección en el mismo sitio de la pantalla. 2.2 no lleva
pestañas y dice en una nota que se midió solo en el club donde más dirigió.

### Simulador (1.2), antes de la adenda 4

Lee `simulador_v1.json`: la matriz del bloque de juego abierto (20 × 20) de la liga del
torneo de 1.6 y de la era principal de cada historia. Tocar una casilla empieza ahí; "una
acción más" aplica μ → μQ/‖μQ‖; "hasta el final" da 200 pasos; se ve cuántas de cada 100
siguen vivas (‖μ₀Qⁿ‖). 46 aborta si la distribución límite de su matriz no coincide a 1e-9
con la publicada por 45.

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
| "los estados vivos se comunican" | frase falsa en 1.2 hasta h2_34 | la fase es la del origen de la posesión y no cambia: Q es diagonal por bloques (ADR-61 §0) |
| "explicación" en una nota | el filtro de frases prohibidas aborta | `\bexplic` es causal; decir "frase" o "texto" |
| nombre por subcadena | un jugador "Herrera" se cuela en la historia | buscar por `in` en vez de `==` sobre `coach` |
| `"Club América"` vs `"América"` | el mapa de zonas dice 0 filas | `team` es el valor **de la columna** |
| par con otro orden | el signo sale al revés | `par()` devuelve si viene invertido; las frases citan el orden del JSON ("A frente a B") |
| clave `adn` en el JSON embebido | el filtro de frases prohibidas aborta | `\badn\b` es "ADN"; no nombrar así ninguna clave |
| número en prosa | `test_cifras_trazables` en rojo | escribir "primer acto", no "acto 1"; citar con `M.cita()` |
| chequeo del humo copiado del sintético | FALLA sobre el informe real aunque la página esté bien | el humo exigía los casos límite del sintético (Ambriz sin cuasi, Ortiz sin jugada); lo esperado se lee de `D` (h2_35b) |
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
- Que llegar más a la franja del área es jugar "mejor" o "más eficiente" (ADR-61 §8).
- Que un T que rechaza lo "causó" el técnico: el control Cocca I → II también
  rechaza (adenda 1 de ADR-60). El placebo es contexto, nunca criterio.

## 9. El generador sintético tiene que reproducir el esquema REAL

`humo_reporte.py` genera los datos con los que se renderiza la página. **Si su
forma no coincide con la de los JSON reales, la prueba valida menos de lo que
aparenta.** Al añadir un campo que el generador lee, añadirlo también al
sintético, **con los casos límite**: el vacío, el bloqueado, el que tiene cero,
el que sobrevive en una historia sin lectura preinscrita, el homónimo.


## 10. Simulador desde h2_38 (adenda 4 §5 y adenda 5 §5)

Lee `simulador_v2.json` (conteos). Tres vistas, cada una con una línea que dice qué son sus
porcentajes:

1. **De dónde viene y a dónde va.** Tocar una zona: tres flechas de salida (las filas de los
   conteos), tres de llegada (las columnas) y cómo termina la acción. Los porcentajes son
   «de cada 100 balones que pasan por esa zona».
2. **Paso a paso.** Se toca una zona para poner ahí el balón; cada clic en «una acción más»
   sortea **un** paso con `Math.random` (`FIG._simPaso`), dibuja esa flecha con su
   probabilidad y deja el rastro de las anteriores. Al llegar a un final lo dice y ofrece
   «otra jugada». Lleva la leyenda "jugada inventada por el modelo, no real".
3. **A la larga.** Itera el reparto; los porcentajes son «de las posesiones que ya duraron
   mucho».

Fuente: la liga, cada club del técnico o todos sus clubes (conteos sumados). Una fila sin
conteos toma la de la liga.
