/* Humo del informe H7 (tres actos, cinco historias) en un DOM real.
   node scripts/humo_reporte.js pagina.html [completo|sin_contexto] */
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

ok(errores.length === 0, `sin excepciones al cargar (${errores.slice(0, 2).join(" | ")})`);

/* 1. estructura de la adenda 2 */
ok(D.historias.map(h => h.id).join() === "jardine,larcamon,ambriz,herrera,ortiz", "cinco historias, en orden");
ok(document.querySelectorAll("#segHist button").length === 5, "selector con cinco historias");
ok(document.querySelectorAll("#segActo button").length === 4, "índice por actos");
ok(document.querySelectorAll("#segModo button").length === 2, "interruptor sencilla / técnica");
ok(D.acto1.length === 7 && D.cierre.length === 3, "acto 1 con siete bloques, cierre con tres");
["acto1", "acto2", "acto3", "cierre"].forEach(a => ok(document.getElementById(a), `cabecera ${a}`));
ok(!/<script[^>]+src=|<link[^>]+href=["']?http|@import/i.test(html), "sin dependencias externas");

/* 2. acto 1 */
["fig1", "cadena", "estimacion", "semaforo", "fig1b"].forEach(f => {
  const el = document.querySelector(`#acto1 ~ section [data-fig="${f}"] .lienzo, [data-fig="${f}"] .lienzo`);
  ok(el && el.innerHTML.trim().length > 40, `acto 1: figura ${f}`);
});
const PROG = modo !== "sin_progresion";
ok(!/se comunican entre sí;/.test(document.getElementById("a1-2").textContent), "1.2 ya no dice que todos los estados vivos se comunican");
if (PROG) {
  ok(/conserva la fase/.test(document.getElementById("a1-2").textContent), "1.2 con la corrección de ADR-61 §0");
  ["viva", "superv"].forEach(f => {
    const el = document.querySelector(`[data-fig="${f}"] .lienzo`);
    ok(el && el.innerHTML.trim().length > 40, `acto 1: figura ${f} (ADR-61)`);
  });
  const segv = document.querySelectorAll('[data-fig="viva"] [data-seg] button');
  ok(segv.length === 3, "1.6: tres pasos de la animación");
  if (segv.length === 3) { click(segv[2]); ok(/cuasi-estacionaria/.test(document.querySelector('[data-fig="viva"]').textContent), "1.6: el último paso es la cuasi-estacionaria"); }
} else {
  ok(/supervivencia_v1\.json/.test(document.getElementById("a1-6").textContent) && document.querySelector("#a1-6 code"), "1.6 sin insumo: muestra el comando");
  ok(/supervivencia_v1\.json/.test(document.getElementById("a1-7").textContent), "1.7 sin insumo: lo declara");
}

/* 3. cada historia */
const CUATRO = [1, 2, 3, 4];
D.historias.forEach(h => {
  click(document.querySelector(`#segHist button[data-k="${h.id}"]`));
  const secs = [...document.querySelectorAll("#informe section")].filter(s => /^a[23]-/.test(s.id));
  ok(secs.length === 12, `${h.id}: doce secciones en los actos 2 y 3 (${secs.length})`);
  const incompletas = secs.filter(s => {
    if (s.querySelector("[data-pendiente]") || s.querySelector(".vacio code")) return false;
    const capas = new Set([...s.querySelectorAll("[data-capa]")].map(x => +x.dataset.capa));
    return !CUATRO.every(c => capas.has(c));
  }).map(s => s.id);
  ok(incompletas.length === 0, `${h.id}: toda sección trae sus cuatro capas o se declara (${incompletas})`);
  if (PROG) {
    ok(!document.querySelector("#a2-2 [data-pendiente]"), `${h.id}: 2.2 ya no está pendiente`);
    ok(/franja del área/.test(document.getElementById("a2-2").textContent), `${h.id}: 2.2 habla de la franja del área`);
    const fp = document.querySelector('#a2-2 [data-fig="prog"] .lienzo');
    ok(fp && fp.querySelectorAll("circle").length >= 4, `${h.id}: 2.2 figura de las cinco eras`);
    /* lo esperado sale de los datos embebidos, no de los casos del sintético */
    const hj = D.historias.find(x => x.id === h.id);
    const b22 = (hj.acto2.find(x => x.id === "a2-2").bloques || []);
    const conJug = b22.some(b => b.tipo === "fig" && b.id === "jugada");
    const jugOk = conJug ? !!document.querySelector('#a2-2 [data-fig="jugada"] circle')
                         : b22.some(b => b.tipo === "hueco" && b.capa === 3);
    ok(jugOk, `${h.id}: jugada de ejemplo ${conJug ? "dibujada" : "declarada como hueco"}`);
    ok(document.querySelector('#a2-2 [data-fig="p4"] circle'), `${h.id}: dispersión de P4`);
    const b21 = (hj.acto2.find(x => x.id === "a2-1").bloques || []);
    const conViva = b21.some(b => b.tipo === "fig" && b.id === "viva_era");
    const vivaOk = conViva ? !!document.querySelector('#a2-1 [data-fig="viva_era"] svg')
                           : /no es evaluable|progresion_v1/.test(document.getElementById("a2-1").textContent);
    ok(vivaOk, `${h.id}: 2.1 ${conViva ? "trae dónde vive una posesión viva" : "declara por qué no la trae"}`);
  } else {
    ok(/progresion_v1\.json/.test(document.getElementById("a2-2").textContent) && document.querySelector("#a2-2 code"), `${h.id}: 2.2 sin insumo: muestra el comando`);
  }
  if (modo !== "sin_relevos") {
    ["fig_T", "cu", "mapas_dif", "estilos"].forEach(f => {
      const el = document.querySelector(`[data-fig="${f}"] .lienzo`);
      ok(el && el.innerHTML.trim().length > 40, `${h.id}: figura ${f} (ADR-60)`);
    });
    ok(/Uso del campo tras el relevo/.test(document.getElementById("a3-1").textContent), `${h.id}: 3.1 trae T`);
    ok(/El control no aisló al técnico/.test(document.getElementById("a3-1").textContent), `${h.id}: 3.1 dice qué pasó con el control`);
    ok(/Placebo exploratorio/.test(document.getElementById("a3-1").textContent), `${h.id}: 3.1 trae el placebo`);
    ok(document.querySelectorAll("#a3-2 .fr").length >= 1, `${h.id}: 3.2 con frases`);
    ok(document.querySelectorAll('[data-fig="estilos"] circle').length >= 20, `${h.id}: el mapa pinta las eras`);
  } else {
    ok(/relevos_v1\.json/.test(document.getElementById("a3-2").textContent) && document.querySelector("#a3-2 code"),
      `${h.id}: 3.2 muestra el comando que falta`);
    ok(document.querySelector("#a3-1 .hueco"), `${h.id}: 3.1 declara que falta T`);
  }
  const port = [...document.querySelectorAll("#portada a")];
  ok(port.length === 5 || modo === "sin_contexto", `${h.id}: portada con cinco frases (${port.length})`);
  ok(port.every(a => document.getElementById(a.dataset.ancla)), `${h.id}: cada frase de portada apunta a su sección`);
  ok(port.every(a => a.querySelectorAll(".nv").length === 1), `${h.id}: cada frase de portada con un nivel`);
  const eras = document.querySelectorAll("#eras .chip").length;
  ok(eras === h.eras.length && eras >= 2, `${h.id}: ${eras} eras en la cabecera`);
  if (modo === "completo") {
    ["eras_pos", "tarjetas", "concedido", "fig4", "fig5", "fig6", "fig7", "fig8", "fig3"].forEach(f => {
      const el = document.querySelector(`[data-fig="${f}"] .lienzo`);
      ok(el && el.innerHTML.trim().length > 40, `${h.id}: figura ${f}`);
    });
  }
  const s24 = document.getElementById("a2-4");
  if (["ambriz", "herrera"].includes(h.id))
    ok(/ADR-54/.test(s24.querySelector(".hueco")?.textContent || ""), `${h.id}: presión declarada fuera de ADR-54`);
  else if (modo === "completo")
    ok(s24.querySelector('[data-fig="fig3b"]'), `${h.id}: presión con su bosque`);
});
click(document.querySelector('#segHist button[data-k="herrera"]'));
ok(!/Hector/.test(document.getElementById("eras").textContent), "un homónimo no entra a la historia (igualdad exacta)");
click(document.querySelector('#segHist button[data-k="jardine"]'));

/* 4. niveles, semáforo y fuentes */
const frases = [...document.querySelectorAll("#informe .fr")];
ok(frases.length > 30, `frases con nivel: ${frases.length}`);
ok(frases.every(f => ["A", "B", "C"].includes(f.dataset.nivel)), "toda frase lleva A, B o C");
ok(frases.every(f => f.querySelectorAll(".nv").length === 1), "un solo nivel por frase");
const cifras = [...document.querySelectorAll("#informe .cf")];
ok(cifras.length > 40 && cifras.every(c => c.dataset.f && c.dataset.f.length > 3),
  `toda cifra en el texto trae fuente (${cifras.length})`);
const nulos = frases.filter(f => f.classList.contains("nulo"));
ok(nulos.length >= 5, `nulos visibles (${nulos.length})`);
ok(nulos.every(f => /(mayor|menor) a|sobreviven a la correcci/.test(f.textContent)),
  "cada nulo dice su margen o su conteo tras corregir");
ok(frases.filter(f => f.dataset.nivel === "B").every(f => /\[/.test(f.textContent)),
  "toda frase B trae un intervalo (oculto en modo sencillo, no borrado)");
ok(/--sem-a/.test(html) && /nv-A\{background:var\(--sem-a\)/.test(html), "el semáforo usa sus tokens");
if (modo === "completo") {
  click(document.querySelector('#segHist button[data-k="larcamon"]'));
  ok([...document.querySelectorAll("#informe .fr")].some(f => f.dataset.nivel === "A" && /Difiere/.test(f.textContent)),
    "una historia sin lectura preinscrita redacta un contraste que sobrevive");
  click(document.querySelector('#segHist button[data-k="jardine"]'));
}

/* 5. modo sencillo / técnico */
ok(!document.body.classList.contains("tecnica"), "arranca en modo sencillo");
ok(document.querySelectorAll("#informe .tec").length > 20, "los intervalos y q van marcados como técnicos");
click(document.querySelector('#segModo button[data-k="tecnica"]'));
ok(document.body.classList.contains("tecnica"), "el interruptor pasa a técnico");
const met = [...document.querySelectorAll("details.metodo")];
ok(met.length > 5 && met.every(d => d.open), `en técnico los plegables «cómo lo medimos» se abren (${met.length})`);
click(document.querySelector('#segModo button[data-k="sencilla"]'));
ok(!document.body.classList.contains("tecnica") && met.every(d => !d.open), "y vuelve a sencillo");

/* 6. colores: sin colores cableados en figuras */
const lienzos = [...document.querySelectorAll(".lienzo")].map(l => l.innerHTML).join("");
["#ff453a", "#30d158", "#0a84ff", "#ffd60a", "#173f29"].forEach(c =>
  ok(!lienzos.includes(c), `sin color cableado ${c}`));
ok(/var\(--a1\)/.test(lienzos), "las figuras usan el token --a1");

/* 7. mapas */
const mapaRol = document.querySelector('[data-fig="roles"] svg[data-cancha]');
if (mapaRol) {
  const s = [...mapaRol.querySelectorAll("text.pctz")].map(t => parseInt(t.textContent));
  ok(s.length === 20 && s.reduce((a, b) => a + b, 0) === 100, `las 20 casillas suman 100 (${s.reduce((a, b) => a + b, 0)})`);
}
const f2 = document.querySelector('[data-fig="fig2"]');
ok(f2 && (/Falta/.test(f2.textContent) || f2.querySelector("svg[data-cancha]")), "mapa de zonas: se pinta o declara el parquet");

/* 8. interacción */
try {
  click(document.querySelector('[data-fig="fig3"] [data-seg] button[data-k="ambos"]'));
  const c = document.querySelectorAll('[data-fig="fig3"] circle[data-lleno]');
  ok(c.length >= 6 && [...c].some(x => x.dataset.lleno === "0"), `«los dos» dibuja corregido y crudo (${c.length})`);
} catch (e) { ok(false, "segmentado fig3: " + e.message); }
try {
  click(document.querySelector('[data-fig="fig4"] button[data-k="xg"]'));
  ok(/percentil|parcial/.test(document.querySelector('[data-fig="fig4"]').innerHTML), "fig4 cambia de métrica");
} catch (e) { ok(false, "fig4: " + e.message); }
try {
  const it = document.querySelectorAll('[data-fig="roles"] [data-jug]')[2];
  click(it);
  ok(document.querySelectorAll('[data-fig="roles"] .item.on')[0].dataset.jug === it.dataset.jug,
    "tocar un jugador cambia el mapa");
} catch (e) { ok(false, "roles: " + e.message); }
try {
  click(document.querySelector('[data-fig="fig6"] button[data-k="n80"]'));
  ok(/N80 =/.test(document.querySelector('[data-fig="fig6"]').innerHTML), "fig6 pasa a N80");
} catch (e) { ok(false, "fig6: " + e.message); }
if (modo === "completo") try {
  click(document.querySelector('[data-fig="fig5"] button[data-k="Santiago Solari"]'));
  ok(document.querySelectorAll('[data-fig="fig5"] svg[data-bosque]').length === 4, "fig5 cambia de técnico");
} catch (e) { ok(false, "fig5: " + e.message); }
const tip = document.getElementById("tip");
click(document.querySelector("#informe .cf"));
ok(tip.classList.contains("fijo") && /fuente/.test(tip.innerHTML), "tocar una cifra fija su fuente");

/* 9. cierre y huecos */
if (modo === "completo") {
  const pts = document.querySelectorAll('[data-fig="fig9"] .pto');
  ok(pts.length >= 20, `marcador con ${pts.length} predicciones`);
  ok(document.querySelectorAll('[data-fig="fig9"] .pto.no').length > 0, "los fallos se ven");
  const f9 = D.cierre.flatMap(x => x.bloques || []).find(b => b.id === "fig9");
  const nNE = f9 ? f9.datos.filter(p => p.cumple === null || p.cumple === undefined).length : 0;
  ok(document.querySelectorAll('[data-fig="fig9"] .pto.ne').length === nNE, `las no evaluables se ven punteadas (${nNE})`);
  ok(/ADR-60/.test(document.getElementById("c-1").textContent), "el cierre cuenta las predicciones de ADR-60");
  ok(document.querySelector("#c-3 [data-pendiente]"), "anexo de errores declarado como pendiente");
}
if (modo === "sin_contexto") {
  const s26 = document.getElementById("a2-6");
  ok(/contexto_v1\.json/.test(s26.textContent) && s26.querySelector("code"), "2.6 muestra el comando que falta");
  ok(document.getElementById("a3-4").querySelector(".vacio"), "3.4 también declara el hueco (usa contexto)");
  ok(document.getElementById("c-1").querySelector(".vacio"), "el cierre también (marcador)");
  ok(document.getElementById("a2-1").querySelectorAll(".fr").length >= 1, "el resto se pinta igual");
  ok(/falta/.test(document.getElementById("traza").textContent), "la huella marca el JSON ausente");
}

/* 10. legibilidad */
const chicos = [...document.querySelectorAll("#informe svg text")].filter(t => {
  const f = parseFloat(t.getAttribute("font-size") || "12"); return f < 10; });
ok(chicos.length === 0, `sin texto SVG por debajo de 10px (${chicos.length})`);

console.log(fallos ? `\n${fallos} FALLAS` : "\nhumo en verde");
process.exit(fallos ? 1 : 0);
