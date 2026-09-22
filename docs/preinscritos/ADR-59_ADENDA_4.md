# ADR-59 · Adenda 4 — la historia primero, club por club

> **Escrita el 2026-09-22**, después del ensayo con un lector ajeno a la página
> (h2_36 instalado, commit pendiente) y **antes** del código de h2_37. Se
> commitea sola, antes del código.
>
> **Declaración de contaminación.** Todos los resultados de ADR-53 a ADR-61 ya
> se vieron. Igual que la adenda 3, esta adenda **solo cambia la presentación**.
> Las "tres preguntas" de §2 **no son contrastes nuevos**: no tienen familia,
> ni q, ni predicción, y no entran al marcador. Son descripciones de nivel C
> que resumen, con plantillas fijas, lo que ya se midió. Los datos nuevos de §5
> y §6 (flujos entre zonas, matrices de todas las eras y nombres de jugadores)
> son descriptivos y salen de los mismos parquets, sin estimar nada nuevo.
>
> **Motivo** (ensayo del 2026-09-22, registrado en `docs/ensayos/2026-09-22.md`):
>
> - la página da números pero no cuenta la historia del técnico al principio;
> - no se puede ver al técnico en cada uno de sus clubes;
> - el simulador no se entiende;
> - la tabla de contexto, la figura de relevos y el mapa de estilos no se leen;
> - el marcador sale como una columna de puntos sin texto, y deja un gran
>   espacio en blanco al final;
> - el tono es demasiado formal.

## 1. Qué cambia y qué no

| cambia | no cambia |
|---|---|
| sección nueva al inicio de cada historia: "Su carrera, club por club" (§2) | ninguna cifra, familia, q, veredicto ni predicción |
| sub-selector de club dentro de cada historia (§3) | el marcador (sigue en 28 de 36 con sus no evaluables) |
| simulador de flujos y de jugadas (§5) en lugar del de reparto a la larga | las lecturas preinscritas de Jardine y sus guardas |
| figuras de contexto, relevos, estilos y marcador (§4) | frases prohibidas, nada causal, ninguna cifra tecleada |
| tono de tú, con frases cortas (§7) | el anexo completo y sus fuentes (adenda 3 §4) |
| nombres de jugadores en 2.7 (§6) | el grafo de jugadores (va en F4, ADR-62) y Voronoi (F5) |

## 2. "Su carrera, club por club" (nivel C, sin contrastes nuevos)

Es la primera sección de cada historia. Arriba lleva una **línea de tiempo**:
cada club del técnico en orden cronológico, con sus partidos y, contra la liga
del mismo torneo, sus métricas ya publicadas:

- duración de la posesión (`did_h4_v1 › unidades`, B);
- territorio y npxG a favor y en contra (`metricas_v1 › unidades.global`, B);
- continuidad del once (`jugadores_v1`, C).

Entre dos clubes seguidos del mismo técnico se ve la flecha del cambio de club.

Debajo, **las mismas tres preguntas para las cinco historias**, contestadas
por plantilla. Ninguna se escribe a mano ni se omite por su resultado.

1. **¿Cómo juega donde más dirigió?** Una frase que junta los signos ya
   publicados del club principal. Por ejemplo: "sus posesiones duraron más que
   las de la liga, llegó más al área y dominó más el territorio". Cada parte
   dice su nivel (probado o medido). Una parte sin diferencia se dice como
   "igual que la liga".
2. **¿Juega igual en sus otros clubes?** Dos cosas:
   - en cuántos de sus clubes cada métrica cayó del mismo lado de la liga ("la
     posesión quedó por encima de la liga en 2 de 3 clubes");
   - la distancia entre sus clubes contra la de dos épocas cualesquiera de la
     liga (`estilos_v1 › traslados` y `distancias_todas`): "sus clubes se
     parecen entre sí más que X de cada 100 pares de épocas de la liga".

   Sin la palabra "idea" ni "estilo propio".
3. **¿Él cambió al club o el club lo cambió a él?** La respuesta sale del
   control y del placebo (ADR-60 adenda 1). Plantilla fija:

   > "Con estos datos no se puede decir que él cambió al club. Cuando llegó,
   > el reparto del juego cambió en k de n relevos, pero el mismo técnico en
   > el mismo club (Cocca) también cambia, y partir la etapa de un técnico en
   > dos mitades da cambios parecidos. Lo que sí se ve: {respuesta 2}."

   Si relevos_v1 o placebo_v1 faltan, se declara el hueco.

Todas las frases de esta sección son nivel C. Sus cifras llevan fuente, como
todas.

## 3. Sub-selector de club

Debajo del selector de técnico: "todos sus clubes" (por defecto) y un botón
por club.

- **Todos sus clubes:** la página como en h2_36, con la carrera arriba.
- **Un club:** cada sección del segundo bloque muestra ese club **si el JSON
  trae esa unidad**. Si no la trae, lo dice en una línea: "para {club} no
  tenemos esta medición; solo se hizo en el club donde más dirigió". Es el
  caso de llegar al área (2.2), que ADR-61 preinscribió solo para la era
  principal y que **no se extiende** aquí.
- Las frases de portada y las lecturas preinscritas de Jardine siguen siendo
  las del club principal.
- El bloque "de dónde viene" (3.1 y 3.2) ya compara clubes y no cambia con el
  sub-selector.

## 4. Figuras que se sustituyen

- **Contexto (2.5):** la tabla A contra B se sustituye por cuatro paneles
  (localía, marcador, minuto 60, rival fuerte o débil). Cada panel lleva
  barras enfrentadas para las métricas que ya publica. La tabla pasa al anexo.
- **Relevos (3.1):** barras horizontales, una por relevo, con el largo del
  cambio. Barra llena si resiste la prueba, hueca si no. Una línea vertical
  marca "lo que se mueve sin cambiar de técnico" (placebo). El bosque pasa al
  anexo.
- **Mapa de estilos (3.2):**
  - cada esquina lleva un nombre llano que sale del signo de las cargas ("más
    balón y más rotación", etc.), nunca un nombre táctico inventado;
  - la leyenda va arriba;
  - una frase explica la figura: "cada punto es un técnico en un club; las
    flechas van del técnico que se fue al que llegó, y la línea continua une
    los clubes de un mismo técnico".
- **Marcador (cierre):** agrupado por tema (duración, presión, balón parado,
  contexto, jugadores, relevos, llegada), cada grupo con su nombre llano y su
  conteo ("presión: 2 de 4"). Cada punto dice en su tooltip qué se predijo. Se
  corrige el bug que los apilaba en una columna.
- **Jugada real (2.2):** se separan los puntos que caen en la misma zona para
  que no se encimen. Sigue siendo la jugada elegida por regla (ADR-61 §2).

## 5. Simulador (1.2): de dónde viene y a dónde va el balón

Sustituye al de la adenda 3 §6. Usa matrices del juego abierto de la liga y de
**cada era** de las cinco historias (46 v2).

- **Toca una zona:** tres flechas de a dónde va el balón desde ahí (las tres
  transiciones más probables), tres de dónde le llega (las tres zonas de
  origen más frecuentes) y la probabilidad de que la posesión termine en esa
  acción (remate, pérdida o fuera). Todo sale de los conteos, sin estimar
  nada.
- **"Simula una jugada":** sortea una posesión con la cadena de esa era, paso
  a paso, desde la zona tocada hasta que termina, y la dibuja numerada. Cada
  clic sortea **una distinta** ("otra jugada"). Lleva la leyenda fija:
  "jugada inventada por el modelo, no real: el modelo acierta la probabilidad
  de cada paso, pero no el largo total de las posesiones (por eso no simulamos
  partidos)".
- **"A la larga"** queda como un botón: pinta el reparto al que tiende el
  balón, con la frase de la adenda 3.
- Se elige la liga, el técnico en cada uno de sus clubes o "todos sus clubes"
  (sumando los conteos de sus eras).
- La jugada simulada y la jugada real de 2.2 son cosas distintas y se
  presentan por separado.

**Guarda:** 46 v2 sigue comprobando, para las eras principales, que la
distribución a la larga coincide a 1e-9 con la publicada.

## 6. Nombres de jugadores (2.7)

Los nombres salen de la columna `player` de `transitions.parquet`: el nombre
más frecuente por `player_id` dentro de la era. 2.7 empieza por la frase de
fútbol (cuánto rota el once y cuántos jugadores juntan el 80% de los minutos)
y lista los cinco con más minutos, con su nombre, posición y minutos. Los
medidores van después.

## 7. Tono

De tú a tú: frases cortas, verbos en pasado, sin punto y coma, sin "cabe
señalar". Se conservan íntegros los condicionales que protegen la precisión
("si hay diferencia, es menor a X") y los niveles. Las plantillas de la
adenda 2 §3 y la adenda 3 §5 se reescriben con esta voz, **sin cambiar qué
dicen**: la misma dirección, el mismo nivel y el mismo margen. Los tests que ya
verifican las plantillas (nivel, margen de los nulos, cifras con fuente) tienen
que seguir pasando sin tocarlos.

## 8. Topes

- Por historia, en el cuerpo: ≤ 2 500 palabras, ≤ 15 secciones (una más por la
  carrera) y ≤ 17 figuras.
- La jerga de la adenda 3 §5 sigue prohibida en el cuerpo.
- Ningún grupo de puntos, chips o lista del cuerpo puede apilarse en una
  columna de más de 12 elementos. El humo lo comprueba leyendo el estilo
  calculado; esa regla habría atrapado el marcador en columna.
