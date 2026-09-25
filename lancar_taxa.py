# -*- coding: utf-8 -*-
"""Lancamento manual de taxa de agencia.

    python lancar_taxa.py Maersk USD 5,42
    python lancar_taxa.py --listar
    python lancar_taxa.py --listar Maersk
"""

from __future__ import annotations

import sys

import armazenamento as bd
import config
import painel


def _para_float(texto: str) -> float:
    texto = texto.strip().replace("R$", "").strip()
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    return float(texto)


def listar(filtro: str | None = None) -> int:
    con = bd.conectar()
    try:
        if filtro:
            cursor = con.execute(
                "SELECT momento, origem, moeda, valor, tipo FROM cambio"
                " WHERE origem LIKE ? ORDER BY momento DESC LIMIT 60",
                ("%%%s%%" % filtro,))
        else:
            cursor = con.execute(
                "SELECT momento, origem, moeda, valor, tipo FROM cambio"
                " WHERE origem <> 'PTAX' ORDER BY momento DESC LIMIT 60")
        linhas = cursor.fetchall()
    finally:
        con.close()

    if not linhas:
        print("Nenhuma taxa registrada ainda.")
        return 0

    print("%-19s  %-22s  %-5s  %-9s  %s"
          % ("Quando", "Origem", "Moeda", "Valor", "Tipo"))
    for l in linhas:
        print("%-19s  %-22s  %-5s  %9.4f  %s"
              % (l["momento"], l["origem"][:22], l["moeda"], l["valor"], l["tipo"]))
    return 0


def lancar(agencia: str, moeda: str, valor: str) -> int:
    moeda = moeda.upper()
    if moeda not in config.MOEDAS:
        print("Moeda '%s' fora da lista %s (ajuste config.MOEDAS)."
              % (moeda, ", ".join(config.MOEDAS)))
        return 2
    try:
        numero = _para_float(valor)
    except ValueError:
        print("Valor '%s' não parece um número. Use 5,42 ou 5.42." % valor)
        return 2

    con = bd.conectar()
    try:
        bd.gravar_cambio(con, agencia, "manual", moeda, numero)
        con.commit()
        caminho = painel.gravar(con)
    finally:
        con.close()

    print("%s %s = %.4f registrado." % (agencia, moeda, numero))
    print("painel: %s" % caminho)
    return 0


def main(argumentos: list[str]) -> int:
    if not argumentos or argumentos[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argumentos[0] == "--listar":
        return listar(argumentos[1] if len(argumentos) > 1 else None)
    if len(argumentos) < 3:
        print(__doc__)
        return 2
    return lancar(argumentos[0], argumentos[1], argumentos[2])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
