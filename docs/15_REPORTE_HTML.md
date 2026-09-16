# 15 — El reporte HTML: contrato del entregable

> `scripts/12_reporte_html.py` produce **el entregable**. Ningún otro documento
> lo describía, y es la única pieza que el jurado va a ver.
>
> Leer esto ANTES de tocar el script. Última revisión 2026-08-26.

---

## 1. Qué es y por qué es así

Un **único** archivo `reporte.html` con todos los datos embebidos como JSON, las
gráficas dibujadas en SVG por JavaScript en el navegador, y **cero dependencias
externas**: ni CDN, ni fuentes remotas, ni librerías (ADR-38).

Se abre con doble clic. Funciona sin internet, sin servidor y sin Python.

**Por qué no Streamlit**: apila bloques en columnas y no hay CSS que lo cambie —
no se pueden hacer rejillas asimétricas ni tarjetas de tamaños distintos. Y el
reto pide un HTML. `app.py` se conserva para exploración durante el desarrollo.

**El principio que manda sobre el diseño** viene del reto:

> *"Su análisis debe permitir que alguien que **no vio los partidos** pueda
> entender con claridad cómo juega el equipo y cuáles son las ideas del
> entrenador."*

De ahí que **el reporte no muestre ni un p-valor**. La incertidumbre se dice en
palabras: `fuerza(q)` traduce el q-valor a *"muy sólido"*, *"sólido, con margen
estrecho"*, *"insuficiente tras corregir"*, *"no lo distinguimos del azar"*.

---

## 2. De dónde saca los datos

```
data/processed/transitions.parquet        ← mapas por jugador
reports/ic_*.json                         ← E[T], P(gol), P(remate) con IC
reports/plantel_*.json                    ← control de plantel, niveles 1 y 3
reports/huella_*.parquet                  ← huella táctica por estado
reports/campo_presion_*.json              ← π por zona (D1)
reports/presion_indice_*.json             ← curva de decaimiento
reports/nivel_calibracion_*.json          ← nivel en k≥k0
reports/calibracion_*.json                ← el instrumento: ¿la presión sirve?
reports/estandarizacion_defense_*.json    ← cantidades concedidas
reports/fdr_presion.json                  ← q-valores de la familia D1
```

**Si falta un JSON, la sección no miente: muestra el comando que lo genera.**
Es deliberado y debe conservarse. Un reporte que finge tener datos que no tiene
es peor que uno con un hueco declarado.

---

## 3. Las cinco secciones

| id | sección | qué contesta |
|---|---|---|
| `s0` | 01 · el ritmo | tres métricas con anillo e intervalos de confianza |
| `s1` | 02 · el territorio | huella táctica **+ el tablero interactivo** (§3 bis) |
| `s2` | 03 · el factor humano | control de plantel intra-jugador |
| `s3` | 04 · el matiz | nube de puntos: durar ≠ hacer daño, con la referencia de rivales |
| `s4` | 05 · sin balón | bloque defensivo D1 (presión) |

Todas se repintan al cambiar club, técnico o rival. `render()` las reconstruye
enteras: no hay estado parcial que sincronizar.

> **Hubo una sección 06 y ya no existe.** El tablero interactivo vivía al final
> en una sección propia; se mudó dentro de la 02, debajo de la huella táctica,
> porque ahí ya se habla de territorio y ver el flujo junto al mapa de dónde se
> separa del resto es mucho más fuerte que al final.

---

## 3 bis. El tablero interactivo de la sección 02

Es la pieza que traduce «matriz de transición» a algo que se toca. **Dos canchas
lado a lado** —el técnico y su comparación, misma escala— y **el simulador
debajo**.

### Tres modos sobre las mismas dos canchas

| modo | qué pinta cada casilla |
|---|---|
| **Dónde vive** | % de acciones del equipo en esa zona. Al tocar una casilla salen **flechas** a sus destinos con su probabilidad |
| **De dónde nace el remate** | el *lift*: cuántas veces más pasan por ahí las jugadas que acaban en remate frente a una cualquiera |
| **…y el gol** | igual, **bloqueado** si la era no llega a 100 goles |

### El lift de ruta

$$\text{lift}(z) = \frac{P(\text{la jugada visitó } z \mid \text{acabó en remate})}{P(\text{la jugada visitó } z)}$$

Se eligió el **cociente** y no el reparto crudo de «¿desde dónde se remata?»
porque ese segundo sale igual para todos los técnicos —el área— y no discrimina.
El cociente aísla por dónde **decide transitar** un equipo antes de que la
jugada se vuelva peligrosa.

**Tres controles que no son opcionales:**

1. **Supresión por soporte.** Bajo 10 visitas el lift se emite como nulo y la
   casilla se pinta **vacía**, no tenue: una casilla tenue se lee como «poco», y
   lo correcto es «no lo sabemos». En Jardine son 6 de 20 zonas en modo gol.
2. **Puerta del modo gol.** Con menos de 100 goles la pestaña se desactiva
   **diciendo el motivo y el n real**. Anselmi tiene 62 y queda bloqueado. Si
   uno de los dos lados está bloqueado, se desactiva el modo entero: media
   comparación es peor que ninguna.
3. **Escala recortada en 2.5×, logarítmica.** El centro del tercio rival da ~4×
   para *cualquier* técnico —hay que llegar al área para rematar— y esas dos
   casillas se comían toda la rampa: los dos mapas salían idénticos. Cortando en
   2.5× el contraste se desplaza a las zonas intermedias, que es donde se ve por
   qué banda construye cada uno. **El número impreso sigue siendo el lift real**;
   solo cambia el color, y el recorte va declarado en la leyenda.

   Logarítmica porque el lift es un cociente: 2× y 0.5× están igual de lejos de
   1 en sentido multiplicativo, y en escala lineal el lado bajo se comprimiría a
   la mitad.

**El caveat causal va impreso**, no plegado: *que una jugada pase por aquí no
provoca el remate; puede ser que las jugadas que ya iban bien lleguen a esta
zona*. Es la misma endogeneidad de ADR-48.

### «— el club, sin él —»

Es una opción del selector «frente a» de arriba, **al final de la lista**. Si
fuera la primera, el reporte abriría en ese modo y las secciones de pareja
saldrían con su aviso.

Se llama «sin él» y no «el club» a propósito: `12_API_STATSBOMB.md` §6 advierte
que la base del club **contiene al foco** —Jardine es el 53% de las
transiciones del América—, así que compararlo contra «el club» sería compararlo
consigo mismo a medias, con el efecto atenuado por construcción. Es
`other_coaches` de ADR-16.

Al elegirlo, las secciones 01, 03, 04 y 05 **explican por qué no aplican** en vez
de romperse: sus contrastes (`ic_*`, `plantel_*`, `campo_presion_*`) se calculan
por pareja de eras y no existen para «el resto del club».

### El simulador

El balón se mueve solo entre centros de zona, un paso cada 340 ms, dejando
flechas. Debajo, la tira de fichas cuenta la jugada en palabras:

> `banda izquierda, tercio propio · pase` › `centro, tercio medio · conducción` › **`REMATE`**

- La **fase** sale exacta del estado: el estado es (zona × fase) y la fase era la
  mitad del espacio de estados que estaba oculta.
- El **tipo de acción** se sortea de la mezcla real de esa zona, separando «la
  jugada sigue» de «la jugada termina». La acción que acaba una posesión en el
  área rival es un remate; la que la continúa en campo propio, casi siempre un
  pase. Mezclarlas diría que se remata desde todas partes.

El calor se acumula: con 1.000 jugadas la cancha se pinta sola con el mapa de
dónde vive el equipo, construido delante del visitante.

**No dibuja los 22 jugadores, y no debe hacerlo.** No existen en estos datos: el
freeze frame solo está en los remates y la cadena no sabe dónde estaba nadie.
Inventar posiciones sería lo mismo que ADR-38 prohíbe al vetar el difuminado —
sugerir una resolución que el modelo no tiene.

### Qué se quitó, y por qué

- **El histograma simulado vs observado.** Enseñaba la sobredispersión de forma
  visual, pero es auditoría, no fútbol, y ya vive en `03_METHODS.md` §7.1.
- **El bloque de la nula por permutación.** Mismo motivo. Sigue viva en cada IC
  del reporte y en ADR-30; lo que se quitó es el widget.

---

## 3 ter. Los porcentajes de las casillas suman 100 exacto

Se usa el **método de los restos mayores**: cada casilla se redondea a entero y
el punto que falta o sobra se reparte a las de mayor resto.

Redondear cada casilla por separado acumulaba **±2 puntos sobre 20 casillas**, y
un total de 101% mina la confianza en la matriz aunque la matriz esté bien. No
era un error de cálculo — el reparto real suma 1.000000 — pero se veía como uno.


| id | sección | qué contesta |
|---|---|---|
| `s0` | 01 · el ritmo | tres métricas con anillo e intervalos de confianza |
| `s1` | 02 · el territorio | huella táctica: dónde se separa del resto del club |
| `s2` | 03 · el factor humano | control de plantel intra-jugador |
| `s3` | 04 · el matiz | nube de puntos: durar ≠ hacer daño |
| `s4` | 05 · sin balón | bloque defensivo D1 (presión) |

Todas se repintan al cambiar club, técnico o rival. `render()` las reconstruye
enteras: no hay estado parcial que sincronizar.

---

## 4. Reglas de diseño que NO se pueden romper

### 4.1 Sin dependencias externas (ADR-38)

Ni `<script src>`, ni `@import`, ni `<link>` a nada remoto. Su virtud es
funcionar sin internet, en la máquina de un jurado, sin permisos.

### 4.2 Los mapas no se difuminan (ADR-38)

El modelo estima una probabilidad **constante por zona**. Un desenfoque gaussiano
o un hexbin sugeriría una resolución espacial continua que no existe, y ante un
jurado técnico eso es una tergiversación. Se usa un halo suave que **no borra
los bordes**.

### 4.3 Escala compartida entre mapas que se comparan

Dos canchas lado a lado deben normalizarse al **máximo común**, no cada una al
suyo. Con escalas independientes, dos repartos muy distintos se pintan con la
misma intensidad y la comparación visual miente.

Afecta a `mapaSVG` (mapas de jugador, parámetro `vmax`) y a `mapaNivel` (mapas
de presión, que ya lo hacía). **Es un requisito de honestidad, no de estética.**

### 4.4 Tamaño idéntico entre canchas que se comparan

Van en `.grid par` (`1fr 1fr`), nunca en `.grid duo` (`1.55fr 1fr`). `duo` está
pensada para *figura + barra lateral*. Usada para dos canchas del mismo tipo,
la de la derecha sale un 36% más chica y la mancha mayor parece más intensa sin
serlo.

Todas las canchas comparadas usan el mismo ancho: la constante `W_MAPA`.

### 4.5 Un solo par de colores en todo el reporte

```js
C_FOCO = var(--a1)   // color del club: SIEMPRE el técnico analizado
C_RIV  = var(--riv)  // plata neutra:   SIEMPRE la comparación
C_NEG  = var(--neg)  // coral:          "hace menos" en los mapas de diferencia
```

`--a1` lo fija `cambiaClub()` según `TEMA`. Ningún color se escribe a mano en
una figura. Antes cada figura elegía el suyo y el bloque defensivo pintaba al
América de azul, que es el color de su rival clásico.

### 4.6 Contraste mínimo

Ningún texto por debajo de 4.5:1 sobre el fondo, ni por debajo de 0.72rem en
estilo en línea, ni por debajo de 10px dentro de un SVG. Los tokens actuales:

| token | uso | contraste |
|---|---|---|
| `--tx1` / `--tx` | negritas, titulares | 18.6:1 |
| `--tx2` | notas y texto secundario | 10.4:1 |
| `--tx3` | etiquetas en versalitas | 6.8:1 |

`.nota` es la clase única para el texto pequeño explicativo. **No escribas
`style="font-size:.76rem;color:var(--tx3)"` en línea**: eso es lo que había, en
diez sitios, y dejó todas las explicaciones del reporte por debajo del mínimo
legible.

### 4.7 Vidrio en el chrome, contenido opaco

La barra de navegación y los tooltips son translúcidos con desenfoque; las
tarjetas de contenido son más opacas. Es la regla de la guía de Apple: el vidrio
es la capa de control, no el contenido. `--rim` da el borde especular.

`@media (prefers-reduced-transparency: reduce)` apaga el vidrio entero. El
desenfoque es decoración; la legibilidad no.

### 4.8 Todo se puede tocar, no solo señalar

Los tooltips responden a `mouseover` **y a `click`**. Sin lo segundo, las 20
casillas de cada cancha son mudas en un teléfono y todo el detalle por zona
desaparece.

---

## 5. Trampas conocidas de este archivo

| trampa | síntoma | causa |
|---|---|---|
| `"Club América"` vs `"América"` | la app dice "se necesitan dos etapas" con un dataset válido | el nombre de display no es el valor de la columna `team` |
| `MIN_POSS` ≠ `MIN_POSESIONES` | el reporte lista entrenadores sin artefactos | los dos umbrales deben valer **1500** |
| `var(--tx1)` sin declarar | los `<b>` salen en gris tenue, sin error | una `var()` inválida **hereda**; no falla |
| IDs duplicados en SVG | `url(#halo)` resuelve al primero del documento | son definiciones idénticas, funciona, pero no añadas una distinta con el mismo id |
| `color-mix` | la barra de la leyenda sale vacía en navegadores viejos | siempre `background:<color>` plano antes del gradiente |

---

## 6. Cómo verificar un cambio

**El reporte no tiene tests unitarios: tiene dos comprobaciones de extremo a
extremo.** Ninguna necesita los datos licenciados.

```bash
source .venv/bin/activate

python scripts/verifica_reporte.py
#   - el JavaScript compila (node --check)
#   - las llaves del CSS cuadran
#   - NINGUNA variable CSS se usa sin estar declarada

python scripts/humo_reporte.py
#   - genera datos sintéticos con la forma exacta de recolecta()
#   - RENDERIZA la página en un DOM real (jsdom)
#   - afirma, entre otras cosas: las cinco secciones se pintan; las canchas de
#     cada par comparten viewBox; no queda ningún color cableado; ningún texto
#     por debajo del umbral; los porcentajes de las casillas SUMAN 100 exacto;
#     tocar una casilla dibuja flechas en las DOS canchas; las zonas sin
#     soporte quedan vacías; el modo gol se bloquea con su n; el recorte de
#     escala satura 3.98× y 4.10× igual pero distingue 1.30× de 1.96×;
#     P(gol) <= P(remate) en el simulador; «el club, sin él» está en el
#     selector; con 0 de N la lista de futbolistas se pinta igual
#   - deja reporte_demo.html para mirarlo con los ojos
```

`node --check` solo dice que el JavaScript **compila**. Todos los bugs de este
proyecto compilaban. Lo que hay que comprobar es que la página **se pinta**, y
eso es lo que hace `humo_reporte.py`.

Requiere `jsdom` una sola vez:

```bash
npm install jsdom      # en la raíz del repo; node_modules/ está en .gitignore
```

Si `jsdom` no está disponible, `humo_reporte.py` lo dice y sale sin fallar: la
comprobación es valiosa, no obligatoria para poder trabajar.

---

## 7. Cómo añadir un club

1. `CLUBES` en `12_reporte_html.py`: nombre de display → `{dir, team}`. Ojo con
   §5: `team` es el valor **de la columna**, sin "Club".
2. `TEMA` en el JavaScript: `a1`, `a2` y los dos radiales del aura.
3. Lo mismo en `app.py`.
4. Regenerar: `phase0` → `generar_todo.sh` → `12_reporte_html.py`.

No hace falta tocar ninguna figura: todas leen el color del tema.

---

## 8. Lo que el reporte NO dice, y debe seguir sin decir

- Quién es **mejor** entrenador. Describe estilo, no rendimiento.
- Ningún p-valor. La incertidumbre va en palabras (§1).
- Ninguna afirmación causal. El bloque de conclusiones al pie lo declara
  explícitamente y **no debe suavizarse**.
- Ninguna cifra de presión sin decir si es **por posesión** o **por acción**
  (ADR-48): los dos estimandos difieren en signo.

---

## 9. El generador sintético tiene que reproducir el esquema REAL

`humo_reporte.py` genera los datos con los que se renderiza la página. **Si su
forma no coincide con la que emite `recolecta()`, la prueba valida menos de lo
que aparenta.** Pasó tres veces en una sola sesión:

| el generador producía | el parquet real trae | consecuencia |
|---|---|---|
| estados con nombre (`"z13\|open"`) | **enteros** (`0..83`) | el humo pasaba y el simulador salía en 0.00 |
| solo pares CON cambios de plantel | también pares con **0 de N** | la sección 03 se quedaba en blanco y nadie lo veía |
| `fin` indexado por posición | indexado por **valor de estado** | etiquetas cambiadas en eras con estados faltantes |

Es el error de proceso #2 de `02_STATE_OF_PLAY.md` §8 —*«`synth.py` prometía el
ESQUEMA REAL de StatsBomb y llevaba versiones sin `player_id`»*— repetido.

**Regla**: al añadir un campo a `recolecta()`, añadirlo también al generador, y
**con los casos límite**: el que está vacío, el que está bloqueado, el que tiene
cero. Un generador que solo produce el caso feliz prueba el caso feliz.
