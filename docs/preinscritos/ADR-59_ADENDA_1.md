# ADR-59 · Adenda 1 — ajustes de nivel y de regla antes de escribir el HTML

> **Escrita el 2026-09-17**, después de cruzar el borrador de ADR-59 contra los
> siete JSON de `reports/` y **antes** de publicar `12_reporte_html.py` v2.
> Se commitea sola, antes del código (paquete h2_29).
>
> **Declaración de contaminación.** Todos los resultados ya se vieron (como en
> ADR-59). Esta adenda no añade titulares ni cambia signos: corrige dos
> redondeos, baja de nivel lo que no tiene intervalo y fija dos reglas que el
> borrador dejaba abiertas. La regla 6 se fijó viendo los datos y así se declara.

## 1. Los redondeos siguen al JSON

| cifra | ADR-59 | JSON | se publica |
|---|---|---|---|
| Jardine–Ortiz, E[T], extremo superior | +7.1 | 0.07049 (`did_h4_v1 › pares › did.E_T.ic95[1]`) | **+7.0** |
| Jardine, contexto, minuto 60 · P(remate) | +2.1 pp | 0.020484 (`contexto_v1 › contrastes["momento\|M2"].theta`) | **+2.0 pp** |

La cota del nulo contra Ortiz queda en "menor a 7.0%".

## 2. ADR-53 en el marcador

`did_h4_v1.json` no trae el bloque `predicciones`. Las cuatro se recalculan
desde el JSON con los criterios de 06_DECISIONS (ADR-53):

1. la firma temporal baja: `did.posterior_mas_largo/did.de` < `crudo.posterior_mas_largo/crudo.de`;
2. Cocca I contra Cocca II deja de ser "negativo y rechazado" tras corregir;
3. Jardine contra Solari conserva el signo y |DiD| < |crudo|;
4. `control_negativo.n_equivalentes == 0`.

Con eso, el marcador es 20 de 26 (53: 4/4, 54: 2/4, 55: 5/7, 56: 5/6,
57: 0/1, 58: 4/4). Un test lo fija.

## 3. ADR-57 P1: sobre nueve técnicos

`contexto_v1 › predicciones` registra P1 con los once técnicos de
`viaja_marcador_M1`, incluidos Jardine y Ortiz: 5 de 11. 06_DECISIONS y ADR-59
cuentan los nueve técnicos con varios clubes fuera del América: **3 de 9**. El
informe publica 3 de 9 y muestra el 5 de 11 en una nota. Con cualquiera de los
dos la predicción (al menos 6 de 9) falla: el marcador no cambia.

## 4. Una frase B necesita intervalo

ADR-59 §2 define B como "diferencia contra la liga **con IC**". Estas cifras
están marcadas B en §4 del borrador y su JSON no trae intervalo. Pasan a **C**:

| sección | cifra | JSON |
|---|---|---|
| §4 | posesión sobre la liga por torneo | `did_h4_v1 › serie_por_torneo` (solo `rel_E_T`, `n_poss`) |
| §5 | lo que ajusta la liga | `contexto_v1 › liga` (valores puntuales) |
| §6 | la liga tras el primer cambio, perdiendo | `jugadores_v1 › liga.Tactical` ([delta, n]) |
| §7 | embudo del balón parado | `balon_parado_v2 › liga.P_S_secuencia`, `P_G_secuencia` |

**Alternativa considerada y descartada:** mantenerlas en B como "parámetro
poblacional de la liga". El propio proyecto trata a la liga como muestra:
su base se remuestrea por partido en todos los contrastes (D56-bootstrap,
D59P-incertidumbre). Llamarla población solo en estas cuatro cifras sería una
regla ad hoc. Si se quieren en B, el camino es que los scripts de origen
emitan su intervalo (paquete aparte).

## 5. Figura 7: coeficientes, no curva

`balon_parado_v2 › modelo` trae los β estandarizados y su IC, pero no el
intercepto ni las medias y desviaciones de estandarización. Una curva de
probabilidad contra la distancia en metros no se puede dibujar sin inventarlos.
La figura 7b es un bosque de β con IC. Tampoco se traduce "cabeza" a "metros
equivalentes": esa conversión necesita la desviación estándar de la distancia.

**Alternativa descartada:** efectos marginales. Necesitan lo mismo que falta.

## 6. "N80 alto" = por encima de la mediana de la liga del torneo

ADR-58 publica percentiles sin umbral. Jardine · América: 0.82, 0.76, 0.97,
0.44, 0.74, 0.94. Umbrales posibles y su conteo:

| regla | conteo |
|---|---|
| **percentil > 0.50 (mediana)** | **5 de 6** |
| percentil ≥ 0.70 | 5 de 6 |
| percentil ≥ 0.85 (simétrica al 15% de la continuidad) | 2 de 6 |
| N80 ≥ 14 jugadores (absoluto) | 6 de 6 |

Se adopta la mediana por ser la referencia neutra de un percentil, **sabiendo**
que reproduce el "5 de 6" del borrador. Se descarta el umbral absoluto: el
N80 depende del número de partidos del torneo y ADR-58 lo define contra la
liga del mismo torneo. La frase lleva la marca "adenda 1" en el informe.

## 7. Anexo de errores silenciosos

ADR-59 §4 · §9 pide "los 20 bugs silenciosos, en anexo". No hay catálogo en
los insumos de la fase 2 y 06_DECISIONS numera hasta el #21. El anexo queda
declarado como pendiente en el informe hasta tener la fuente; no se publica
un conteo sin verla.

## 8. q sí, p no

15_REPORTE_HTML §1 prohíbe mostrar p-valores; ADR-59 §2 pide q en nivel A.
Manda ADR-59: el informe muestra q (con su lectura en palabras) y nunca p.
15_REPORTE_HTML se actualiza en consecuencia.

## 9. Lecturas preinscritas con guarda

Las frases que dependen de un signo o de un veredicto (§2, §3, §5 a §8) llevan
una comprobación en el generador. Si una corrida nueva deja de sostenerlas, el
script termina con `LECTURA PREINSCRITA ROTA` y no escribe la página. La
decisión de redactar otra cosa es humana y va en otra adenda.
