"""Arranque: python -m redes_ia [--demo] [--puerto 8765] [--sin-navegador]"""
import argparse
import logging
import os
import threading
import time
import webbrowser


def main():
    ap = argparse.ArgumentParser(prog="redes_ia", description="Redes IA: panel local de contenido para TikTok e Instagram")
    ap.add_argument("--demo", action="store_true", help="datos de ejemplo (en datos/demo), sin tocar los tuyos")
    ap.add_argument("--puerto", type=int, default=int(os.environ.get("REDES_IA_PUERTO", 8765)))
    ap.add_argument("--host", default=os.environ.get("REDES_IA_HOST", "127.0.0.1"),
                    help="por seguridad, solo 127.0.0.1 (en Docker se usa 0.0.0.0 dentro del contenedor)")
    ap.add_argument("--sin-navegador", action="store_true", help="no abrir el navegador al arrancar")
    args = ap.parse_args()

    if args.demo:
        from . import RAIZ
        os.environ["REDES_IA_DATOS"] = str(RAIZ / "datos" / "demo")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    from .db import iniciar
    iniciar()
    if args.demo:
        from .servicios import demo
        demo.cargar()

    import uvicorn
    url = f"http://127.0.0.1:{args.puerto}"
    print(f"\n  Redes IA está en marcha: abre {url}\n  Para cerrarlo, cierra esta ventana o pulsa Ctrl+C.\n")
    if not args.sin_navegador:
        threading.Thread(target=lambda: (time.sleep(1.5), webbrowser.open(url)), daemon=True).start()
    uvicorn.run("redes_ia.web.app:app", host=args.host, port=args.puerto, log_level="warning")


if __name__ == "__main__":
    main()
