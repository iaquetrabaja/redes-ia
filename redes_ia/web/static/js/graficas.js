// Gráficas de Resumen y de la ficha de cada cuenta (Chart.js incluido en static/vendor: funciona sin internet).
// Cada <canvas data-grafica="clave"> pinta las series de #datos-grafica[clave]: {nombre: [[fecha, valor], …]}.
(function () {
  "use strict";
  const src = document.getElementById("datos-grafica");
  if (!src || typeof Chart === "undefined") return;
  const datos = JSON.parse(src.textContent);
  const letra = getComputedStyle(document.body).fontFamily;
  Chart.defaults.font.family = letra;
  const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const oscuro = getComputedStyle(document.documentElement).colorScheme === "dark";
  // cada red siempre del mismo color: TikTok en tinta, Instagram en acento, YouTube en azul
  const RED = { TikTok: css("--text"), Instagram: css("--accent"), YouTube: oscuro ? "#6aa6d6" : "#2f6f9f" };
  const PAL = oscuro ? ["#ef6a3a", "#ededea", "#6aa6d6", "#8f8f8a", "#d2a94a"] : ["#d24d1e", "#141414", "#2f6f9f", "#7d7d78", "#a37b1f"];
  const color = (nombre, i) => RED[nombre.split(" ")[0]] || PAL[i % PAL.length];
  const corto = v => {
    const a = Math.abs(v);
    if (a >= 1e6) return (v / 1e6).toFixed(1).replace(/\.0$/, "").replace(".", ",") + " M";
    if (a >= 1e4) return (v / 1e3).toFixed(1).replace(/\.0$/, "").replace(".", ",") + " mil";
    return Number(v).toLocaleString("es-ES");
  };
  const fecha = f => f.slice(5).split("-").reverse().join("/");

  function opciones(apilado) {
    const linea = css("--border"), texto = css("--text-2"), font = { family: letra, size: 11 };
    return {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: texto, boxWidth: 10, boxHeight: 10, font: { family: letra, size: 12 } } },
        tooltip: { backgroundColor: css("--text"), titleColor: css("--bg"), bodyColor: css("--bg"), padding: 10, cornerRadius: 4,
          callbacks: { label: c => " " + c.dataset.label + ": " + (c.raw == null ? "—" : Number(c.raw).toLocaleString("es-ES")) } }
      },
      scales: {
        x: { stacked: apilado, grid: { display: false }, ticks: { color: texto, maxRotation: 0, autoSkip: true, maxTicksLimit: 10, font }, border: { color: linea } },
        y: { stacked: apilado, grid: { color: linea }, ticks: { color: texto, font, callback: corto }, border: { display: false } }
      }
    };
  }

  document.querySelectorAll("canvas[data-grafica]").forEach(el => {
    const series = Object.entries(datos[el.dataset.grafica] || {}).filter(([, p]) => p.some(x => x[1]));
    const barras = el.dataset.tipo === "barras";
    if (!series.length || (!barras && series.every(([, p]) => p.length < 2))) {
      const caja = el.closest(".chart-box");
      if (caja) caja.hidden = true;
      const aviso = el.closest(".card") && el.closest(".card").querySelector(".grafica-vacia");
      if (aviso) aviso.hidden = false;
      return;
    }
    const fechas = Array.from(new Set(series.flatMap(([, p]) => p.map(x => x[0])))).sort();
    new Chart(el, {
      type: barras ? "bar" : "line",
      data: {
        labels: fechas.map(fecha),
        datasets: series.map(([nombre, p], i) => {
          const m = Object.fromEntries(p);
          const c = color(nombre, i);
          return { label: nombre, data: fechas.map(f => m[f] ?? null), borderColor: c, backgroundColor: c,
            borderWidth: 1.75, pointRadius: fechas.length < 12 ? 2.5 : 0, pointHoverRadius: 3, tension: 0.25,
            spanGaps: true, borderRadius: 2, maxBarThickness: 22 };
        })
      },
      options: opciones(barras)
    });
  });
})();
