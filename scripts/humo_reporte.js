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

/* topes y jerga de la adenda 3 (§5 y §7) */
const TOPE = { palabras: 2500, secciones: 14, figuras: 16 };
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
ok(document.querySelectorAll("#segHist button").length === 5, "selector con cinco historias");
ok(document.querySelectorAll("#segActo button").length === 4, "índice por partes");
ok(!$("segModo"), "sin interruptor sencilla/técnica (adenda 3 §1)");
ok(D.acto1.length === 3 && D.cierre.length === 2, `primera parte con tres secciones y cierre con dos (${D.acto1.length}, ${D.cierre.length})`);
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
if (PROG) ok(/nunca cambia su forma de empezar/.test($("a1-1").textContent), "1.1 dice que cada forma de empezar es su propio tablero");
const sim = document.querySelector('#a1-2 [data-fig="sim"]');
ok(sim && sim.querySelectorAll("[data-z]").length === 20, "1.2 simulador con sus veinte casillas");
if (sim) {
  const vivas = () => +sim.querySelector("[data-vivas]").dataset.vivas;
  click(sim.querySelector('[data-simmapa] [data-z="5"]'));
  ok(/zona que tocaste/.test(sim.textContent) && vivas() === 100, "tocar una zona empieza ahí, con todas vivas");
  click(sim.querySelector('[data-sim="uno"]'));
  const v1 = vivas();
  ok(v1 < 100 && /1 acciones/.test(sim.textContent), `una acción más: siguen vivas ${v1}`);
  click(sim.querySelector('[data-sim="diez"]'));
  ok(vivas() < v1, "diez acciones más: quedan menos vivas");
  click(sim.querySelector('[data-sim="fin"]'));
  const fin = [...sim.querySelectorAll("text.pctz")].map(t => t.textContent).join();
  click(sim.querySelector('[data-sim="reset"]'));
  click(sim.querySelector('[data-simmapa] [data-z="18"]'));
  click(sim.querySelector('[data-sim="fin"]'));
  const fin2 = [...sim.querySelectorAll("text.pctz")].map(t => t.textContent).join();
  ok(fin === fin2, "hasta el final: empiece donde empiece, el reparto es el mismo");
  const era = sim.querySelector('[data-sim="era"]');
  ok(!!era, "se puede cambiar al técnico de la historia");
  if (era) { click(era); ok(sim.querySelector('[data-sim="era"]').classList.contains("on"), "el botón del técnico queda activo"); }
  click(sim.querySelector('[data-sim="reset"]'));
}

/* 3. cada historia */
D.historias.forEach(h => {
  click(document.querySelector(`#segHist button[data-k="${h.id}"]`));
  const hj = D.historias.find(x => x.id === h.id);
  const secs = [...$("informe").querySelectorAll("section")];
  const cuerpo = secs.filter(s => /^a[23]-/.test(s.id));
  ok(cuerpo.length === 9, `${h.id}: nueve secciones en «cómo juega» y «de dónde viene» (${cuerpo.length})`);
  const incompletas = cuerpo.filter(s => {
    if (s.querySelector("[data-pendiente]") || s.querySelector(".vacio code")) return false;
    const capas = new Set([...s.querySelectorAll("[data-capa]")].map(x => +x.dataset.capa));
    return !(capas.has(1) && capas.has(2));
  }).map(s => s.id);
  ok(incompletas.length === 0, `${h.id}: toda sección trae frase y figura o las declara (${incompletas})`);
  /* topes */
  const palabras = secs.map(s => s.textContent).join(" ").split(/\s+/).filter(Boolean).length;
  const figuras = $("informe").querySelectorAll("[data-fig]").length;
  ok(palabras <= TOPE.palabras, `${h.id}: ${palabras} palabras en el cuerpo (tope ${TOPE.palabras})`);
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
    ok(/franja del área/.test($("a2-2").textContent), `${h.id}: 2.2 habla de llegar a la franja del área`);
    const b22 = (hj.acto2.find(x => x.id === "a2-2").bloques || []);
    const conJug = b22.some(b => b.tipo === "fig" && b.id === "jugada");
    ok(conJug ? !!document.querySelector('#a2-2 [data-fig="jugada"] circle') : b22.some(b => b.tipo === "hueco"),
      `${h.id}: jugada de ejemplo ${conJug ? "dibujada" : "declarada"}`);
  } else {
    ok(/progresion_v1\.json/.test($("a2-2").textContent) && document.querySelector("#a2-2 code"), `${h.id}: 2.2 sin insumo: muestra el comando`);
  }
  /* 3.1 y 3.2 */
  if (modo !== "sin_relevos") {
    ok(document.querySelector('#a3-1 [data-fig="fig_T"] circle'), `${h.id}: 3.1 con la figura de relevos`);
    ok(/reparto de las acciones/.test($("a3-1").textContent), `${h.id}: 3.1 cuenta los relevos en palabras`);
    ok(/mismo técnico en el mismo club/.test($("a3-1").textContent), `${h.id}: 3.1 dice qué pasó con el control`);
    ok(/sin cambiar de técnico/.test($("a3-1").textContent), `${h.id}: 3.1 trae el placebo`);
    if (modo !== "sin_contexto")
      ok(document.querySelectorAll('#a3-2 [data-fig="estilos"] circle').length >= 20, `${h.id}: 3.2 pinta el mapa de estilos`);
    ok(document.querySelector('#anexo [data-fig="cu"]') && document.querySelector('#anexo [data-fig="mapas_dif"]'),
      `${h.id}: plantel contra uso completo en el anexo`);
  } else {
    ok(/relevos_v1\.json/.test($("a3-1").textContent) && document.querySelector("#a3-1 code"), `${h.id}: 3.1 muestra el comando que falta`);
  }
  /* portada */
  const port = [...document.querySelectorAll("#portada a")];
  ok(port.length === 5 || modo === "sin_contexto", `${h.id}: portada con cinco frases (${port.length})`);
  ok(port.every(a => document.getElementById(a.dataset.ancla)), `${h.id}: cada frase de portada apunta a su sección`);
  ok(document.querySelectorAll("[data-portada]").length === port.length * 2, `${h.id}: ninguna frase de portada se duplica en el anexo`);
  const eras = document.querySelectorAll("#eras .chip").length;
  ok(eras === h.eras.length && eras >= 2, `${h.id}: ${eras} clubes en la cabecera`);
  const b24 = (hj.acto2.find(x => x.id === "a2-4").bloques || []);
  if (b24.some(b => b.tipo === "hueco" && /seis clubes/.test(b.html)))
    ok(/seis clubes/.test($("a2-4").textContent), `${h.id}: presión declarada fuera de los seis clubes medidos`);
});
click(document.querySelector('#segHist button[data-k="herrera"]'));
ok(!/Hector/.test($("eras").textContent), "un homónimo no entra a la historia (igualdad exacta)");
click(document.querySelector('#segHist button[data-k="jardine"]'));

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

/* 10. legibilidad */
const chicos = [...document.querySelectorAll("svg text")].filter(t => parseFloat(t.getAttribute("font-size") || "12") < 10);
ok(chicos.length === 0, `sin texto SVG por debajo de 10px (${chicos.length})`);

console.log(fallos ? `\n${fallos} FALLAS` : "\nhumo en verde");
process.exit(fallos ? 1 : 0);
