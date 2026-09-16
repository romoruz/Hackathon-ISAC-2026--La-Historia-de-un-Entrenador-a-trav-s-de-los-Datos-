# ADR-53 — El contraste entre eras se normaliza por la liga del mismo torneo

> **BORRADOR, 2026-09-15.** Escrito ANTES de correr
> `scripts/30_did_contemporaneo.py` sobre datos reales. Pasa a
> `06_DECISIONS.md` cuando Rodrigo lo confirme. Lo que diga la corrida no
> modifica este texto: se reporta contra él.

## Contexto

`25_pares_h4.py` construye un prior contemporáneo (H4-5), pero magnitud y
permutación corren a λ=0, así que el prior no entra en ningún número. La v5
mide la diferencia entre eras **con la deriva del proveedor dentro**. Los
síntomas, medidos sobre `pares_h4_v5.json`:

- En 37 de los 45 pares significativos, el entrenador posterior tiene
  posesiones más largas.
- E[T] correlaciona 0.42 con la fecha media de la era (51 unidades).
- La liga pasa de 6.04 a 6.74 acciones por posesión filtrada entre A2021 y
  C2026 (`deriva_proveedor.json`).

**Por qué λ>0 no lo arregla.** Encoger las dos eras hacia el mismo `q`
multiplica la diferencia por un factor menor que 1. Atenúa por igual la parte
de estilo y la de deriva, y no cambia su proporción. Lo que falta es un
término que se reste, no uno que encoja.

**Por qué no es el DiD de Card y Krueger.** Cada era se observa solo en su
periodo y no hay pre-tratamiento. Lo que se hace es una normalización
contemporánea: el "control" es la liga en los mismos torneos. El supuesto de
identificación es que, sin cambio de entrenador, el club se habría movido como
la liga. B3/B4 (`24_linea_base_contemporanea.py`) lo contrastan, y el
contraste es débil por construcción.

## Decisión

Para cada unidad u = (club, entrenador):

$$D_u = \log E_T(\hat P_u, \hat\alpha_u) - \log E_T(\hat P_{base(u)}, \hat\alpha_u)$$

- $\hat P_u$: EMV a λ=0. $\hat\alpha_u$: distribución inicial empírica.
  Es el estimando de `08_ic_derivados.py` y se calcula con **la misma función**
  `derivadas` (una sola ruta, lección del bug #2).
- $\hat P_{base(u)}$: la liga sin el club (B1), en los torneos de u, mezclada
  con la composición de transiciones de u por torneo (B2). Cada torneo se
  normaliza por su total antes de mezclar.
- $\hat\alpha_u$ en los dos términos: se compara qué pasa después de empezar
  donde empieza u.

Para un par del mismo club: $\theta = D_a - D_b$, reportado como
$e^\theta - 1$.

**Incertidumbre.** Bootstrap no paramétrico por posesión, con reemplazo
(ADR-07/31), intervalo basic (ADR-10) en escala log. Se remuestrean las
posesiones del foco y las de la base, esta última estratificada por torneo. El
p bilateral se obtiene invirtiendo el IC basic. B = 4000.

**Sobre el submuestreo de H4-3.** Politis y Romano (1994) validan el
submuestreo con $b/n \to 0$ **y** reescalando por la tasa de convergencia
($\tau_b/\tau_n$). H4-3 no cumple ninguna de las dos: $b/n$ va de 0.25 a 0.97 en
los 60 pares y no reescala. Además, fija la era chica, que es la que más aporta a la
varianza. Evidencia sobre la v5: corr($b/n$, ancho) = −0.88, y en
Berizzo–Larcamón ($b/n$ = 0.93) el ancho es de 1.5 pp contra 8.05 pp del
bootstrap de `08`. El campo se renombra a `rel_E_T_rango_submuestreo`.

## Reglas preinscritas

| | |
|---|---|
| D53-1 | Familia **nueva**: θ(E_T) de todos los pares intra-club, BH al 5% |
| D53-2 | P_gol y P_remate son descriptivos, fuera de la familia |
| D53-3 | El crudo (mismo estimando, sin normalizar) sirve de comparación, no de hallazgo |
| D53-4 | Control negativo con márgenes **sin cambios** (3% E_T, 10% P_gol). Si ninguno cumple, se reporta el menor margen demostrable |
| D53-5 | Clave compuesta (club, entrenador) |
| D53-6 | Candado H4-8 vigente |
| D53-7 | Serie por torneo descriptiva, torneos con ≥ 400 posesiones del foco |
| D53-8 | Se declara si el piso del p impide rechazar un par aislado |

## Predicciones, escritas antes de correr

**Declaración de contaminación.** Antes de escribir esto vi dos ajustes
burdos: una pendiente temporal dentro de cada club y una normalización por la
tabla de liga de `deriva_proveedor.json`. Estas predicciones **no son
ciegas**. Se escriben para poder fallar, no para aparentar independencia.

1. **La firma temporal baja.** De 37/45 en la v5, la proporción de
   rechazados con el posterior más largo cae en el DiD. Si queda por encima
   del 75%, se reporta como deriva residual o tendencia táctica real de la
   liga, sin elegir entre las dos.
2. **Cocca I vs Cocca II deja de ser negativo y significativo.** Los dos
   ajustes burdos le daban +10.1% y +6.2%. Si el DiD sale negativo y
   significativo, la frase "un técnico difiere de sí mismo" se sostiene y se
   reporta como tal.
3. **Jardine vs Solari conserva el signo y se reduce** respecto al crudo.
4. **Ningún par cumple la equivalencia al 3%.** Con ~3,500 posesiones por era,
   el IC válido de `08` para Berizzo–Larcamón ya mide ±4% sin contar la
   varianza de la base. Si se cumple la predicción, la frase del reporte es
   "no detectamos una diferencia mayor a X%", con X el menor margen
   demostrable, y **se retira** la afirmación de equivalencia.

## Consecuencias

- La v5 queda como está y se reinterpreta como **diferencia bruta entre eras,
  deriva incluida**. No se borra ni se vuelve a correr.
- Los textos de H4-1 y H4-5 en `25_pares_h4.py` se corrigen (paquete h2_11):
  la significancia de la v5 también es a λ=0, y el prior no corrige la deriva.
- Cocca y el par nulo quedan **congelados** en la narrativa hasta tener el
  resultado.
- `12_API_STATSBOMB.md` §6 pedía diferencias en diferencias para H5. Este ADR
  lo hace para H4, y H5 lo hereda.

---

## Anexo — correcciones al registro detectadas en la misma sesión

1. **`17_SECCION_H2H4.md` §6.** La sincronía del escalón A2022→C2023 es de
   **18 de 18** clubes (`frac_mismo_sentido` = 1.0), no de 17 de 18 ni de 0.94.
   El resto de las cifras de §6 coinciden con `deriva_proveedor.json`.
2. **ADR-52.** D1 corrió con **seis** clubes: 27 parejas, 648 contrastes y
   32 sobrevivientes (`fdr_presion.json`). El texto habla de la terna y de
   12 parejas, y `generar_defensa_h7.sh` y `12_reporte_html.py` siguen con
   la terna por defecto.
3. **Control negativo de la v5.** Su criterio se evaluó con el rango de
   submuestreo. Con el IC válido de `08` (estimando α, no w), Berizzo–Larcamón
   da +0.13% con IC [−4.07%, +3.98%]: **no cumple ±3%**, con deriva o sin
   ella.
4. **Bug #17, caso activo en el reporte.** `defensa()` indexaba la calibración
   solo por nombre de era. Con Jardine en América y San Luis, el test del
   paquete reproduce que el América recibe el valor de San Luis. En toda la
   liga hay además tres parejas de entrenadores que coinciden en dos clubes
   (Ambriz–Paiva, Herrera–Siboldi, Larcamón–Guede).
5. **`goal_open`.** `recolecta()` carga todos los `goal_open_*.json` en cada
   club sin filtrar. No se tocó porque no se ha visto el formato de
   `25_goal_open_eras.py`. Queda pendiente.
6. **`ref_rivales`.** La referencia de rivales del reporte promedia toda la
   ventana, así que comparar una era contra ella arrastra el mismo confusor
   temporal.
