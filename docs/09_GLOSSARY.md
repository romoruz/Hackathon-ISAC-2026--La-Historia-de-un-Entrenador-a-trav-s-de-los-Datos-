# 09 — Glosario

> Términos del proyecto, en el cruce entre matemáticas y fútbol. Para quien
> domina uno de los dos lenguajes pero no el otro.

---

## Matemáticas

**Cadena de Markov absorbente.** Proceso estocástico en tiempo discreto donde
ciertos estados, una vez alcanzados, no se abandonan. Aquí: la posesión termina
en gol, remate sin gol, pérdida o balón fuera.

**Estado transitorio / absorbente.** Transitorio = se puede salir de él
(una zona del campo con el balón). Absorbente = final de la posesión.

**Matriz fundamental $N = (I-Q)^{-1}$.** $N_{ij}$ = número esperado de visitas
al estado $j$ antes de que la posesión termine, partiendo de $i$. Existe porque
la serie $\sum_k Q^k$ converge cuando $\rho(Q)<1$ (serie de Neumann).

**Radio espectral $\rho(Q)$.** Mayor valor absoluto de los eigenvalores de $Q$.
Si $\rho(Q)<1$, toda posesión termina casi seguramente.

**Probabilidad de absorción $B = NR$.** $B_{ia}$ = probabilidad de que la
posesión termine en el estado absorbente $a$, partiendo de $i$.

**Distribución de visitas $\nu$.** Medida de probabilidad sobre estados que
resume dónde pasa el tiempo el equipo. Es el objeto que se compara entre
entrenadores.

**EMV (estimador de máxima verosimilitud).** El valor del parámetro que hace
más probables los datos observados. Aquí: $\hat p_{ij} = n_{ij}/n_i$.

**Estimador de encogimiento (shrinkage).** Combinación convexa entre la
estimación propia y una referencia externa. Introduce sesgo para reducir
varianza. Tipo James–Stein.

**Prior Dirichlet.** Distribución conjugada de la multinomial. La media
posterior coincide exactamente con el estimador de encogimiento, lo que da dos
lecturas del mismo número.

**Validación cruzada por bloques.** Partir los datos en pliegues respetando la
estructura de dependencia. Aquí los bloques son posesiones, no eventos.

**Bootstrap.** Estimar la incertidumbre remuestreando con reemplazo. *Por
bloques* = la unidad de remuestreo es un grupo correlacionado.

**Bootstrap básico (percentil invertido).** $[2\hat\theta - q_{1-\alpha/2},\,
2\hat\theta - q_{\alpha/2}]$. Corrige sesgo de primer orden.

**LRT / $G^2$.** Estadístico de razón de verosimilitudes. Aquí,
$G^2_i = 2n_i D_{KL}(\hat p_{i\cdot}\Vert q_{i\cdot})$: divergencia KL escalada
por tamaño de muestra.

**Divergencia de Kullback–Leibler.** Cuánta información se pierde al usar una
distribución en lugar de otra. No es simétrica.

**Distancia de variación total.** $\frac12\sum_j|p_j - q_j|$. Máxima diferencia
de probabilidad que las dos distribuciones asignan a un mismo evento. En $[0,1]$.

**Distancia de Wasserstein $W_1$.** Costo mínimo de transportar una
distribución hasta convertirla en otra. Es un programa lineal (problema de
transporte). Con métrica base en metros, se interpreta como "cuántos metros hay
que mover la masa de probabilidad".

**FDR / Benjamini–Hochberg.** Controlar la proporción esperada de falsos
positivos *entre los rechazos*, en vez de la probabilidad de cometer alguno.

**Proceso de Poisson no homogéneo.** Proceso puntual donde la tasa varía en el
espacio. Aquí: intensidad de acciones defensivas por zona.

**Adelgazamiento (thinning).** Si cada punto de un proceso de Poisson se
conserva con probabilidad $\pi(x)$, el resultado es Poisson con intensidad
$\pi(x)\lambda(x)$. Permite corregir la censura del área visible de los datos
360.

**Semi-Markov.** Generalización donde el tiempo de permanencia en un estado no
es geométrico/exponencial. $Q_{ij}(t) = p_{ij}F_{ij}(t)$.

**Números pseudoaleatorios comunes (CRN).** Usar las mismas semillas al comparar
dos escenarios simulados; colapsa la varianza de la diferencia.

**Importance sampling.** Simular bajo una distribución que favorece el evento
raro y corregir con el cociente de verosimilitudes.

---

## Fútbol y datos

**Evento (event data).** Registro de una acción con balón: tipo, jugador,
coordenadas, resultado. ~3,000 por partido.

**StatsBomb 360.** Producto que añade la posición de los jugadores visibles en
el instante de cada evento. **No es tracking**: son instantáneas, no
trayectorias, y no traen velocidades.

**Freeze frame.** La instantánea de posiciones de un evento.

**Área visible (`visible_area`).** Polígono que indica qué parte del campo
capturaba la cámara. Fuera de él no hay información: por eso el modelo defensivo
necesita corrección por adelgazamiento.

**SPADL.** Formato unificado para describir acciones de fútbol
independientemente del proveedor.

**xG (Expected Goals).** Probabilidad de que un remate termine en gol, dadas sus
condiciones.

**xT (Expected Threat).** Probabilidad de que la posesión termine en gol dado el
estado actual. Introducido por Rudd (2011) con cadenas de Markov y popularizado
por Singh (2018). En este proyecto se construye desde cero, no se importa.

**OBV (On-Ball Value).** Métrica propietaria de StatsBomb análoga a VAEP. Está
en el dataset y sirve como validación externa gratuita.

**PPDA.** Pases permitidos por acción defensiva. Proxy crudo de intensidad de
presión.

**Contrapresión.** Presionar inmediatamente después de perder el balón.
`counterpress` está en el dataset.

**`play_pattern`.** Cómo empezó la posesión. **Etiqueta la posesión completa,
no el evento individual.** Es la trampa más costosa del formato.

**Carry.** Conducción del balón. StatsBomb la registra con mucha generosidad:
44% de las acciones con balón, la mayoría reajustes de 1–3 m.

---

## Términos propios del proyecto

**`poss_uid`.** Identificador único de posesión. Es la **unidad de remuestreo**
de todo el bootstrap.

**Foco (focus).** La unidad analizada: un equipo o una era de entrenador.

**Línea base (baseline).** Contra quién se compara. Tres opciones:
`other_coaches` (otras eras del mismo club, el diseño fuerte), `opponents`,
`rest`.

**Prior $q$.** La referencia hacia la que encoge el estimador. **No es la línea
base**: el prior estabiliza renglones ralos, la línea base define el contraste.

**Fuga de prior.** Cuando $q$ contiene a la unidad focal. Infla $\lambda^*$ y
atenúa las diferencias medidas por construcción.

**Era.** Periodo continuo bajo un mismo entrenador, delimitado por fechas.

**Huella táctica (fingerprint).** Mapa de $G^2$ por estado que muestra dónde el
foco se separa de la línea base.

**Absorción terminal.** Transición artificial hacia `LOSS` que se añade cuando
la última acción de una posesión deja el balón en un estado transitorio. Sin
ella, $N$ se infla sistemáticamente.

**Fase (`phase`).** Categoría del **origen** de la posesión: `open`,
`transition`, `restart`, `set_piece`. No describe si el balón está parado ahora.

**`frac_below_min`.** Fracción de renglones con menos de 30 observaciones.
Diagnóstico principal de si la malla es demasiado fina para los datos.

**`params_per_obs`.** Parámetros del modelo divididos entre observaciones.
Por encima de ~0.5 en la unidad más pequeña analizada, se está sobreajustando.

---

## Términos del tablero y del bloque de remate

> Añadidos el 2026-08-29.

**Lift de ruta.** $P(\text{la jugada visitó } z \mid \text{acabó en remate})$
dividido entre $P(\text{la jugada visitó } z)$. Un lift de 2.4 dice que las
jugadas peligrosas pasan 2.4 veces más por esa casilla que una cualquiera del
mismo equipo. **Es un cociente contra la propia marginal**, no un porcentaje: el
reparto crudo de «desde dónde se remata» sale igual para todos los técnicos —el
área— y no discrimina.

**Supresión por soporte.** Emitir `null` en vez de un valor cuando hay menos de
un mínimo de observaciones detrás. Una zona con 3 jugadas puede dar un lift de
15× que es ruido con aspecto de hallazgo. La casilla se pinta **vacía**, no
tenue: tenue se lee como «poco», y lo correcto es «no lo sabemos».

**`goal_open` (integral de visibilidad).** Fracción **angular** de la boca de
meta no tapada por los defensores, vista desde el punto de remate. Cada defensor
se modela como disco de radio $r$ y proyecta una sombra de semiancho
$\arcsin(r/\rho)$; se unen los intervalos en 1-D. No confundir con la proyección
sobre la línea de meta, que es una fracción **lineal** y no la misma cantidad.

**Método de los restos mayores.** Reparto de enteros que suman exacto: se
redondea hacia abajo y la diferencia se asigna a los de mayor resto fraccionario.
Se usa para que los porcentajes de las 20 casillas sumen 100 y no 101.

**Escala divergente recortada.** Mapa de color donde el valor neutro (aquí
$1.00\times$) se ve neutro, y se satura por encima de un tope. El recorte existe
porque el área da ~4× para cualquier técnico y se comía toda la rampa. **El
número impreso no se recorta**: solo el color, y el recorte se declara.

**Concentración hacia adelante.** Criterio **físico** para identificar los
estados absorbentes, que en el parquet son enteros sin etiqueta:
$\frac{\text{tasa en el tercio rival}}{\text{tasa propia} + \text{tasa rival}}$.
Gol y remate dan ≈1.00 —no existen en campo propio—; pérdida y balón fuera, ≈0.6.
Sustituyó a dos criterios que fallaban: por frecuencia global (intercambiaba
remate y balón fuera) y por gradiente en puntos porcentuales (llamaba «remate» a
la pérdida, porque también crece hacia adelante partiendo de una base alta).

**$\tau^2$ y confiabilidad.** Varianza **entre unidades** una vez descontado el
ruido de muestreo. La confiabilidad $\tau^2/(\tau^2+\sigma_j^2)$ es el hermano
del encogimiento: cuánto se puede fiar uno de la media de una unidad. **No es
«el estilo del entrenador»**: es la varianza entre eras, que contiene también
plantel y contexto (`10_RESULTADOS.md` §25.5).

**Suelo de detección.** El menor $\tau$ que un diseño distingue de cero con
frecuencia razonable. Se estima por simulación con las $n$ reales. Existe porque
el estimador está **truncado en cero**: un $\tau^2 = 0$ puede significar «no hay
variación» o «no puedo verla», y son cosas distintas.

**ICC (correlación intraclase).** $\tau^2/(\tau^2+\sigma^2)$. Aquí 0.9%: quién
dirige explica el 1% de lo que dura una posesión concreta. Suena a nada y no lo
es — sobre miles de posesiones son 1.54 acciones de diferencia entre extremos.
