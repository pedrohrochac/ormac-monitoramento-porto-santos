# -*- coding: utf-8 -*-
"""Coleta completa, ou --cambio para so o cambio.

    python main.py             navios + cambio + painel
    python main.py --cambio    so dolar/euro/libra + painel
"""

from __future__ import annotations

import sys
from datetime import datetime

import armazenamento as bd
import coleta_cambio
import coleta_navios
import config
import painel
from historico import reconciliar


def _coletar_cambio(con) -> list[str]:
    avisos = []

    oficiais = coleta_cambio.ler_ptax_todas()
    for moeda, cotacao in oficiais.items():
        if "erro" in cotacao:
            avisos.append("PTAX %s: %s" % (moeda, cotacao["erro"]))
            continue
        rotulo = cotacao.get("boletim", "")
        bruto = (cotacao.get("momento") or "")[:16]
        if len(bruto) == 16:
            rotulo = ("%s %s/%s %s" % (rotulo, bruto[8:10], bruto[5:7],
                                       bruto[11:16])).strip()
        bd.gravar_cambio(con, "PTAX", "oficial", moeda, cotacao["venda"],
                         extra=rotulo)
        print("  PTAX %s  %.4f  (%s)" % (moeda, cotacao["venda"],
                                         cotacao.get("boletim", "")))

    for agencia, leitura in coleta_cambio.ler_agencias().items():
        if "erro" in leitura:
            avisos.append("Agência %s: %s" % (agencia, leitura["erro"]))
            continue
        for moeda in config.MOEDAS:
            if moeda in leitura:
                bd.gravar_cambio(con, agencia, "auto", moeda, leitura[moeda],
                                 extra=leitura.get("_data", ""))
                print("  %s %s  %.4f" % (agencia, moeda, leitura[moeda]))

    con.commit()
    return avisos


def _coletar_navios(con) -> list[str]:
    avisos = []
    resultado = coleta_navios.coletar()

    for nome, bloco in resultado.items():
        rotulo = config.FONTES[nome]["rotulo"]
        if not bloco["ok"]:
            avisos.append("%s: %s" % (rotulo, bloco["erro"]))
            print("  [falhou] %s -> %s" % (rotulo, bloco["erro"]))
        else:
            print("  [ok] %-28s %4d linhas" % (rotulo, len(bloco["dados"])))

    esperados = (resultado.get("esperados_carga", {}).get("dados", [])
                 + resultado.get("esperados_passageiros", {}).get("dados", []))
    if esperados:
        bd.gravar_esperados(con, esperados)

    fundeados = resultado.get("fundeados", {}).get("dados", [])
    if fundeados or resultado.get("fundeados", {}).get("ok"):
        bd.gravar_fundeados(con, fundeados)

    programados = resultado.get("programados", {}).get("dados", [])
    if programados:
        bd.gravar_programados(con, programados)

    con.commit()

    bloco_atracados = resultado.get("atracados", {})
    if bloco_atracados.get("ok"):
        numeros = reconciliar(con, bloco_atracados["dados"], datetime.now())
        print("  no cais: %d   escalas novas: %d   encerradas: %d"
              % (numeros["no_cais"], numeros["novas"], numeros["fechadas"]))
    else:
        avisos.append("Sem a lista de atracados, as escalas não foram atualizadas "
                      "nesta rodada.")

    return avisos


def main(argumentos: list[str]) -> int:
    so_cambio = "--cambio" in argumentos
    inicio = datetime.now()
    print("%s  %s" % (inicio.strftime("%d/%m/%Y %H:%M:%S"),
                      "câmbio" if so_cambio else "coleta completa"))

    con = bd.conectar()
    avisos: list[str] = []
    try:
        if not so_cambio:
            print("navios:")
            avisos += _coletar_navios(con)
        print("câmbio:")
        avisos += _coletar_cambio(con)

        bd.registrar_coleta(con, "cambio" if so_cambio else "completa",
                            "; ".join(avisos))
        con.commit()

        caminho = painel.gravar(con, avisos)
        print("painel: %s" % caminho)
    finally:
        con.close()

    if avisos:
        print("avisos:")
        for aviso in avisos:
            print("  - %s" % aviso)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
