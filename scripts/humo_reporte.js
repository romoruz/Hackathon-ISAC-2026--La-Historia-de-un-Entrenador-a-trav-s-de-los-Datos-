/* Ejecuta reporte_demo.html en un DOM real y comprueba que se pinta.
   Cualquier excepcion dentro de render() -- una clave que no existe, una
   funcion renombrada a medias -- aparece aqui y no en la defensa. */
const fs = require("fs");
const { JSDOM } = require("jsdom");

const errores = [];
const dom = new JSDOM(fs.readFileSync("reporte_demo.html", "utf8"), {
  runScripts: "dangerously",
  pretendToBeVisual: true,
  virtualConsole: new (require("jsdom").VirtualConsole)()
    .on("jsdomError", e => errores.push(e.message))
    .on("error", (...m) => errores.push(m.map(x => (x && x.stack) ? x.stack.split("\n").slice(0,4).join(" || ") : String(x)).join(" "))),
});

const { document } = dom.window;
if (errores.length) {
  console.error(errores.join("\n"));
  process.exit(1);
}

let fallos = 0;
const ok = (cond, msg) => {
  console.log((cond ? "  ok   " : "  FALLA") + "  " + msg);
  if (!cond) fallos++;
};

/* --- las cinco secciones tienen contenido --- */
["s0", "s1", "s2", "s3", "s4"].forEach(id => {
  const n = document.getElementById(id);
  ok(n && n.innerHTML.trim().length > 400, `sección ${id} pintada`);
});

/* --- canchas del MISMO tamaño: el bug que se estaba arreglando --- */
/* Dos canchas hermanas dentro de una `.par` deben compartir viewBox. Si una
   figura vuelve a traer su propio ancho, esto salta. */
const pares = [...document.querySelectorAll(".grid.par")];
ok(pares.length >= 2, `rejillas de comparación .par encontradas: ${pares.length}`);
pares.forEach((g, i) => {
  const vb = [...g.querySelectorAll("svg")].map(s => s.getAttribute("viewBox"));
  ok(vb.length === 2 && vb[0] === vb[1],
    `par ${i + 1}: dos canchas con el mismo viewBox (${vb.join(" | ")})`);
});

/* --- ninguna cancha comparada usa un ancho antiguo --- */
const anchos = new Set([...document.querySelectorAll(".par svg")]
  .map(s => s.getAttribute("viewBox")));
ok(anchos.size === 1, `un único tamaño de cancha comparada: ${[...anchos]}`);

/* --- los colores azul/rojo cableados desaparecieron --- */
const h = document.documentElement.innerHTML;
["#4aa8ff", "#ff5470", "#8b8b93"].forEach(c =>
  ok(!h.includes(c), `color cableado ${c} eliminado`));

/* --- el rival se pinta en plata, el foco en color de club --- */
ok(h.includes("var(--riv)"), "el rival usa el token --riv");
ok(h.includes("var(--a1)"), "el foco usa el color del club");

/* --- toda figura comparada lleva leyenda --- */
ok(document.querySelectorAll(".leyenda").length >= 4,
  `leyendas presentes: ${document.querySelectorAll(".leyenda").length}`);
ok(document.querySelectorAll(".mapcap").length >= 4,
  `canchas rotuladas con nombre y color: ${document.querySelectorAll(".mapcap").length}`);

/* --- la guía de lectura existe y está abierta --- */
const g = document.getElementById("guia");
ok(g && g.open, "guía de lectura visible al abrir");
ok(document.querySelectorAll("#guia .paso").length === 5, "cinco pasos en la guía");

/* --- nada de texto por debajo del umbral legible --- */
const chicos = [...document.querySelectorAll("[style]")]
  .map(e => e.getAttribute("style"))
  .filter(v => /font-size:\.(6[0-9]|7[0-1])rem/.test(v));
ok(chicos.length === 0,
  `sin texto en estilo EN LÍNEA por debajo de .72rem (${chicos.length})`);
const svgChico = [...document.querySelectorAll("svg text")]
  .map(t => parseFloat(t.getAttribute("font-size") || "99"))
  .filter(v => v < 10);
ok(svgChico.length === 0, `sin texto SVG por debajo de 10px (${svgChico.length})`);

/* --- cambiar de club y de técnico no rompe nada --- */
const sel = document.getElementById("selClub");
sel.value = "Cruz Azul";
try {
  dom.window.cambiaClub();
  ok(true, "cambio de club sin excepción");
} catch (e) { ok(false, "cambio de club: " + e.message); }

const dt = document.getElementById("selDT");
dt.value = dt.options[dt.options.length - 1].value;
try {
  dom.window.cambiaDT();
  ok(true, "cambio de técnico sin excepción");
} catch (e) { ok(false, "cambio de técnico: " + e.message); }

try {
  document.getElementById("swap").onclick();
  ok(true, "intercambio de técnicos sin excepción");
} catch (e) { ok(false, "swap: " + e.message); }

/* --- clic en un jugador repinta sus mapas (la sección de la captura) --- */
const jug = document.querySelector("[data-jug]");
if (jug) {
  try {
    jug.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
    ok(document.getElementById("mapas").innerHTML.includes("svg"),
      "clic en jugador repinta sus dos canchas");
  } catch (e) { ok(false, "clic en jugador: " + e.message); }
}

/* --- la seccion 06 se pinta y el simulador FUNCIONA --- */
/* No basta con que no lance: hay que comprobar que simular cambia el marcador,
   que las probabilidades son coherentes y que el balon recorre la cancha. */
/* El tablero vive AHORA en la seccion 02, no en una 06 aparte. */
ok(!document.getElementById("s5"), "la sección 06 ya no existe");
ok(/La tabla que hay detrás/.test(document.getElementById("s1").innerHTML),
  "el tablero está dentro de la sección 02");
ok(!document.getElementById("histo"), "el histograma de longitudes se retiró");
/* La nula salio del tablero por peticion: era auditoria, no futbol. Sigue
   viva en 03_METHODS §4.3 y en los IC de cada titular. */
ok(!document.querySelector("#s1 details"), "el bloque de la nula ya no está en el tablero");
ok(!!document.getElementById("cancha"), "cancha del simulador presente");


/* --- DOS CANCHAS lado a lado --- */
ok(!!document.getElementById("canchaA") && !!document.getElementById("canchaB"),
  "las dos canchas están presentes");
const cA = document.querySelectorAll("#canchaA [data-z]");
ok(cA.length === 20, `las 20 casillas son tocables (${cA.length})`);

/* LOS PORCENTAJES DEBEN SUMAR 100 EXACTO. Redondear cada casilla por separado
   acumulaba +-2 puntos sobre 20 casillas, y eso mina la confianza en la matriz
   aunque la matriz este bien. */
const pcts = [...document.querySelectorAll("#canchaA text")]
  .map(t => parseInt(t.textContent, 10)).filter(v => !isNaN(v));
const suma = pcts.reduce((a, b) => a + b, 0);
ok(pcts.length === 20 && suma === 100,
  `los porcentajes de las casillas suman 100 exacto (${suma} en ${pcts.length})`);

cA[7].dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
ok(document.querySelectorAll("#canchaA path[marker-end]").length > 0,
  "tocar una casilla dibuja flechas");
ok(document.querySelectorAll("#canchaB path[marker-end]").length > 0,
  "la cancha de comparación dibuja las suyas a la vez");
ok(/sigue jugando/i.test(document.getElementById("panel").innerHTML),
  "el panel compara las dos");
ok(/gol|remate/i.test(document.getElementById("panel").innerHTML),
  "el desglose nombra los desenlaces");
ok(!document.querySelector("#s1 details"), "el bloque de la nula ya no está");
/* El desglose por zona se indexa por VALOR de estado; `fin` tambien. Si uno de
   los dos usara la POSICION, las etiquetas saldrian cambiadas en cuanto una era
   no visite alguna combinacion zona x fase — sin fallar. */
ok(!/>\?</.test(document.getElementById("panel").innerHTML),
  "ningún desenlace queda sin nombre");

/* --- REFERENCIA DE LOS RIVALES en el grafico de puntos --- */
const s3h = document.getElementById("s3").innerHTML;
ok(/LOS RIVALES/.test(s3h), "la referencia de los rivales se pinta en el gráfico");
/* Cuando cae fuera del rango de los tecnicos, se marca en el margen con la
   direccion, no se recorta al borde como si fuera un valor mas ni se estiran
   los ejes (comprimiria a los tecnicos en una esquina). */
ok(/fuera<\/text>|LOS RIVALES<\/text>/.test(s3h),
  "la referencia se marca dentro o en el margen, según caiga");
ok(/están por encima|Sobre la referencia/.test(s3h),
  "la nota explica dónde queda la referencia respecto a los técnicos");
/* La etiqueta NO puede decir «la liga»: son posesiones jugadas CONTRA este
   club, contaminadas por como juega el (02_STATE_OF_PLAY §7.1). */
ok(/No es el promedio de la Liga MX/.test(s3h),
  "la nota aclara que no es el promedio de la liga");
ok(!/promedio de la liga mx</i.test(s3h.replace(/No es el promedio de la Liga MX/g, "")),
  "en ningún otro sitio se llama «la liga» a esa referencia");

/* --- MAPA DE PELIGRO (lift de ruta) --- */
const btnMod = [...document.querySelectorAll("#modoMapa button")];
ok(btnMod.length === 3, `tres modos de mapa (${btnMod.length})`);
ok(btnMod[0].classList.contains("on"), "arranca en «dónde vive», no en el lift");

btnMod.find(b => b.dataset.m === "REMATE").onclick();
const txtR = [...document.querySelectorAll("#canchaA text")].map(x => x.textContent);
ok(txtR.some(x => /×$/.test(x)), "las casillas muestran el cociente con ×");
/* Las zonas sin soporte van VACIAS: pintarlas tenues se leeria como «poco»,
   cuando lo correcto es «no lo sabemos». */
ok(txtR.filter(x => /×$/.test(x)).length === 18,
  `las 2 zonas sin soporte quedan vacías (${txtR.filter(x => /×$/.test(x)).length} con dato)`);
ok(/no es causal/i.test(document.getElementById("leyMapa").innerHTML),
  "el caveat de causalidad va impreso, no plegado");

/* EL RECORTE DE LA ESCALA. El centro del area da ~4x para cualquier tecnico y
   se comia toda la rampa: los dos mapas salian identicos. Con el techo en 2.5x
   esas casillas saturan y el contraste se va a las zonas intermedias, que es
   donde esta la firma tactica. */
/* Por `data-z`, no por posicion: el SVG trae otros rect antes de las casillas
   y el indice no coincide con el de zona. */
const alfaZ = z => parseFloat(
  document.querySelector(`#canchaA [data-z="${z}"] rect`).getAttribute("fill-opacity"));
ok(Math.abs(alfaZ(9) - alfaZ(10)) < 1e-6,
  `las casillas de 3.98× y 4.10× saturan igual (${alfaZ(9)} vs ${alfaZ(10)})`);
ok(alfaZ(1) < alfaZ(9) - 0.02,
  `la banda de 1.96× queda por debajo del techo (${alfaZ(1)} < ${alfaZ(9)})`);
ok(alfaZ(2) < alfaZ(1) - 0.02,
  `1.30× y 1.96× se distinguen entre sí (${alfaZ(2)} < ${alfaZ(1)})`);
/* El NUMERO impreso no se toca: solo cambia el color. */
ok([...document.querySelectorAll("#canchaA text")].some(x => /3\.98×/.test(x.textContent)),
  "el número impreso sigue siendo el lift real, no el recortado");
ok(/satura en 2\.5×/.test(document.getElementById("leyMapa").innerHTML),
  "el recorte se declara en la leyenda");
ok(!document.querySelector("#canchaA path[marker-end]"),
  "en modo peligro no se dibujan flechas de transición");

/* La puerta del modo GOL: se desactiva DICIENDO por que y con el n real. */
btnMod.find(b => b.dataset.m === "GOL").onclick();
const tm = document.getElementById("tituloMapa").innerHTML;
ok(/muestra suficiente/i.test(tm) && /22/.test(tm),
  "el modo gol se bloquea explicando el motivo y con el n real");
btnMod[0].onclick();

/* --- SECCION 03 CON CERO CAMBIOS --- */
/* El caso que fallaba: con 0 de N, `lista` iba vacia y la seccion no pintaba
   nada. El lector veia «0/12» y una pantalla en blanco.
   Se lee del DOM, no de DATOS, porque es lo que ve el usuario. */
{
 const s2 = document.getElementById("s2").innerHTML;
 const m = s2.match(/data-num="(\d+)"[^>]*>0<\/span><span[^>]*>\/(\d+)</);
 if (m) {
  const cambian = +m[1], total = +m[2];
  ok(/data-jug=/.test(s2),
    `la lista de futbolistas se pinta (cambian ${cambian}/${total})`);
  ok(cambian === 0 ? /Ninguno supera ese umbral/.test(s2)
                   : /cruzan el umbral/.test(s2),
    cambian === 0 ? "con cero cambios se dice que el orden es solo descriptivo"
                  : "con cambios se explica qué marca el punto");
 } else {
  ok(false, "no encuentro la tarjeta «cambiaron su juego» en la sección 03");
 }
}

/* --- «EL CLUB, SIN ÉL» EN EL SELECTOR DE ARRIBA --- */
ok([...document.getElementById("selRival").options].some(o => o.value === "__CLUB__"),
  "«el club, sin él» está en el selector de arriba");

/* --- SIMULADOR --- */
document.getElementById("b1").onclick();
ok(document.querySelectorAll("#cancha circle.bola").length === 1,
  "la ficha del balón aparece al animar una jugada");
/* La tira debe decir el TIPO de accion, no solo la zona: el espacio de estados
   es (zona x fase) y el tipo estaba oculto. */
ok(/pase|conducción|remate/i.test(document.getElementById("tira").innerHTML),
  "la tira dice qué tipo de acción fue cada salto");
ok(/juego abierto|transición|reinicio|balón parado/i.test(
   document.getElementById("relato").innerHTML),
  "el relato dice en qué fase nació la jugada");
ok(document.querySelectorAll("#tira .fx").length > 0,
  "la tira de fichas describe la jugada en palabras");
/* El calor tiene que ACUMULARSE: si cada corrida lo reiniciara, el mapa nunca
   se pintaria y la promesa de "la cancha se pinta sola" seria falsa. */
document.getElementById("b1000").onclick();
const P = document.getElementById("marcador").innerHTML;
ok(/DURACIÓN MEDIA/.test(P), "el marcador muestra la duración media");
/* Todo gol es un remate: P(gol) NUNCA puede superar P(remate). Si esto salta,
   el contador de desenlaces esta mal. */
const nums = [...P.matchAll(/>([\d.]+)%</g)].map(m => parseFloat(m[1]));
ok(nums.length >= 2 && nums[1] <= nums[0] + 1e-9,
  `P(gol)=${nums[1]}% <= P(remate)=${nums[0]}%`);
const op = [...document.querySelectorAll("#cancha rect")]
  .map(r => parseFloat(r.getAttribute("fill-opacity") || "0"));
ok(Math.max(...op) > 0.05, `el calor se acumula (max ${Math.max(...op).toFixed(2)})`);


/* --- MODO CLUB: cambia el selector y comprueba que degrada con explicacion --- */
const sr = document.getElementById("selRival");
sr.value = "__CLUB__";
try {
  dom.window.render();
  ok(/club, sin él/i.test(document.getElementById("s1").innerHTML),
    "al elegir «el club, sin él» el tablero lo refleja");
  ok(/dos etapas concretas/i.test(document.getElementById("s0").innerHTML),
    "las secciones de pareja explican por qué no aplican, en vez de romperse");
  ok(!!document.getElementById("canchaB"), "sigue habiendo cancha de comparación");
} catch (e) { ok(false, "modo club: " + e.message); }
sr.value = sr.options[1].value; dom.window.render();
document.getElementById("b1000").onclick();

document.getElementById("bR").onclick();
ok(/Pulsa/.test(document.getElementById("marcador").innerHTML),
  "reiniciar devuelve el marcador a su estado inicial");

if (errores.length) { console.error(errores.join("\n")); fallos++; }
console.log(fallos ? `\n${fallos} FALLOS` : "\ntodo en verde");
process.exit(fallos ? 1 : 0);
