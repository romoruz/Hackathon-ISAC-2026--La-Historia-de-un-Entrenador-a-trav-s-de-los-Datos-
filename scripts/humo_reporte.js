/* Humo del informe (ADR-59 adendas 2 y 3) en un DOM real.
   node scripts/humo_reporte.js pagina.html [completo|sin_relevos|sin_progresion|sin_contexto]
   Lo esperado sale de los datos embebidos (D), no de los casos del sintético. */
const fs = require("fs");
const { JSDOM } = require("jsdom");
const [ruta, modo = "completo"] = process.argv.slice(2);
const html = fs.readFileSync(ruta, "utf8");
let fallos = 0;
const ok = (c, m) => { console.log((c ? "  ok   " : "  FALLA ") + m); if (!c) fallos++; };

const errores = [];
const vc = new (require("jsdom").VirtualConsole)();
vc.on("jsdomError", e => errores.push(String(e.message || e)));
const dom = new JSDOM(html, { runScripts: "dangerously", pretendToBeVisual: true, virtualConsole: vc });
const { document } = dom.window;
const D = dom.window.eval("D");
const click = el => el.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
const $ = id => document.getElementById(id);
const PROG = modo !== "sin_progresion";
/* adenda 5 §3: el técnico se elige en un menú desplegable */
const verHist = id => click(document.querySelector(`#dropHist .drop-menu button[data-k="${id}"]`));
const opcHist = () => [...document.querySelectorAll("#dropHist .drop-menu button")].map(b => b.dataset.k);
const verClub = (sid, club) => click(document.querySelector(`[data-selclub="${sid}"] button[data-k="${club}"]`));
const selDe = sid => [...document.querySelectorAll(`[data-selclub="${sid}"] button`)].map(b => b.dataset.k);

/* topes y jerga de la adenda 3 (§5 y §7) */
/* adenda 9: el tope de palabras ESCALA con el número de clubes del técnico.
   Un tope fijo castigaba justo lo que la adenda 8 pide enseñar: los clubes lado a lado. */
const TOPE = { base: 2900, porClub: 200, secciones: 18, figuras: 30,
  /* adenda 10 §7: la red de pases lleva su tope propio y NO cuenta en el general */
  red: { palabras: 220, figuras: 1 } };
const topePalabras = h => TOPE.base + TOPE.porClub * h.eras.length;
const JERGA = [/ADR-\d/, /\bq =/, /\bp = 0\.\d/, /IC \[/, /N80/, /τ/, /λ/, /π/, /bootstrap/i, /Benjamini/, /BH al/,
  /\bf = 0\.\d/, /\bF\d\d\b/, /D\d\d-\d/, /h2_\d\d/, /\bera principal\b/i, /\bla base\b/i, /cuasi-estacionaria/i];
function jergaCuerpo() {
  const halladas = [];
  [$("informe"), document.querySelector("header")].forEach(z => {
    const c = z.cloneNode(true);
    c.querySelectorAll("#glosario, #anexo").forEach(x => x.remove());
    const textos = [c.textContent];
    c.querySelectorAll("[data-tip],[aria-label],[title]").forEach(e =>
      ["data-tip", "aria-label", "title"].forEach(a => e.getAttribute(a) && textos.push(e.getAttribute(a))));
    textos.forEach(t => JERGA.forEach(p => { const m = t.match(p); if (m) halladas.push(`${p.source} … ${t.slice(Math.max(0, m.index - 30), m.index + 30).replace(/\s+/g, " ")}`); }));
  });
  return halladas;
}

ok(errores.length === 0, `sin excepciones al cargar (${errores.slice(0, 2).join(" | ")})`);

/* 1. estructura */
ok(D.historias.map(h => h.id).join() === "jardine,larcamon,ambriz,herrera,ortiz", "cinco historias, en orden");
ok(opcHist().length === 5, "menú de técnico con cinco historias");
ok(document.querySelectorAll("#dropIr .drop-menu button").length === 4, "menú «ir a» con las cuatro partes");
ok(!$("segClub"), "no hay selector global de club (adenda 5 §4)");
ok(document.querySelectorAll("nav .navin > *").length === 3, "la barra lleva solo el nombre y los dos menús");
/* adenda 6 §1: NO se comprueba la hoja de estilo (eso fue lo que dio falsa seguridad en h2_38,
   porque la regla verificada era la que causaba el fallo). Se ABRE el menú y se mira si algo lo recorta. */
function recortadoPor(el) {
  for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
    const o = dom.window.getComputedStyle(p);
    if (["hidden", "clip"].includes(o.overflow) || ["hidden", "clip"].includes(o.overflowY)) return p.className || p.tagName;
  }
  return null;
}
function abre(id) {
  const d = $(id); click(d.querySelector("button"));
  const m = d.querySelector(".drop-menu"), op = m && m.querySelector("button");
  return { abierto: d.classList.contains("abierto"),
           display: m ? dom.window.getComputedStyle(m).display : "(sin menú)",
           recorte: m ? recortadoPor(m) : "(sin menú)", ops: m ? m.querySelectorAll("button").length : 0 };
}
["dropHist", "dropIr"].forEach(id => {
  const r = abre(id);
  ok(r.abierto && r.display !== "none" && r.recorte === null && r.ops > 0,
    `${id}: el menú se abre y se ve (abierto ${r.abierto}, display ${r.display}, recortado por ${r.recorte}, ${r.ops} opciones)`);
  click(document.body);
});
/* adenda 5 §3: todo control se ve que es un control */
ok(/\.seg button,\.sim-bar button,summary,\.chip\[data-tip\],\.enlace,\[data-jug\],\.drop>button,\.drop-menu button\{cursor:pointer\}/.test(html),
  "todo control lleva cursor:pointer");
ok(/\.drop>button:hover/.test(html) && /:focus-visible/.test(html), "los controles se realzan al pasar el mouse y al enfocarlos");
ok(!$("segModo"), "sin interruptor sencilla/técnica (adenda 3 §1)");
ok(D.acto1.length === 3 && D.cierre.length === 3, `primera parte con tres secciones y cierre con tres (${D.acto1.length}, ${D.cierre.length})`);
ok(D.cierre.map(s => s.id).join() === "c-1,c-red,c-2", `la red de pases va entre «¿Nos creen?» y «Límites» (${D.cierre.map(s => s.id).join()})`);
ok($("anexo") && !$("anexo").open, "el anexo existe y arranca cerrado");
ok($("glosario") && !$("glosario").open && $("glosDl").querySelectorAll("dt").length >= 5, "glosario plegado con sus términos");
ok(document.querySelectorAll("#leyNv .nv").length === 3, "leyenda con los tres niveles");
ok(!/<script[^>]+src=|<link[^>]+href=["']?http|@import/i.test(html), "sin dependencias externas");

/* 2. primera parte */
["inicios", "fig1b"].forEach(f => {
  const el = document.querySelector(`#informe [data-fig="${f}"] .lienzo`);
  ok(el && el.innerHTML.trim().length > 40, `primera parte: figura ${f}`);
});
const ini = document.querySelector('#a1-1 [data-fig="inicios"]').textContent;
ok(["juego abierto", "contragolpe", "saque de banda", "córner", "gol", "pérdida", "balón fuera"].every(x => ini.includes(x)),
  "1.1 nombra las cuatro formas de empezar y los cuatro finales");
if (PROG) ok(/cuatro tableros separados/.test($("a1-1").textContent), "1.1 dice que cada forma de empezar es su propio tablero");
const sim = () => document.querySelector('#a1-2 [data-fig="sim"]');
ok(sim() && /de dónde viene/.test(sim().textContent), "1.2 simulador de flujos (adenda 4 §5)");
if (sim()) {
  click(sim().querySelector('[data-simmapa] [data-z="9"]'));
  ok(sim().querySelectorAll('[data-flecha="va"]').length === 3 && sim().querySelectorAll('[data-flecha="viene"]').length === 3,
    "tocar una zona dibuja tres flechas de salida y tres de llegada");
  ok(/termina la posesión el \d+%/.test(sim().textContent), "dice cómo termina la jugada desde esa zona");
  ok(/de cada 100 balones que pasan por esa zona/.test(sim().textContent),
    "la vista de flujos dice qué son sus porcentajes (adenda 5 §5)");
  /* adenda 5 §5: paso a paso, una acción por clic */
  click(sim().querySelector('[data-sim="modo:jugada"]'));
  ok(/toca una zona de la cancha/i.test(sim().textContent), "«paso a paso» empieza pidiendo la zona");
  click(sim().querySelector('[data-simmapa] [data-z="9"]'));
  const puntos = () => sim().querySelectorAll("[data-simmapa] [data-paso]").length;
  const n0 = puntos();
  let creci = 0, term = false;
  for (let k = 0; k < 12; k++) {
    const antes = puntos(), b = sim().querySelector('[data-sim="paso"]');
    click(b);
    if (/La posesión terminó en/.test(sim().textContent)) { term = true; break; }
    if (puntos() === antes + 1) creci++;
  }
  ok(n0 === 1, `al elegir la zona hay un solo punto (${n0})`);
  ok(creci >= 1 || term, "cada clic en «una acción más» añade una sola acción");
  ok(/inventada por el modelo, no real/.test(sim().textContent), "la jugada paso a paso dice que es inventada por el modelo");
  const caminos = new Set();
  for (let k = 0; k < 8; k++) {
    click(sim().querySelector('[data-sim="otra"]'));
    click(sim().querySelector('[data-simmapa] [data-z="9"]'));
    for (let j = 0; j < 4; j++) { const b = sim().querySelector('[data-sim="paso"]'); if (b) click(b); }
    caminos.add(sim().querySelector("[data-simmapa]").innerHTML.length);
  }
  ok(caminos.size >= 2, `«otra jugada» empieza jugadas distintas (${caminos.size} de 8)`);
  click(sim().querySelector('[data-sim="modo:larga"]'));
  ok(sim().querySelectorAll("text.pctz").length === 20, "«a la larga» pinta el reparto de las veinte zonas");
  ok(/posesiones que ya duraron mucho/.test(sim().textContent), "«a la larga» dice qué son sus porcentajes (adenda 5 §5)");
  verHist("larcamon");
  const bs = [...sim().querySelectorAll('[data-sim^="src:"]')].map(b => b.dataset.sim);
  ok(bs.includes("src:liga") && bs.includes("src:todos") && bs.length === 2 + D.historias.find(h => h.id === "larcamon").eras.length,
    `el simulador deja elegir la liga, cada club y todos sus clubes (${bs.length})`);
  click(sim().querySelector('[data-sim="src:todos"]'));
  ok(sim().querySelector('[data-sim="src:todos"]').classList.contains("on"), "«todos sus clubes» queda activo");
  verHist("jardine");
}
/* adenda 5 §5: el espacio de estados, explicado */
ok(/80/.test($("a1-1").textContent) && /situaciones vivas/.test($("a1-1").textContent),
  "1.1 dice cuántas situaciones vivas tiene la cadena");
ok(/La malla no es más fina/.test($("a1-1").textContent) && /parámetros por observación/.test($("a1-1").textContent), "1.1 dice por qué la malla es de cinco por cuatro");
ok(/probabilidad de paso es contar/.test($("a1-1").textContent) && /terminan la posesión/.test($("a1-1").textContent),
  "1.1 trae un ejemplo de probabilidad de paso");
/* adenda 5 §1 y §2: primero la historia, después el método */
const ordenActos = [...$("informe").querySelectorAll(".acto")].map(a => a.id);
ok(ordenActos.join() === "acto2,acto3,acto1,cierre", `primero la historia y al final el método (${ordenActos.join()})`);
ok(/Cómo lo hicimos, si te interesa/.test($("acto1").textContent), "el método se presenta como opcional");
ok($("portada").querySelector(".quehicimos"), "la portada dice qué hicimos, en cinco líneas");
ok(/posesiones/.test($("portada").querySelector(".quehicimos").textContent), "«qué hicimos» trae sus cifras");
ok($("portada").querySelectorAll(".conclus a").length === (modo === "sin_relevos" ? 2 : 3), "la portada sube las conclusiones");
ok([...$("portada").querySelectorAll(".conclus a")].every(a => document.getElementById(a.dataset.ancla)),
  "cada conclusión enlaza a su evidencia");

/* 3. cada historia */
D.historias.forEach(h => {
  verHist(h.id);
  const hj = D.historias.find(x => x.id === h.id);
  const secs = [...$("informe").querySelectorAll("section")];
  const cuerpo = secs.filter(s => /^a[23]-/.test(s.id));
  ok(cuerpo.length === 10, `${h.id}: diez secciones en «cómo juega» y «de dónde viene» (${cuerpo.length})`);
  /* adenda 4 §2: la carrera y las tres preguntas */
  const car = $("a2-0");
  ok(car && car.querySelectorAll(".c-era").length === h.eras.length, `${h.id}: la carrera trae sus ${h.eras.length} clubes`);
  ok(["¿Cómo juega donde más dirigió?", "¿Juega igual en sus otros clubes?", "¿Él cambió al club o el club lo cambió a él?"]
    .every(t => car.textContent.includes(t)), `${h.id}: las tres preguntas, iguales para todos`);
  if (modo !== "sin_relevos") ok(/no se puede decir que él cambió al club/.test(car.textContent), `${h.id}: la tercera pregunta usa la plantilla fija`);
  ok([...car.querySelectorAll(".fr")].every(f => f.dataset.nivel === "C"), `${h.id}: las tres respuestas son descriptivas (nivel C)`);
  /* adenda 4 §8: nada se apila en una columna larga */
  const apiladas = [...$("informe").querySelectorAll("*")].filter(e => e.children.length > 12 && e.tagName !== "svg" && e.tagName !== "g" && e.tagName !== "TBODY" && e.tagName !== "defs" &&
    dom.window.getComputedStyle(e).display === "flex" && dom.window.getComputedStyle(e).flexDirection === "column");
  ok(apiladas.length === 0, `${h.id}: ninguna lista del cuerpo se apila en una columna de más de doce (${apiladas.map(e => e.className).join()})`);
  const incompletas = cuerpo.filter(s => {
    if (s.querySelector("[data-pendiente]") || s.querySelector(".vacio code")) return false;
    const capas = new Set([...s.querySelectorAll("[data-capa]")].map(x => +x.dataset.capa));
    return !(capas.has(1) && capas.has(2));
  }).map(s => s.id);
  ok(incompletas.length === 0, `${h.id}: toda sección trae frase y figura o las declara (${incompletas})`);
  /* topes */
  const secsG = secs.filter(s => s.id !== "c-red");   /* adenda 10 §7: C.2 se cuenta aparte */
  const palabras = secsG.map(s => s.textContent).join(" ").split(/\s+/).filter(Boolean).length;
  const figuras = [...$("informe").querySelectorAll("[data-fig]")].filter(f => !f.closest("#c-red")).length;
  const tp = topePalabras(h);
  ok(palabras <= tp, `${h.id}: ${palabras} palabras en el cuerpo con ${h.eras.length} clubes (tope ${tp})`);
  ok(secs.length <= TOPE.secciones, `${h.id}: ${secs.length} secciones (tope ${TOPE.secciones})`);
  ok(figuras <= TOPE.figuras, `${h.id}: ${figuras} figuras en el cuerpo (tope ${TOPE.figuras})`);
  /* jerga */
  const j = jergaCuerpo();
  ok(j.length === 0, `${h.id}: sin jerga en el cuerpo${j.length ? " · " + j.slice(0, 3).join(" | ") : ""}`);
  ok(!$("informe").querySelector(".fr .tec") && !/\bq = /.test([...$("informe").querySelectorAll(".fr")].map(f => f.textContent).join(" ")),
    `${h.id}: las frases del cuerpo no traen intervalos ni q (los intervalos van en las figuras)`);
  /* enlaces al anexo */
  const enl = [...$("informe").querySelectorAll("[data-enlace]")];
  ok(enl.length >= 8 && enl.every(a => document.getElementById(a.dataset.enlace)), `${h.id}: cada «cómo lo medimos» lleva al anexo (${enl.length})`);
  /* 2.1 a 2.2 */
  const s21 = (hj.acto2.find(x => x.id === "a2-1").bloques || []);
  if (s21.some(b => b.id === "serie"))
    ok(/Torneo a torneo/.test($("a2-1").textContent) && document.querySelector('#a2-1 [data-fig="serie"] svg'), `${h.id}: 2.1 dice que se sostiene torneo a torneo`);
  if (PROG) {
    ok(/última franja del campo/.test($("a2-2").textContent), `${h.id}: 2.2 habla de llegar a la última franja del campo`);
    /* adenda 7 §3: la jugada de ejemplo YA NO está en el cuerpo; vive en el anexo */
    ok(!document.querySelector('#a2-2 [data-fig="jugada"]'), `${h.id}: la jugada no está en el cuerpo`);
    ok(!!$("anexo").querySelector('#x-a2-2 [data-fig="jugada"]') || !!$("anexo").querySelector('#x-a2-2 .hueco'),
      `${h.id}: la jugada, o su hueco, sigue completa en el anexo`);
    /* adenda 7 §2: la figura del cuerpo son SUS clubes, no los cinco técnicos */
    const brs = [...document.querySelectorAll('#a2-2 [data-fig="prog"] .bint .br .br-n')].map(e => e.textContent);
    const susClubes = h.eras.map(e => e.club);
    ok(brs.length > 0 && brs.every(t => susClubes.some(c => t.includes(c))),
      `${h.id}: 2.2 compara sus clubes (${brs.join(" | ")})`);
    ok(brs.some(t => /donde más dirigió/.test(t)), `${h.id}: 2.2 marca el club donde más dirigió`);
    ok([...$("anexo").querySelectorAll('#x-a2-2 [data-fig="prog"] .br-n')].length >= 5,
      `${h.id}: la comparación de los cinco técnicos sigue en el anexo`);
  } else {
    ok(/progresion_v1\.json/.test($("a2-2").textContent) && document.querySelector("#a2-2 code"), `${h.id}: 2.2 sin insumo: muestra el comando`);
  }
  /* 3.1 y 3.2 */
  if (modo !== "sin_relevos") {
    ok(document.querySelectorAll('#a3-1 [data-fig="relevos"] rect').length >= 1, `${h.id}: 3.1 con las barras de relevos`);
    ok(/reparto de las acciones/.test($("a3-1").textContent), `${h.id}: 3.1 cuenta los relevos en palabras`);
    ok(/mismo técnico en el mismo club/.test($("a3-1").textContent), `${h.id}: 3.1 dice qué pasó con el control`);
    ok(/sin cambiar de técnico/.test($("a3-1").textContent), `${h.id}: 3.1 trae el placebo`);
    if (modo !== "sin_contexto") {
      ok(document.querySelectorAll('#a3-2 [data-fig="estilos"] circle').length >= 20, `${h.id}: 3.2 pinta el mapa de estilos`);
      ok(document.querySelectorAll('#a3-2 [data-esquina]').length === 4 && /Cómo leer el mapa/.test($("a3-2").textContent), `${h.id}: el mapa nombra sus cuatro esquinas y dice cómo leerse`);
    }
    ok(document.querySelector('#anexo [data-fig="cu"]') && document.querySelector('#anexo [data-fig="mapas_dif"]'),
      `${h.id}: plantel contra uso completo en el anexo`);
  } else {
    ok(/relevos_v1\.json/.test($("a3-1").textContent) && document.querySelector("#a3-1 code"), `${h.id}: 3.1 muestra el comando que falta`);
  }
  /* portada */
  const port = [...document.querySelectorAll("#portada a")];
  ok(port.length === (modo === "sin_relevos" ? 7 : 8) || modo === "sin_contexto", `${h.id}: portada con las conclusiones y las cinco frases (${port.length})`);
  ok(port.every(a => document.getElementById(a.dataset.ancla)), `${h.id}: cada frase de portada apunta a su sección`);
  ok(document.querySelectorAll("[data-portada]").length === document.querySelectorAll("#portada [data-portada]").length * 2,
    `${h.id}: ninguna frase de portada se duplica en el anexo`);
  ok(!$("informe").querySelector("[data-portada-solo]") && !/Miramos/.test($("a1-1").textContent),
    `${h.id}: «qué hicimos» vive solo en la portada`);
  const eras = document.querySelectorAll("#eras .chip").length;
  ok(eras === h.eras.length && eras >= 2, `${h.id}: ${eras} clubes en la cabecera`);
  /* adenda 7 §1: los clubes lado a lado, sin ningún selector */
  const otro = h.eras.find(e => e.club !== h.principal);
  ok(!$("informe").querySelector("[data-selclub]"), `${h.id}: no queda ningún selector de club en el cuerpo`);
  if (otro) {
    const secs2 = [...$("informe").querySelectorAll("[data-porclub]")];
    ok(secs2.length >= 3, `${h.id}: hay secciones con los clubes lado a lado (${secs2.length})`);
    secs2.forEach(sec => {
      const cols = [...sec.querySelectorAll(".pc-col")].map(c => c.dataset.club);
      ok(cols.length === +sec.dataset.porclub && cols.every(c => h.eras.some(e => e.club === c)),
        `${h.id}/${sec.id}: una columna por club (${cols.join(" | ")})`);
      ok(/donde más dirigió/.test(sec.querySelector(".porclub").textContent),
        `${h.id}/${sec.id}: se dice cuál es el club donde más dirigió`);
    });
    const alguna = secs2.find(x => x.id === "a2-1") || secs2[0];
    ok(alguna.textContent.includes(otro.club), `${h.id}: ${otro.club} aparece sin tocar nada`);
  }
  /* adenda 8 §1-§2: la figura trae los clubes dentro, con la misma escala */
  if (otro) {
    const mf = document.querySelector('#a2-1 [data-fig="zonas_clubes"] .mapfila');
    ok(!!mf, `${h.id}: 2.1 trae un mapa por club`);
    if (mf) {
      const cl = [...mf.querySelectorAll(".mf-uno")].map(e => e.dataset.club);
      ok(cl.length === h.eras.length && cl.every(c => h.eras.some(e => e.club === c)),
        `${h.id}: 2.1 tiene los ${h.eras.length} mapas (${cl.join(" | ")})`);
      const conMapa = mf.querySelectorAll("svg[data-cancha]").length;
      ok(+mf.dataset.mapas === cl.length &&
         (conMapa === 0 ? mf.querySelectorAll(".vacio").length === cl.length : +mf.dataset.escala > 0),
        `${h.id}: 2.1 ${conMapa ? "comparte una sola escala (" + mf.dataset.escala + ")" : "declara el hueco de cada club"}`);
      ok(/comparten la escala/.test($("a2-1").textContent), `${h.id}: 2.1 dice que la escala es común`);
    }
    const tc = document.querySelector('#a2-3 [data-fig="tarjetas_clubes"]');
    ok(!!tc, `${h.id}: 2.3 trae las tarjetas por club`);
    if (tc) {
      const porTarjeta = [...tc.querySelectorAll(".card .bint")].map(b => b.querySelectorAll(".br").length);
      ok(porTarjeta.length >= 3 && porTarjeta.every(n => n === h.eras.length),
        `${h.id}: cada tarjeta de 2.3 tiene una barra por club (${porTarjeta.join(",")})`);
    }
  }
  /* ADR-63 §5 y adenda 8 §3: los mismos jugadores con otro técnico */
  const jz = $("a3-1");
  const conJz = !!jz.querySelector('[data-fig="jz_mapas"]');
  if (conJz) {
    ok(/los mismos jugadores/i.test(jz.textContent), `${h.id}: 3.1 dice que compara jugadores consigo mismos`);
    ok(/punto porcentual/.test(jz.textContent) && /no «el doble»/.test(jz.textContent),
      `${h.id}: explica qué es un punto porcentual`);
    ok(/no por qué/.test(jz.textContent) && /lesión/.test(jz.textContent),
      `${h.id}: la frase de no-causalidad está`);
    const leg = jz.querySelector(".jzleg");
    ok(!!leg && /más presencia con/.test(leg.textContent) && !/positivo|negativo/.test(leg.textContent),
      `${h.id}: la leyenda va encima y nombra a los dos técnicos`);
    const mf2 = jz.querySelector('[data-fig="jz_mapas"] .mapfila');
    ok(!!mf2 && +mf2.dataset.mapas === 2 && +mf2.dataset.escala > 0,
      `${h.id}: los dos mapas del jugador comparten escala`);
    ok(jz.querySelectorAll('[data-fig="jz_rank"] .item').length >= 3, `${h.id}: el ranking de quién cambió más`);
  } else {
    ok(!!jz.querySelector(".hueco") || !!jz.querySelector(".vacio"),
      `${h.id}: si no hay jugadores comparables, se declara`);
  }
  const b24 = (hj.acto2.find(x => x.id === "a2-4").bloques || []);
  if (b24.some(b => b.tipo === "hueco" && /seis clubes/.test(b.html)))
    ok(/seis clubes/.test($("a2-4").textContent), `${h.id}: presión declarada fuera de los seis clubes medidos`);
});
verHist("herrera");
ok(!/Hector/.test($("eras").textContent), "un homónimo no entra a la historia (igualdad exacta)");
verHist("jardine");

verHist("larcamon");
if (modo !== "sin_contexto") {
  ok(document.querySelectorAll('#a2-6 [data-fig="ctx4"] .lienzo .card').length === 4, "contexto en cuatro paneles (adenda 4 §4)");
  ok(/Los que más jugaron/.test($("a2-8").textContent), "2.7 nombra a los que más jugaron");
}
if (modo !== "sin_contexto") ok(document.querySelectorAll('#c-1 [data-fig="marcador"] .tema').length >= 5, "el marcador va agrupado por tema");
verHist("jardine");

/* ADR-59 adenda 10: la red de pases, sin resolver */
const red = $("c-red");
ok(!!red, "cierre: la sección de la red de pases existe");
if (red && !red.querySelector(".vacio code")) {
  const tr = red.textContent.replace(/\s+/g, " ");
  ok(/No sabemos si la red cambia más cuando cambia el técnico/.test(tr), "la red: dice, literal, que no se resolvió");
  ok(/error nuestro/.test(tr), "la red: nombra el error como nuestro");
  ok(/no quién lo causó/.test(tr) && /paso del tiempo/.test(tr), "la red: no separa al técnico del paso del tiempo");
  ok(!/(se mueve|cambia) lo mismo|cambie o no|placebo|percentil/i.test(tr), "la red: sin las frases de retiro ni jerga (adenda 10 §3)");
  ok([...red.querySelectorAll(".fr")].every(f => f.dataset.nivel === "C"), "la red: todo es descriptivo (nivel C)");
  const pr = tr.split(/\s+/).filter(Boolean).length, fr = red.querySelectorAll("[data-fig]").length;
  ok(pr <= TOPE.red.palabras && fr <= TOPE.red.figuras,
    `la red: ${pr} palabras y ${fr} figura, con su tope aparte (${TOPE.red.palabras} y ${TOPE.red.figuras})`);
  const sv = red.querySelector('[data-fig="red_phi"] svg[data-red]');
  ok(!!sv && sv.querySelectorAll("circle").length === +sv.dataset.n && +sv.dataset.n > 0,
    `la red: un punto por cambio de técnico (${sv ? sv.querySelectorAll("circle").length : 0})`);
  ok(!!sv && !sv.querySelector("marker, [marker-end]"), "la red: sin flechas entre técnicos");
  const xr = $("anexo").querySelector("#x-c-red");
  ok(!!xr, "la red: su «cómo lo medimos» completo en el anexo");
  if (xr) {
    ok(/no se lee/.test(xr.textContent), "anexo: la prueba con el error va marcada como que no se lee");
    ok(/Fallo tres/.test(xr.textContent) && /Fallo uno bis/.test(xr.textContent), "anexo: el catálogo de los fallos de la red");
    ok(xr.querySelectorAll("table.tabla tbody tr").length >= 1, "anexo: la tabla de relevos de la corrida única");
  }
  const m62 = document.querySelectorAll('#c-1 [data-fig="marcador"] .tema');
  if (modo !== "sin_contexto") ok([...m62].some(t => /red de pases/.test(t.textContent)), "el marcador trae la red de pases");
}

/* 4. niveles y fuentes */
const frases = [...$("informe").querySelectorAll(".fr")];
ok(frases.length > 15, `frases con nivel en el cuerpo: ${frases.length}`);
ok(frases.every(f => ["A", "B", "C"].includes(f.dataset.nivel)), "toda frase lleva nivel");
ok(frases.every(f => ["probado", "medido", "descriptivo"].includes(f.querySelector(".nv").textContent)), "el nivel se dice en palabras");
const cifras = [...$("informe").querySelectorAll(".cf")];
ok(cifras.length > 20 && cifras.every(c => c.dataset.f && c.dataset.f.length > 3), `toda cifra del cuerpo trae fuente (${cifras.length})`);
const nulos = frases.filter(f => f.classList.contains("nulo"));
ok(nulos.every(f => /(mayor|menor) a|sobreviven a la correcci/.test(f.textContent)), `cada nulo dice su margen (${nulos.length})`);
ok(frases.filter(f => f.dataset.nivel === "B").every(f => !/\[/.test(f.textContent)), "ninguna frase B del cuerpo imprime su intervalo (va en la figura y el anexo)");
ok(/nv-A\{background:var\(--sem-a\)/.test(html), "el semáforo usa sus tokens");

/* 5. anexo */
const anexo = $("anexo");
ok(anexo.querySelectorAll("section").length >= 15, `el anexo trae las secciones completas (${anexo.querySelectorAll("section").length})`);
ok(/q = /.test(anexo.textContent) && anexo.querySelectorAll(".tec").length > 10, "en el anexo sí están q e intervalos");
ok([...anexo.querySelectorAll("details.plegable")].every(d => d.open), "los «cómo lo medimos» del anexo van abiertos");
if (modo === "completo") {
  ["fig9", "fig3", "fig4", "fig5", "fig8", "eras_pos", "fig7b", "roles"].forEach(f => {
    const el = anexo.querySelector(`[data-fig="${f}"] .lienzo`);
    ok(el && el.innerHTML.trim().length > 40, `anexo: figura ${f}`);
  });
  if (PROG) ok(anexo.querySelector('[data-fig="p4"] circle'), "anexo: dispersión de P4");
  ok(anexo.querySelector("#x-c-3 [data-pendiente]"), "anexo: catálogo de errores declarado como pendiente");
  const pts = anexo.querySelectorAll('[data-fig="fig9"] .pto');
  ok(pts.length >= 20 && anexo.querySelectorAll('[data-fig="fig9"] .pto.no').length > 0, `marcador completo con fallos a la vista (${pts.length})`);
  ok(document.querySelectorAll('#c-1 [data-fig="marcador"] .pto').length === pts.length, "el marcador corto del cierre cuenta las mismas predicciones");
}

/* 6. colores */
const lienzos = [...document.querySelectorAll(".lienzo")].map(l => l.innerHTML).join("");
["#ff453a", "#30d158", "#0a84ff", "#ffd60a", "#173f29"].forEach(c => ok(!lienzos.includes(c), `sin color cableado ${c}`));
ok(/var\(--a1\)/.test(lienzos), "las figuras usan el token --a1");

/* 7. mapas */
const mapaRol = document.querySelector('[data-fig="roles"] svg[data-cancha]');
if (mapaRol) {
  const s = [...mapaRol.querySelectorAll("text.pctz")].map(t => parseInt(t.textContent));
  ok(s.length === 20 && s.reduce((a, b) => a + b, 0) === 100, `las 20 casillas suman 100 (${s.reduce((a, b) => a + b, 0)})`);
}
const f2 = document.querySelector('#a2-1 [data-fig="fig2"]');
ok(f2 && (/Falta/.test(f2.textContent) || f2.querySelector("svg[data-cancha]")), "mapa de zonas: se pinta o declara el parquet");

/* 8. interacción */
try {
  click(document.querySelector('[data-fig="prog"] [data-seg] button[data-k="tau"]'));
  ok(/tiempo hasta llegar/.test(document.querySelector('[data-fig="prog"]').textContent), "2.2 cambia a tiempo hasta llegar");
} catch (e) { ok(!PROG, "prog: " + e.message); }
try {
  const it = document.querySelectorAll('[data-fig="roles"] [data-jug]')[2];
  click(it);
  ok(document.querySelectorAll('[data-fig="roles"] .item.on')[0].dataset.jug === it.dataset.jug, "tocar un jugador cambia el mapa");
} catch (e) { ok(false, "roles: " + e.message); }
try {
  click(document.querySelector('#a2-8 [data-fig="fig6"] button[data-k="n80"]'));
  ok(/juntan el 80%/.test(document.querySelector('#a2-8 [data-fig="fig6"]').innerHTML), "2.7 pasa a jugadores con el 80% de los minutos");
} catch (e) { ok(modo === "sin_contexto", "fig6: " + e.message); }
const tip = $("tip");
click(document.querySelector("#anexo .cf"));
ok(tip.classList.contains("fijo") && /fuente/.test(tip.innerHTML), "en el anexo, tocar una cifra fija su fuente");

/* 9. sin insumos */
if (modo === "sin_contexto") {
  const s26 = $("a2-6");
  ok(/contexto_v1\.json/.test(s26.textContent) && s26.querySelector("code"), "contexto muestra el comando que falta");
  ok($("c-1").querySelector(".vacio"), "el cierre también (marcador)");
  ok($("a2-1").querySelectorAll(".fr").length >= 1, "el resto se pinta igual");
  ok(/falta/.test($("traza").textContent), "la huella del anexo marca el JSON ausente");
}

/* adenda 6 §2 y §3: etiquetas que no mienten */
ok(![$("informe"), document.querySelector("header"), $("anexo")]
    .some(z => z && z.textContent.includes("todos sus clubes")),
  "en ninguna parte visible se promete un agregado de «todos sus clubes»");
ok(!$("informe").textContent.includes("percentil"), "«percentil» ya no está en el cuerpo");
ok($("anexo").textContent.includes("percentil"), "«percentil» sigue en el anexo");

/* 10. legibilidad */
const chicos = [...document.querySelectorAll("svg text")].filter(t => parseFloat(t.getAttribute("font-size") || "12") < 10);
ok(chicos.length === 0, `sin texto SVG por debajo de 10px (${chicos.length})`);

console.log(fallos ? `\n${fallos} FALLAS` : "\nhumo en verde");
process.exit(fallos ? 1 : 0);
