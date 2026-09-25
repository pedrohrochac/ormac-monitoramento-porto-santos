# -*- coding: utf-8 -*-
"""Servidor local do painel.

    python servidor.py

Faz tres coisas:

  1. serve o painel em http://localhost:8777 (porta em config.PORTA_SERVIDOR)
  2. recoleta sozinho a cada config.INTERVALO_COLETA_MINUTOS (hoje: 120)
  3. atende o botao "Atualizar agora" da propria pagina

Enquanto esta rodando, voce nao precisa de cron nem do Agendador de Tarefas.
Feche o terminal e o robo para. Para a versao que sobrevive a reinicializacao,
use o instalar_agendamento.py.
"""

from __future__ import annotations

import http.server
import json
import socketserver
import threading
import time
import webbrowser
from datetime import datetime

import armazenamento as bd
import config
import main as coletor
import painel

_TRAVA = threading.Lock()
_ESTADO = {"coletando": False, "ultima": None, "avisos": []}


def coletar(so_cambio: bool = False) -> dict:
    """Uma coleta completa. Protegida por trava: nunca duas ao mesmo tempo."""
    if not _TRAVA.acquire(blocking=False):
        return {"ok": False, "erro": "já existe uma coleta em andamento"}
    _ESTADO["coletando"] = True
    try:
        con = bd.conectar()
        avisos = []
        try:
            if not so_cambio:
                avisos += coletor._coletar_navios(con)
            avisos += coletor._coletar_cambio(con)
            bd.registrar_coleta(con, "cambio" if so_cambio else "completa",
                                "; ".join(avisos))
            con.commit()
            painel.gravar(con, avisos, com_servidor=True)
        finally:
            con.close()
        _ESTADO["ultima"] = datetime.now()
        _ESTADO["avisos"] = avisos
        return {"ok": True, "avisos": avisos,
                "momento": _ESTADO["ultima"].strftime("%d/%m/%Y %H:%M:%S")}
    except Exception as erro:                            # noqa: BLE001
        return {"ok": False, "erro": "%s: %s" % (type(erro).__name__, erro)}
    finally:
        _ESTADO["coletando"] = False
        _TRAVA.release()


def _laco():
    """Recoleta a cada intervalo, para sempre, numa thread de fundo."""
    intervalo = config.INTERVALO_COLETA_MINUTOS * 60
    while True:
        time.sleep(intervalo)
        print("[%s] coleta automática" % datetime.now().strftime("%H:%M:%S"))
        resultado = coletar()
        if not resultado["ok"]:
            print("  falhou: %s" % resultado.get("erro"))


class Alca(http.server.SimpleHTTPRequestHandler):
    def _json(self, codigo: int, corpo: dict) -> None:
        dados = json.dumps(corpo).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_POST(self):                                   # noqa: N802
        if self.path.rstrip("/") == "/atualizar":
            resultado = coletar()
            self._json(200 if resultado["ok"] else 503, resultado)
            return
        self.send_error(404)

    def do_GET(self):                                    # noqa: N802
        caminho = self.path.split("?")[0].rstrip("/")
        if caminho in ("", "/painel", "/index.html"):
            self.path = "/" + config.ARQUIVO_PAINEL
        elif caminho == "/estado":
            self._json(200, {
                "coletando": _ESTADO["coletando"],
                "ultima": (_ESTADO["ultima"].isoformat(sep=" ", timespec="seconds")
                           if _ESTADO["ultima"] else None),
                "avisos": _ESTADO["avisos"],
            })
            return
        return super().do_GET()

    def log_message(self, formato, *args):               # noqa: A003
        if "/atualizar" in (args[0] if args else ""):
            super().log_message(formato, *args)


class Servidor(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> int:
    print("Monitor Porto de Santos — servidor local")
    print("Coleta automática a cada %d minutos." % config.INTERVALO_COLETA_MINUTOS)
    print("Coletando agora, antes de abrir...")
    resultado = coletar()
    if resultado["ok"]:
        print("  pronto. %d aviso(s)." % len(resultado.get("avisos", [])))
        for aviso in resultado.get("avisos", []):
            print("  - %s" % aviso)
    else:
        print("  falhou: %s" % resultado.get("erro"))
        print("  o painel antigo continua no ar, se existir.")

    threading.Thread(target=_laco, daemon=True).start()

    endereco = "http://localhost:%d/" % config.PORTA_SERVIDOR
    with Servidor(("127.0.0.1", config.PORTA_SERVIDOR), Alca) as servidor:
        print("\nPainel em %s" % endereco)
        print("Ctrl+C para parar.\n")
        try:
            webbrowser.open(endereco)
        except Exception:                                # noqa: BLE001
            pass
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            print("\nParado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
