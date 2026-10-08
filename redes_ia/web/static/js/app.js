// Redes IA: pequeñas ayudas de la interfaz.
(function () {
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  // Avisos que se cierran solos
  $$(".flash").forEach(f => { f.addEventListener("click", () => f.remove()); setTimeout(() => f.remove(), 7000); });
  // Botones «Copiar»
  $$("[data-copy]").forEach(b => b.addEventListener("click", () => {
    const t = b.dataset.copy || (document.querySelector(b.dataset.copyFrom) || {}).innerText || "";
    navigator.clipboard.writeText(t).then(() => { const o = b.textContent; b.textContent = "Copiado"; setTimeout(() => b.textContent = o, 1300); });
  }));
  // Cambiar tema
  $$("[data-theme-toggle]").forEach(b => b.addEventListener("click", () => {
    const root = document.documentElement;
    const oscuro = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = oscuro ? "light" : "dark";
    try { localStorage.setItem("theme", root.dataset.theme); } catch (e) {}
  }));
  // Lista de modelos del proveedor elegido (Ajustes → IA)
  const sel = document.querySelector("[data-modelos]");
  if (sel) {
    const btn = document.querySelector("[data-cargar-modelos]");
    btn && btn.addEventListener("click", async () => {
      const prov = (document.querySelector("input[name=proveedor]:checked") || {}).value;
      btn.textContent = "Cargando…";
      const r = await fetch((window.B || "") + "/ajustes/modelos?proveedor=" + encodeURIComponent(prov)).then(x => x.json());
      btn.textContent = "Ver modelos disponibles";
      if (r.error) { alert(r.error); return; }
      const dl = document.getElementById("lista-modelos");
      dl.innerHTML = r.modelos.map(m => `<option value="${m}">`).join("");
      sel.focus();
    });
  }
  // Si hay tareas en marcha, se recarga sola cuando terminan
  const viva = document.querySelector("[data-en-marcha]");
  if (viva) {
    const t = setInterval(async () => {
      try {
        const r = await fetch((window.B || "") + "/api/estado").then(x => x.json());
        if (!r.en_marcha.length) { clearInterval(t); location.reload(); }
      } catch (e) {}
    }, 5000);
  }
})();

// El recuadro «¿Qué es esto?» va justo debajo del título (o de las pestañas, si las hay).
(function () {
  var e = document.querySelector("details.explica"); if (!e) return;
  var ancla = document.querySelector(".main .tabs") || document.querySelector(".main .page-head");
  if (ancla) ancla.after(e);
})();
