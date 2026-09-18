/* Humo del informe H7 en un DOM real.  node scripts/humo_reporte.js pagina.html [completo|sin_contexto] */
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

ok(errores.length === 0, `sin excepciones al cargar (${errores.slice(0, 2).join(" | ")})`);

/* 1. estructura de ADR-59 §4 */
const secs = [...document.querySelectorAll("#informe > section")];
ok(secs.length === 10, `diez secciones (${secs.length})`);
ok(secs.map(s => s.id).join() === "s1,s2,s3,s4,s5,s6,s7,s8,s9,s10", "en el orden de ADR-59");
secs.forEach(s => ok(/componente/.test(s.querySelector(".eyebrow").textContent),
  `${s.id} declara el componente del reto`));
ok(document.querySelectorAll("#segSec button").length === 10, "índice con diez botones");

/* 2. nada externo (ADR-38) y nada del tablero viejo */
ok(!/<script[^>]+src=|<link[^>]+href=["']?http|@import/i.test(html), "sin dependencias externas");
["selRival", "selDT", "cancha", "canchaA", "tira"].forEach(id =>
  ok(!document.getElementById(id), `el tablero viejo no está (#${id})`));

/* 3. figuras de ADR-59 §5 */
const figs = ["fig1", "fig2", "fig3", "fig4", "fig5", "fig6", "fig7", "fig8", "fig9"];
figs.forEach(f => {
  const el = document.querySelector(`[data-fig="${f}"] .lienzo`);
  if (modo === "sin_contexto" && ["fig5", "fig8", "fig9"].includes(f))
    return ok(!el, `${f} ausente sin contexto (su sección lo declara)`);
  ok(el && el.innerHTML.trim().length > 40, `figura ${f} pintada`);
});

/* 4. niveles y fuentes */
const frases = [...document.querySelectorAll(".fr")];
ok(frases.length > 20, `frases con nivel: ${frases.length}`);
ok(frases.every(f => ["A", "B", "C"].includes(f.dataset.nivel)), "toda frase lleva A, B o C");
ok(frases.every(f => f.querySelectorAll(".nv").length === 1), "un solo nivel por frase");
const cifras = [...document.querySelectorAll(".cf")];
ok(cifras.length > 30 && cifras.every(c => c.dataset.f && c.dataset.f.length > 3),
  `toda cifra en el texto trae fuente (${cifras.length})`);
const nulos = frases.filter(f => f.classList.contains("nulo"));
ok(nulos.length >= 5, `nulos visibles (${nulos.length})`);
ok(nulos.every(f => /(mayor|menor) a|sobreviven a la correcci/.test(f.textContent)),
  "cada nulo dice su margen o su conteo tras corregir");
ok(frases.filter(f => f.dataset.nivel === "B").every(f => /\[/.test(f.textContent)),
  "toda frase B trae un intervalo");

/* 5. colores: un solo tono, sin colores cableados en figuras */
const lienzos = [...document.querySelectorAll(".lienzo")].map(l => l.innerHTML).join("");
["#ff453a", "#30d158", "#0a84ff", "#ffd60a", "#173f29"].forEach(c =>
  ok(!lienzos.includes(c), `sin color cableado ${c}`));
ok(/var\(--a1\)/.test(lienzos), "las figuras usan el token --a1");

/* 6. mapas: porcentajes que suman 100 */
const mapaRol = document.querySelector('[data-fig="roles"] svg[data-cancha]');
if (mapaRol) {
  const s = [...mapaRol.querySelectorAll("text.pctz")].map(t => parseInt(t.textContent));
  ok(s.length === 20 && s.reduce((a, b) => a + b, 0) === 100, `las 20 casillas suman 100 (${s.reduce((a, b) => a + b, 0)})`);
}
const f2 = document.querySelector('[data-fig="fig2"]');
const m2 = f2.querySelector("svg[data-cancha]");
if (m2) {
  const s2 = [...m2.querySelectorAll("text.pctz")].map(t => parseInt(t.textContent));
  ok(s2.length === 20 && s2.reduce((a, b) => a + b, 0) === 100, "mapa de zonas: 20 casillas que suman 100");
} else {
  ok(/Falta el parquet/.test(f2.textContent), "sin parquet, el mapa de zonas lo declara");
}

/* 7. interacción */
const click = el => el.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
try {
  const b = document.querySelector('[data-fig="fig3"] [data-seg] button[data-k="ambos"]');
  click(b);
  const c = document.querySelectorAll('[data-fig="fig3"] circle[data-lleno]');
  ok(c.length === 6, `«los dos» dibuja corregido y crudo (${c.length} marcas)`);
  ok([...c].some(x => x.dataset.lleno === "0"), "el crudo va como aro");
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
  ok(/torneo parcial|—/.test(document.body.innerHTML), "un torneo parcial se pinta sin romper");
} catch (e) { ok(false, "fig6: " + e.message); }
if (modo === "completo") try {
  click(document.querySelector('[data-fig="fig5"] button[data-k="Santiago Solari"]'));
  ok(document.querySelectorAll('[data-fig="fig5"] svg[data-bosque]').length === 4, "fig5 cambia de técnico");
} catch (e) { ok(false, "fig5: " + e.message); }
const tip = document.getElementById("tip");
click(document.querySelector(".cf"));
ok(tip.classList.contains("fijo") && /fuente/.test(tip.innerHTML), "tocar una cifra fija su fuente");

/* 8. marcador y huecos declarados */
if (modo === "completo") {
const pts = document.querySelectorAll('[data-fig="fig9"] .pto');
ok(pts.length >= 20, `marcador con ${pts.length} predicciones`);
ok(document.querySelectorAll('[data-fig="fig9"] .pto.no').length > 0, "los fallos se ven");
ok(/Pendiente/.test(document.querySelector('[data-fig="bugs"]').textContent), "anexo de errores declarado como pendiente");
}
if (modo === "sin_contexto") {
  const s5 = document.getElementById("s5");
  ok(/contexto_v1\.json/.test(s5.textContent) && s5.querySelector("code"), "s5 muestra el comando que falta");
  ok(document.getElementById("s8").querySelector(".vacio"), "s8 también declara el hueco (usa contexto)");
  ok(document.getElementById("s9").querySelector(".vacio"), "s9 también declara el hueco (marcador)");
  ok(document.getElementById("s2").querySelectorAll(".fr").length > 3, "el resto se pinta igual");
  ok(/falta/.test(document.getElementById("traza").textContent), "la huella marca el JSON ausente");
}

/* 9. legibilidad */
const chicos = [...document.querySelectorAll("#informe svg text")].filter(t => {
  const f = parseFloat(t.getAttribute("font-size") || "12"); return f < 10; });
ok(chicos.length === 0, `sin texto SVG por debajo de 10px (${chicos.length})`);

console.log(fallos ? `\n${fallos} FALLAS` : "\nhumo en verde");
process.exit(fallos ? 1 : 0);
