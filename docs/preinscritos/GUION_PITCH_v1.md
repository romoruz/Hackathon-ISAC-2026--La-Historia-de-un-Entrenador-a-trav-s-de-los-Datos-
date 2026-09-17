# Guion del pitch · 5 minutos · v1

> 2026-09-17. Deriva de ADR-59 (`ADR-59_BORRADOR.md`): mismas cifras, mismos
> niveles y misma lista de frases prohibidas. Si una cifra cambia en el JSON,
> cambia aquí. Se lee en voz alta; lo que está entre corchetes es la diapositiva.

## 0:00–0:30 · La pregunta y el instrumento

[Diapositiva 1: una cancha dividida en 20 zonas; tres íconos: dónde, cuánto,
cómo termina. Nota al pie: "cadena de Markov absorbente sobre zona × fase ·
53 eras · 18 clubes · 1,524 partidos".]

> "A cada posesión le hacemos tres preguntas: dónde se juega, cuánto dura y con
> qué probabilidad termina en remate o gol. Las respondemos para 53 etapas de
> entrenador en toda la Liga MX, y comparamos cada una contra la liga del mismo
> torneo, porque los datos del proveedor cambian de un torneo a otro."

## 0:30–2:30 · El América de Jardine

[Diapositiva 2: mapa de zonas y cuatro cifras grandes.]

> "Bajo André Jardine, el América tiene posesiones un 25% más largas que la
> liga. Da casi cuatro pases progresivos más por partido, genera 0.3 goles
> esperados más, sin contar penales, y concede 0.3 menos. Y juega en campo
> rival: de las acciones en el último tercio, 61 de cada 100 son suyas, once
> más que un equipo promedio."

[Diapositiva 3: serie por torneo, posesión y field tilt.]

> "Eso se repite en los seis torneos. Lo único que se mueve es la generación de
> ocasiones, que en el último torneo cae al tercio bajo de la liga."

[Diapositiva 4: bosque de contexto y presión, todo cruzando el cero.]

> "Sin balón y según el contexto, el América de Jardine se comporta como la
> liga. No detectamos que presione distinto a su antecesor, y cuando va
> perdiendo, de local o contra un rival fuerte, no detectamos que ajuste
> distinto a los demás. Eso también es un resultado, y lo reportamos con su
> margen."

[Diapositiva 5: percentiles de continuidad del once, seis barras en rojo.]

> "Lo que sí lo distingue es el plantel: en los seis torneos, su once cambia más
> que en el 85% de la liga. El América juega competiciones que no están en estos
> datos; el calendario puede estar detrás, y no lo podemos separar."

## 2:30–3:30 · ¿Qué es de Jardine y qué del América?

[Diapositiva 6: la tabla de cuatro filas de ADR-59 §8, con flechas de color.]

> "Aquí está lo que nadie más va a mostrarles. Jardine dirigió antes a San Luis.
> Ahí, sus posesiones fueron 10% más cortas que la liga, jugó en su campo y usó
> uno de los onces más estables. El perfil se invierte. Y Ortiz, el técnico
> anterior del América, tuvo en el América el mismo dominio territorial que
> Jardine, y en Monterrey lo perdió casi todo."

> "Nuestra lectura: una parte de lo que parece el estilo de un entrenador
> pertenece al contexto del club. Es compatible con técnicos que se ajustan al
> club en vez de imponer un estilo fijo. Es descriptivo, son dos casos, y no
> separa plantel de presupuesto ni de calendario. En los nueve técnicos que
> dirigieron dos clubes, solo tres conservan su forma de ajustar al marcador."

## 3:30–4:15 · Por qué creerlo

[Diapositiva 7: bosque crudo contra corregido, puntos grises moviéndose a sus
posiciones corregidas.]

> "Sin corregir los cambios del proveedor, 24 contrastes de presión parecían
> diferencias entre técnicos. Al corregir quedan 6. En duración de posesión, 15
> comparaciones cambian de signo."

[Diapositiva 8: marcador 20 de 26, con los seis fallos en rojo.]

> "Escribimos 26 predicciones antes de calcular los resultados y acertamos 20. Les
> enseñamos las seis que fallaron, porque son la prueba de que las escribimos
> antes."

## 4:15–5:00 · Límites y cierre

[Diapositiva 9: tres límites en una línea cada uno.]

> "Esto no dice qué técnico es mejor ni por qué ganó el América. No mide el
> tiempo en segundos ni la posición de todos los jugadores, y el modelo falla
> al describir la duración exacta de las posesiones; lo medimos y sabemos por
> qué no cambia estas comparaciones."

[Diapositiva 10: la frase de cierre.]

> "Si no vieron un solo partido, ya saben cómo juega el América de Jardine:
> larga posesión, en campo rival, con un once que cambia cada semana. Y saben
> algo más: qué parte de eso podría venir del club."

## Reglas de ensayo

- Tres corridas cronometradas con alguien que no conozca el proyecto.
- Si a los 2:30 no puede repetir las tres ideas del América de Jardine, se
  recorta, no se acelera.
- Preguntas probables del jurado y la respuesta en una frase:
  - *¿Por qué Markov si lo rechazan?* "Falla en la forma de la duración, con el
    mismo patrón en todas las unidades probadas; al comparar dos eras ajustadas
    igual, el error se cancela en buena parte, y la cobertura de los intervalos
    apenas cambia (0.944 a 0.938, medido con los datos anteriores al API;
    replicarlo está pendiente)."
  - *¿Cómo saben que es el técnico y no los jugadores?* "No lo sabemos, y por
    eso la diapositiva 6 existe."
  - *¿Por qué contra la liga del mismo torneo?* "Porque el proveedor cambió su
    anotación: sin corregir, en 37 de 47 comparaciones significativas el
    técnico posterior tenía posesiones más largas; corregido, en 23 de 44."
