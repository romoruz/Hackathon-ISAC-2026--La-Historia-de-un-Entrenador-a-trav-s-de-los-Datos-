# ADR-59 · Adenda 2 — el informe en tres actos, con cinco historias

> **Escrita el 2026-09-18**, después del barrido exploratorio de eras
> (`scripts/41_barrido_eras.py`) y **antes** de tocar `12_reporte_html.py`
> para la fase F1 (paquete h2_31). Se commitea sola, antes del código.
>
> **Declaración de contaminación.** Todos los resultados de los siete JSON ya
> se vieron (como en ADR-59 y su adenda 1). Además, **el elenco de cinco
> historias se eligió después de ver las distancias del barrido** (53 eras,
> 60 relevos, 13 traslados). Esta adenda no añade contrastes, no cambia
> familias ni q, y no publica ninguna cifra del barrido. Lo que fija es cómo
> se organiza y se redacta lo que ya está medido, con reglas mecánicas que
> valen igual para las cinco historias.

## 1. Estructura

La crónica fija de diez secciones (ADR-59 §4) se reemplaza por tres actos.
`PLAN_FASE2` decía "sin selectores"; esta adenda lo revierte: hay un selector
de cinco historias y un interruptor sencilla/técnica. Cambian el orden y el
lugar de lo que ADR-59 preinscribió, no su contenido.

| ADR-59 | pasa a |
|---|---|
| §1 Cómo leer | Acto 1 (común): la posesión, la cadena y sus clases, cómo se estiman las probabilidades, en qué confiar, por qué contra la liga del mismo torneo, dónde vive una posesión viva, por qué no simulamos |
| §2 con el balón | 2.1 (duración y zonas) y 2.3 (ocasiones y territorio); los pares del mismo club pasan a 3.1 |
| §3 sin el balón | 2.4 |
| §4 en el tiempo | 2.5 |
| §5 contexto | 2.6 |
| §6 plantel | 2.8 |
| §7 balón parado | 2.7 |
| §8 Jardine y el América | 3.4 |
| §9 credibilidad | cierre común |
| §10 límites | cierre común |

Secciones nuevas que en F1 se declaran **pendientes**, sin cifras: 2.2
progresión (ADR-61), 3.2 plantel contra uso y 3.3 mapa de estilos (ADR-60).
En el acto 1, "dónde vive una posesión viva" y la curva de supervivencia
también esperan a ADR-61. El anexo de errores sigue pendiente (adenda 1, §7).

## 2. El elenco y la era principal

Cinco historias: **Jardine, Larcamón, Ambriz, Herrera y Ortiz**. Criterios
declarados: al menos dos clubes en la muestra, muestra grande, relevos con
jugadores compartidos y cobertura del espectro. Se eligieron **viendo** el
barrido. Por eso ninguna distancia del barrido (traslados, relevos, PCA,
medianas) entra al informe en F1. Entrarán con ADR-60, que las preinscribe.

Las eras de una historia son las unidades de `metricas_v1` cuyo `coach` es
**exactamente** el del técnico. La búsqueda es por igualdad, nunca por
subcadena: "Herrera", "Ortiz", "Solari" y "Ambriz" también son nombres de
jugadores en los archivos de la etapa vieja.

La **era principal** de cada historia es la de más partidos (y, si empatan,
la más antigua). Los actos 2.1 y 2.3 a 2.8 la describen. El acto 3 compara
todas las eras. Con esta regla quedan: Jardine · América (100), Larcamón ·
Puebla (51), Ambriz · Toluca (64), Herrera · Tigres UANL (51) y Ortiz ·
América (43).

Jardine sigue siendo la historia que abre la página. En su historia, 3.4
conserva las cuatro eras de ADR-59 §8 (Jardine y Ortiz, en el América y fuera
de él). En las otras cuatro, 3.4 muestra las eras de su técnico.

## 3. Redacción mecánica

Las lecturas preinscritas de ADR-59 valen **solo para Jardine** y conservan
sus guardas (adenda 1, §9): si una deja de sostenerse, el generador termina
con `LECTURA PREINSCRITA ROTA`. Para las otras cuatro historias no hay
lectura preinscrita. Su texto sale de plantillas fijas, que valen para las
cinco:

- **A · rechaza tras BH:** "difiere", con valor, IC, q y su lectura en
  palabras.
- **A · no rechaza (nulo):** "no detectamos una diferencia mayor a X", con X
  el extremo del IC más lejano al cero. Si el IC excluye el cero antes de
  corregir, se dice ("el intervalo no toca el cero, pero no sobrevive a la
  corrección").
- **B · IC que no toca el cero:** "por encima / por debajo de la liga", con
  valor e IC.
- **B · IC que cruza el cero:** "no se separa de la liga; si hay diferencia,
  es menor a X".
- **C:** conteos ("en k de n torneos") y rangos de percentil, sin lenguaje de
  hallazgo.

Las familias y los q son los del JSON; nada se vuelve a corregir. En contexto,
balón parado y jugadores se usa la familia **casos** (`q_casos`,
`rechaza_casos`), que es la que incluye a los doce técnicos de ADR-57.

**Ninguna frase se elige ni se omite por su resultado.** Cada sección tiene
las mismas plantillas para las cinco historias. Si un dato no existe, la
frase se sustituye por un hueco declarado con su motivo.

## 4. Qué pares aparecen

- **3.1 · el club antes y después:** todas las parejas de `did_h4_v1 › pares`
  en los clubes de la historia. En la figura van todas; en el texto, las que
  incluyen al técnico. Cada una se etiqueta "antes de él" o "después de él"
  según el primer torneo de cada era (`did_h4_v1 › unidades[].torneos` y
  `parametros.torneos_orden`). Si en un club no hay una era analizable
  posterior a la suya, se dice.
- **2.4 · presión:** las parejas de `did_presion_v1 › pares` en los clubes de
  la historia. En el texto, las que incluyen al técnico. Las que no lo
  incluyen solo aparecen si rechazan, como control ("lo que el método sí
  detecta en el mismo club", como ADR-59 §3).
- ADR-54 midió presión en seis clubes (`did_presion_v1 ›
  parametros.clubes`). Una historia sin eras en esos clubes (Ambriz, Herrera)
  declara el hueco con ese motivo. El npxG concedido sí se publica, porque
  viene de `metricas_v1`.

## 5. Las cuatro capas y el semáforo

Cada sección de los actos 2 y 3 lleva cuatro capas. Si falta una, se declara
el hueco; una sección nunca sale más corta sin decirlo.

1. **Frase con semáforo:** verde = A, ámbar = B, gris = C. Un nulo de nivel A
   va en verde con la marca "nulo". El color sigue al nivel de evidencia, no
   a la dirección del resultado.
2. **Figura.**
3. **"En un partido":** en F1 **no es una jugada real**. Repite, en unidades
   de un partido o de una posesión, cifras que ya están en la capa 1: E[T] de
   la era contra la de la liga, npxG por partido de la era contra el de la
   liga, córners por partido, minutos del jugador con más minutos. No lleva
   nivel propio. La jugada real necesita los eventos y llega con ADR-61.
4. **Cómo lo medimos:** el estimando, la comparación, la familia y el
   archivo con su campo. Las reglas se citan del propio JSON (`reglas`,
   `parametros`), sin reescribirlas.

El acto 1 es pedagógico y no sigue la plantilla de cuatro capas.

## 6. Portada

Cinco frases por historia, en ranuras fijas, cada una con su nivel y un
enlace a su sección:

1. posesión contra la liga (2.1);
2. field tilt (2.3);
3. npxG concedido (2.4);
4. rotación del once (2.8);
5. lo que cambia entre sus clubes (3.4). En Jardine es la frase preinscrita
   "fuera del América, el perfil de Jardine se invierte"; en las otras, la
   línea de posesión de 3.4.

Las ranuras se fijan aquí y no se cambian por lo que digan los datos.

## 7. Interruptor sencilla / técnica

El modo por defecto es **sencilla**. En sencilla se ocultan los intervalos, el
"q = …" y los plegables de la capa 4. La lectura de q en palabras, el nivel de
cada frase y el margen de cada nulo **nunca** se ocultan. En técnica se ve todo
y los plegables arrancan abiertos. Ninguna frase cambia de nivel entre modos.

## 8. Frases prohibidas nuevas

Se añaden a `frases_prohibidas.py`:

- "pesa más que";
- "demuestra que";
- "su idea".

Las notas internas del roadmap ("el club pesa más que el técnico", "su idea sí
viaja") **no** pasan a la página.

## 9. Lo que no cambia

- Ninguna cifra se teclea: todas salen de los siete JSON y llevan su fuente.
- q sí, p no (adenda 1, §8).
- Nada causal.
- Las macros de la guía LaTeX salen solo de la historia de Jardine y del
  acto 1, para que no choquen entre historias.
- `reports/barrido/` no se lee en F1.
