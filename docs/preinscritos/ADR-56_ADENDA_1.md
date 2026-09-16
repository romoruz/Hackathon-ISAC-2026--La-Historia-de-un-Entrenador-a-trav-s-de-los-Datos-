# ADR-56 · Adenda 1 — B = 16,000 para que el piso del p no bloquee

> **PREINSCRITA, 2026-09-16.** Escrita después del humo de `36` sobre la liga
> **sintética** y antes de correr `36` sobre cualquier dato real. Se commitea
> sola.

## Problema

Con B = 6000, el piso del p bilateral es 2/(B+1) = 0.00033. Pero α/m vale
0.05/336 = 0.00015 en la familia de ADR-52, y 0.05/384 = 0.00013 en la de
casos (ADR-57). Un contraste aislado **no podría rechazar nunca**, por fuerte
que fuera el efecto. ADR-56 solo pedía avisar de esto; eso es insuficiente.

## Decisión

**D56-B.** `36_contexto.py` usa **B = 16,000**: piso 0.000125, por debajo de
α/m en las dos familias. Nada más cambia.

No se ha visto ningún dato real de contexto al escribir esto.
