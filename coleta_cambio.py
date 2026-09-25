# -*- coding: utf-8 -*-
"""PTAX do Banco Central nas tres moedas + leitores das agencias."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

import config


# ----------------------------------------------------------------------- PTAX

def ler_ptax(moeda: str) -> dict | None:
    """Ultima cotacao publicada. O BC usa datas no formato MM-DD-AAAA."""
    fim = datetime.now()
    ini = fim - timedelta(days=10)
    url = config.PTAX_URL.format(
        moeda=moeda,
        ini=ini.strftime("%m-%d-%Y"),
        fim=fim.strftime("%m-%d-%Y"),
    )
    resposta = requests.get(url, headers=config.CABECALHO_HTTP,
                            timeout=config.TIMEOUT)
    resposta.raise_for_status()
    valores = resposta.json().get("value") or []
    if not valores:
        return None
    linha = valores[0]
    return {
        "moeda": moeda,
        "compra": float(linha["cotacaoCompra"]),
        "venda": float(linha["cotacaoVenda"]),
        "boletim": linha.get("tipoBoletim", ""),
        "momento": linha.get("dataHoraCotacao", ""),
    }


def ler_ptax_todas() -> dict:
    saida = {}
    for moeda in config.MOEDAS:
        try:
            cotacao = ler_ptax(moeda)
            if cotacao:
                saida[moeda] = cotacao
        except Exception as erro:                      # noqa: BLE001
            saida[moeda] = {"moeda": moeda, "erro": "%s: %s" % (
                type(erro).__name__, erro)}
    return saida


# ------------------------------------------------------------- agencias (auto)

_NUMERO = re.compile(r"\d{1,3}(?:\.\d{3})*,\d+|\d+[.,]\d+")


def _para_float(texto: str) -> float | None:
    if not texto:
        return None
    texto = texto.strip()
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        valor = float(texto)
    except ValueError:
        return None
    return valor if 0.5 < valor < 100 else None


def ler_msc() -> dict:
    """MSC Brazil Rate of Exchange.

    Procura o codigo da moeda e pega o primeiro numero que vem depois dele.
    Nao depende de classe de CSS nem de posicao de coluna, entao aguenta
    mudanca de layout. Serve de molde para qualquer outra agencia.
    """
    resposta = requests.get(config.MSC_URL, headers=config.CABECALHO_HTTP,
                            timeout=config.TIMEOUT)
    resposta.raise_for_status()
    resposta.encoding = resposta.apparent_encoding or "utf-8"
    sopa = BeautifulSoup(resposta.text, "html.parser")
    texto = sopa.get_text("\n")

    saida = {}
    for moeda in config.MOEDAS:
        achado = re.search(
            r"\b%s\b[^\d\n]*[\n\s]*(%s)" % (moeda, _NUMERO.pattern),
            texto, re.IGNORECASE)
        if achado:
            valor = _para_float(achado.group(1))
            if valor:
                saida[moeda] = valor

    rotulo = sopa.find(id="DateToday")
    if rotulo:
        saida["_data"] = rotulo.get_text(strip=True)
    return saida


LEITORES = {
    "ler_msc": ler_msc,
}


def ler_agencias() -> dict:
    """Roda todos os leitores registrados em config.AGENCIAS_AUTOMATICAS."""
    saida = {}
    for agencia, nome_funcao in config.AGENCIAS_AUTOMATICAS.items():
        funcao = LEITORES.get(nome_funcao)
        if not funcao:
            saida[agencia] = {"erro": "leitor '%s' nao existe" % nome_funcao}
            continue
        try:
            saida[agencia] = funcao()
        except Exception as erro:                      # noqa: BLE001
            saida[agencia] = {"erro": "%s: %s" % (type(erro).__name__, erro)}
    return saida
