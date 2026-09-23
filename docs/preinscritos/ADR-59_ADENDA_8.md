# ADR-59 · Adenda 8 — que la comparación entre clubes se vea, no se lea

> **Escrita el 2026-09-22**, después del quinto ensayo sobre la página de h2_41
> (`docs/ensayos/2026-09-22e.md`) y **antes** del código de h2_42. Se commitea
> sola.
>
> **Declaración de contaminación.** Todos los resultados de ADR-53 a ADR-63 ya se
> vieron. Esta adenda **solo cambia la presentación**: cómo se dibujan cuatro
> figuras y dónde vive la sección que ADR-63 ya preinscribió. No cambia ninguna
> cifra, familia, q, veredicto, predicción ni el marcador, y no añade contrastes.
>
> **Motivo.** La adenda 7 §1 puso los clubes lado a lado, pero solo con su frase:
> las figuras siguieron siendo del club donde más dirigió, bajo el rótulo "solo
> Puebla". El lector ve tres cifras y un solo mapa, así que **no puede ver el
> cambio entre eras**, que es de lo que trata el proyecto. Replicar cada figura
> por club tampoco sirve: con tres clubes da 3 600 palabras y 27 figuras, con los
> mapas a un tercio de ancho.

## 1. Una figura que ya trae los clubes dentro

Sustituye al mecanismo de la adenda 7 §1 (no a su intención). Donde hay dato por
club, **la figura misma compara**, en lugar de repetirse:

- **2.1 (dónde vive el balón):** los mapas 5 × 4 de todos sus clubes **en una
  fila**, con la misma escala (§2), un solo título y un solo pie.
- **2.3 (ocasiones y territorio):** cada tarjeta (pases progresivos, npxG a
  favor, OBV, field tilt) lleva **una barra por club**, con su intervalo, y la
  línea del cero es la liga del mismo torneo.
- **2.4 (sin el balón):** la figura de npxG concedido ya es por club; se rotula
  igual que las demás y se marca cuál es el club donde más dirigió.
- **2.7 (jugadores y minutos):** los medidores por torneo se **agrupan y rotulan
  por club**, en el mismo orden cronológico.

Las frases por club de la adenda 7 §1 se quedan como están.

**Dónde NO se hace, y se dice:** 2.5 (contexto) son cuatro paneles y por tres
clubes serían doce cajas; 2.6 (balón parado) es un embudo **de la liga**, no del
club. Las dos siguen mostrando el club donde más dirigió y lo declaran en una
línea, en lugar de fingir una comparación.

## 2. Escala compartida (regla nueva, vale para toda la página)

Cuando dos o más mapas se ponen a comparar, **comparten la escala de color** y el
pie lo dice. Nunca se normaliza cada mapa por su cuenta: dos mapas con escalas
distintas puestos uno al lado del otro son una comparación falsa. Un test lo
comprueba sobre el modelo, y el humo sobre el DOM.

## 3. La sección de jugadores (ADR-63) entra en 3.1

Tal y como la preinscribió ADR-63 §5, con sus tres piezas obligatorias: la
leyenda **encima** del mapa de diferencia con los nombres de los dos técnicos (no
"positivo" y "negativo"), la nota fija de qué es un punto porcentual, y la frase
fija de no-causalidad. El ranking de quién se movió más lleva la línea del nulo.

Si `jugadores_zona_v1.json` falta, la sección declara el hueco con su comando,
como cualquier otra.

## 4. Topes

Suben a **≤ 3 200 palabras**, ≤ 18 secciones y **≤ 30 figuras** por historia. Los
mapas por club suman figuras pero casi no suman palabras: es exactamente el
intercambio que esta adenda busca, enseñar más y escribir menos. El tope de
palabras sube solo 200 y el humo sigue siendo quien lo hace fallar.

## 5. Lo que sigue prohibido

Comparar mapas con escalas distintas; agregar métricas de eras de torneos
distintos en una sola cifra; atribuir intención a un jugador o a un técnico;
cifras que no salgan de nuestros datos. Todo lo de ADR-59 §3 y las adendas 2 §8,
3 §5, 4, 5 §7, 6 §5 y 7 §6, y ADR-63 §3.

## 6. Lo que no cambia

Ninguna cifra, familia, q, veredicto, predicción ni el marcador. El anexo sigue
completo. Las lecturas preinscritas de Jardine y sus guardas siguen igual.
Ninguna cifra se teclea. El orden de la adenda 5, la barra de la adenda 6 y la
figura de 2.2 de la adenda 7 se quedan como están.

## 7. Fuera de esta adenda

Desglose del simulador por fase; color de club como acento; **F4 (ADR-62)**, la
red de pases; **F5**, varias jugadas, mapas de remate y Voronoi.
