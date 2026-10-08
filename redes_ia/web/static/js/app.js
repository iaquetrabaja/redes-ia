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

// Competencia: «Comprobar» lee la página pública de la cuenta antes de añadirla y enseña lo que encuentra
// (o qué falla y qué hacer). Al pulsar «Añadir» se vuelve a comprobar en el servidor.
(function () {
  const form = document.querySelector("form[data-comprobar]"); if (!form) return;
  const boton = form.querySelector("[data-boton-comprobar]"), caja = form.querySelector("[data-resultado]");
  const esc = t => String(t == null ? "" : t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const miles = n => n == null ? "—" : Number(n).toLocaleString("es-ES");
  boton.addEventListener("click", async () => {
    const red = form.red.value, usuario = form.usuario.value.trim();
    if (!usuario) { form.usuario.focus(); return; }
    caja.hidden = false; caja.className = "comprobacion"; boton.disabled = true;
    caja.innerHTML = "Leyendo la página pública de la cuenta… (unos segundos; si TikTok va lento, hasta medio minuto)";
    try {
      const r = await fetch((window.B || "") + "/api/comprobar?red=" + encodeURIComponent(red) + "&usuario=" + encodeURIComponent(usuario)).then(x => x.json());
      caja.className = "comprobacion " + (r.ok ? (r.tipo === "ok" ? "bien" : "aviso") : "mal");
      let h = "<b>" + esc(r.mensaje) + "</b>";
      if (r.que_hacer) h += "<p>" + esc(r.que_hacer) + "</p>";
      if (r.ok && r.seguidores != null) h += "<p>" + esc(r.nombre || "") + " · " + miles(r.seguidores) + " seguidores</p>";
      if (r.videos && r.videos.length) {
        h += "<ul>" + r.videos.map(v => "<li><span>" + esc((v.texto || "(sin texto)").slice(0, 80)) + "</span> <small>" +
          miles(v.vistas) + " vistas" + (v.publicado ? " · " + esc(v.publicado.slice(0, 10)) : "") + "</small></li>").join("") + "</ul>";
      }
      if (r.ok) h += "<p class='hint'>Todo bien: pulsa «Añadir».</p>";
      caja.innerHTML = h;
    } catch (e) {
      caja.className = "comprobacion mal";
      caja.innerHTML = "<b>No se pudo comprobar.</b><p>¿Sigue abierta la ventana negra de Redes IA? Vuelve a intentarlo.</p>";
    }
    boton.disabled = false;
  });
  form.addEventListener("submit", () => { const b = form.querySelector("button:not([type=button])"); b.disabled = true; b.textContent = "Comprobando…"; });
})();
