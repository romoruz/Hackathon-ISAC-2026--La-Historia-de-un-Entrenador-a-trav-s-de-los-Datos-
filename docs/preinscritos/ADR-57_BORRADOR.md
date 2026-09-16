# ADR-57 — Casos del informe: el América y los entrenadores con varios clubes

> **BORRADOR PREINSCRITO, 2026-09-16.** Escrito después de la sonda de
> contexto y antes de programar `36_contexto.py` y de ver cualquier dato de
> contexto. Se commitea solo.

## Contexto

El reto lo plantea el Club América, pero pide un método que sirva para
"cualquier entrenador". El informe se centra en **André Jardine** y en las
demás eras del América (Ortiz, Solari), y muestra **7–10 técnicos más** para
probar que el marco es general.

Elegir esos técnicos **después** de ver resultados sería selección. El
criterio tiene que ser estructural.

## Decisión

**D57-1. Casos** = todas las eras analizables del **América** más todas las
eras de los entrenadores con **al menos dos eras analizables en clubes
distintos**. Se calcula desde `phase0_report.json`, con el candado H4-8
vigente, y no depende de ningún resultado.

Resultado esperado con los datos actuales: **12 entrenadores y 24 eras**.

| entrenador | eras |
|---|---|
| André Jardine | América, Atlético San Luis |
| Fernando Ortiz | América, Monterrey |
| Santiago Solari | América |
| Nicolás Larcamón | Cruz Azul, León, Puebla |
| Miguel Herrera | Tigres UANL, Tijuana |
| Domènec Torrent | Atlético San Luis, Monterrey |
| Víctor Manuel Vucetich | Mazatlán, Monterrey |
| Ignacio Ambriz | Santos Laguna, Toluca |
| Eduardo Fentanes | Necaxa, Santos Laguna |
| Veljko Paunovic | Guadalajara, Tigres UANL |
| Benjamín Mora | Atlas, Querétaro |
| Beñat San José | Atlas, Mazatlán |

Si el cálculo difiere de esta tabla, el script lo avisa y **manda el
cálculo**, no la tabla.

**D57-2. Familia "casos".** En los análisis que comparan cada era con la liga
(balón parado, ADR-55; contexto, ADR-56) se añade una **segunda familia**: las
24 eras de casos, con BH al 5%, **separada** de la familia de ADR-52. Las dos
se reportan. Una era que esté en ambas lleva los dos q.

**D57-3. H5 ("¿la firma viaja?") es descriptivo** para E[T] (ADR-53) y para el
balón parado (ADR-55), porque sus puntos por era **ya se vieron**. Se presenta
como tabla de las eras de cada entrenador, sin contraste.

**D57-4. Narrativa.** Jardine es el protagonista; Ortiz y Solari, sus
contrapuntos dentro del club; los nueve técnicos de varios clubes, la prueba de
generalidad. La liga (53 eras) es la referencia.

## Predicción, escrita antes de ver datos de contexto

Solo hay una, porque es lo único que no se ha visto.

1. **El ajuste al marcador viaja con el entrenador.** Entre los nueve
   entrenadores de varios clubes, al menos **6** tienen el **mismo signo** de
   θ(marcador, M1) en todas sus eras. Por azar, con dos eras, cabría esperar
   la mitad. Es exploratoria: se evalúa sobre los puntos, sin p.
