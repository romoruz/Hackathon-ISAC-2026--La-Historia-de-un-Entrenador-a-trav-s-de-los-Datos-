# Tercer ensayo — guion para un lector ajeno

**A quién.** Alguien **fuera del hackathon**, que no haya visto la página nunca y
que no sea programador ni analista. Si además le gusta el fútbol pero no lee
estadística, es el lector ideal: es el jurado que no viene a validar las
matemáticas, sino a entender qué se le está contando.

Los ensayos anteriores los hizo gente del equipo. Sabían qué buscar, y por eso
encontraron bugs pero no dijeron si la historia se entiende.

**Qué cambió desde el guion anterior (h2_47):** la página trae la sección de la
red de pases en el cierre, que cuenta un resultado **sin resolver** y un error
nuestro. Es la parte más delicada de todo el informe: puede leerse como
honestidad o como algo que salió mal y se esconde. Las preguntas 8 y 9 son para
eso.

## Reglas para quien conduce el ensayo

1. **No explicar nada.** Ni al principio ni cuando se trabe. Preguntar "¿se
   entiende?" garantiza un sí.
2. **Dar la página y callarse:** "ábrela y ve leyendo en voz alta lo que se te
   ocurra".
3. **Apuntar dónde se queda callado**, dónde frunce el ceño, dónde hace scroll
   rápido. Vale más que lo que diga después.
4. **Cronometrar cuánto tarda en decir algo sobre el técnico.** Más de un minuto
   sin opinar = la portada no funciona.
5. Dejarlo perderse. Perderse es información.
6. **Apuntar si llega solo a la red de pases** (está al final). Si no llega, no
   se la señales hasta después de la pregunta 7.

## Las preguntas, al final y en este orden

1. Sin mirar la pantalla, ¿de qué iba esto?
2. ¿Qué hizo este técnico distinto al resto?
3. Cuando dice que un equipo "llega más a la última franja", ¿comparado con qué?
   (Correcto: "con la liga de esos mismos torneos". Si dice "con los otros
   técnicos" o no sabe, la comparación contra la liga no se está comunicando.)
4. ¿Qué significa que una frase diga "probado" y otra "descriptivo"?
5. ¿Te fiarías de estos números? ¿Por qué?
6. ¿Hubo algo que te pareciera exagerado o vendido?
7. ¿Qué te sobró y qué te faltó?
8. *(Si no llegó sola, ahora sí: "lee la parte de quién le pasa el balón a
   quién".)* Con tus palabras: ¿qué se sabe y qué no se sabe de esa parte?
   (Correcto: no se sabe si la red cambia por el técnico; sí se sabe que el
   cambio viene más de que los mismos jugadores se pasan distinto, pero no por
   qué. Si dice "la red no cambia con el técnico" o "sí cambia", la sección falla.)
9. Después de leer esa parte, ¿te fías más, menos o igual del resto de la
   página? ¿Por qué?

## Preguntas que NO hacer

"¿Te gustó?"; "¿se entiende el simulador?" (le dice que hay uno y que debería
entenderlo: si no lo encontró solo, ese es el dato); "¿no te parece honesto que
contáramos el error?" (contiene la respuesta); cualquiera que contenga la
respuesta.

## Cómo leer el resultado

- **Bien la 1, la 2 y la 3** → la página cumple.
- **Falla la 3** → arreglar la comunicación de "contra la liga del mismo torneo"
  antes de añadir nada. Es el eje del proyecto.
- **Falla la 6** (le pareció vendido) → va antes que cualquier otra cosa. Todo el
  argumento del proyecto es no vender.
- **Falla la 8** (entiende que la red sí o no cambia con el técnico) → la sección
  C.2 se reescribe antes de F5. Es el error que la adenda 1c prohíbe.
- **La 9 dice "menos"** → no se toca el contenido, pero sí se anota por qué: si es
  por el error en sí o por cómo se cuenta.
- Los bugs que encuentre van a la lista, pero **no son el objetivo**.

El registro va en `docs/ensayos/`, con el formato de los anteriores: qué dijo
literal, qué se hizo con cada cosa, y qué se decidió no hacer y por qué.
