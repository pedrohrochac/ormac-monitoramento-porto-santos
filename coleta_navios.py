# -*- coding: utf-8 -*-
"""Le as listas de movimento de navios publicadas pela SPA."""

from __future__ import annotations

import os
import re
import unicodedata
from datetime import datetime

import requests
from bs4 import BeautifulSoup

import config


# --------------------------------------------------------------- utilitarios

def _texto(celula) -> str:
    """Texto da celula com <br> virando barra, espacos colapsados."""
    for br in celula.find_all("br"):
        br.replace_with("\n")
    bruto = celula.get_text("\n")
    partes = [p.strip() for p in bruto.split("\n")]
    partes = [p for p in partes if p]
    return " / ".join(partes)


def _primeiro(valor: str) -> str:
    """Primeira linha de uma celula que veio com varios valores empilhados."""
    return valor.split(" / ")[0].strip() if valor else ""


def normalizar(texto: str) -> str:
    """Chave de comparacao: sem acento, sem pontuacao, maiuscula."""
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^A-Za-z0-9]+", " ", t)
    return t.upper().strip()


def ler_data(valor: str):
    """Aceita dd/mm/aaaa, dd/mm/aaaa hh:mm:ss e dd/mm/aaaa hh:mm."""
    if not valor:
        return None
    valor = valor.strip()
    for formato in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(valor, formato)
        except ValueError:
            continue
    return None


def terminal_de(local: str) -> str:
    """Traduz o codigo do berco para o nome do terminal."""
    if not local:
        return config.TERMINAL_DESCONHECIDO
    chave = normalizar(local)

    for bruto, nome in config.MAPA_TERMINAIS.items():
        if normalizar(bruto) == chave:
            return nome

    for fragmento, nome in config.FAIXAS_BERCOS:
        if chave.startswith(normalizar(fragmento)):
            return nome

    # Segunda tentativa sem separador nenhum: a SPA escreve o mesmo terminal
    # como "BTP I" numa lista e "B.T.P. 1" noutra.
    compacta = chave.replace(" ", "")
    for fragmento, nome in config.FAIXAS_BERCOS:
        if compacta.startswith(normalizar(fragmento).replace(" ", "")):
            return nome

    # Codigo que comeca com numero e berco do cais publico da SPA.
    if getattr(config, "PREFIXO_NUMERICO_E_CAIS_PUBLICO", False) and chave[:1].isdigit():
        return "Cais Público"

    return config.TERMINAL_DESCONHECIDO


# ------------------------------------------------------------------ download

def baixar(nome: str) -> str:
    """Baixa uma lista da SPA.

    O site serve a cadeia de certificados incompleta: o navegador se vira
    porque busca o certificado intermediário sozinho, mas o Python não faz
    isso. Se for o caso, coloque o intermediário em ca-extra.pem ao lado do
    projeto e aponte config.CA_EXTRA para ele. Nunca desligue a verificação.
    """
    fonte = config.FONTES[nome]
    extra = getattr(config, "CA_EXTRA", "")
    verificar = extra if (extra and os.path.exists(extra)) else True
    try:
        resposta = requests.get(fonte["url"], headers=config.CABECALHO_HTTP,
                                timeout=config.TIMEOUT, verify=verificar)
    except requests.exceptions.SSLError as erro:
        raise RuntimeError(
            "Falha na verificação do certificado de %s. O site publica a "
            "cadeia incompleta. Salve o certificado intermediário em "
            "ca-extra.pem e aponte config.CA_EXTRA para ele. Detalhe: %s"
            % (fonte["url"].split("/")[2], erro)) from erro
    resposta.raise_for_status()
    resposta.encoding = resposta.apparent_encoding or "utf-8"
    return resposta.text


def _tabelas(html: str, id_tabela: str):
    sopa = BeautifulSoup(html, "html.parser")
    return sopa.find_all("table", id=id_tabela)


def _linhas_de_dados(tabela):
    """Devolve (titulo_do_grupo, [linhas]) de uma tabela da SPA.

    As tabelas vem com um <th colspan> de titulo (classe de carga, turno)
    seguido da linha de cabecalhos. O resto sao dados.
    """
    titulo = ""
    cabecalho = tabela.find("thead")
    if cabecalho:
        primeira = cabecalho.find("tr")
        if primeira and primeira.find("th") and primeira.find("th").get("colspan"):
            titulo = _texto(primeira.find("th"))

    corpo = tabela.find("tbody") or tabela
    linhas = [tr for tr in corpo.find_all("tr") if tr.find("td")]
    return titulo, linhas


def _campo(celulas, indice: int) -> str:
    return _texto(celulas[indice]) if indice < len(celulas) else ""


# ----------------------------------------------------------------- parsers

def parsear_atracados(html: str) -> list[dict]:
    """Local | Navio | 4 turnos | Carga | Desc. | Emb."""
    saida = []
    for tabela in _tabelas(html, "atracados"):
        _, linhas = _linhas_de_dados(tabela)
        for tr in linhas:
            c = tr.find_all("td")
            local = _campo(c, 0)
            navio = _campo(c, 1)
            if not navio:
                continue
            saida.append({
                "local": local,
                "terminal": terminal_de(local),
                "navio": navio,
                "chave_navio": normalizar(navio),
                "turnos": " ".join(_campo(c, i) for i in (2, 3, 4, 5)).strip(),
                "carga": _campo(c, 6),
                "descarga": _campo(c, 7),
                "embarque": _campo(c, 8),
            })
    return saida


def parsear_esperados(html: str) -> list[dict]:
    """Navio | Bandeira | Com/Cal | Nav | Chegada | Carimbo | Agencia |
    Operac | Mercadoria | Peso | Viagem | DUV | P | Terminal | IMO"""
    saida = []
    for tabela in _tabelas(html, "esperados"):
        classe, linhas = _linhas_de_dados(tabela)
        for tr in linhas:
            c = tr.find_all("td")
            navio = _campo(c, 0)
            if not navio:
                continue
            viagem = _primeiro(_campo(c, 10)).replace("--", "").strip("-")
            saida.append({
                "classe": classe,
                "navio": navio,
                "chave_navio": normalizar(navio),
                "bandeira": _campo(c, 1),
                "dimensoes": _campo(c, 2),
                "navegacao": _campo(c, 3),
                "chegada": _campo(c, 4),
                "carimbo": _campo(c, 5),
                "agencia": _campo(c, 6),
                "operacao": _campo(c, 7),
                "mercadoria": _campo(c, 8),
                "peso": _campo(c, 9),
                "viagem": _campo(c, 10),
                "viagem_curta": viagem,
                "duv": _campo(c, 11),
                "prioridade": _campo(c, 12),
                "terminal_previsto": _campo(c, 13),
                "imo": _campo(c, 14).lstrip("0"),
            })
    return saida


def parsear_fundeados(html: str) -> list[dict]:
    """Mesma estrutura dos esperados, sem DUV e sem IMO."""
    saida = []
    for tabela in _tabelas(html, "fundeados"):
        _, linhas = _linhas_de_dados(tabela)
        for tr in linhas:
            c = tr.find_all("td")
            navio = _campo(c, 0)
            if not navio:
                continue
            saida.append({
                "navio": navio,
                "chave_navio": normalizar(navio),
                "bandeira": _campo(c, 1),
                "chegada": _campo(c, 4),
                "agencia": _campo(c, 6),
                "operacao": _campo(c, 7),
                "mercadoria": _campo(c, 8),
                "viagem": _campo(c, 10),
                "terminal_previsto": _campo(c, 12),
            })
    return saida


def parsear_programados(html: str) -> list[dict]:
    """Data | Hora | ETA | Local | Navio | IMO | Carga | Evento | Viagem | DUV"""
    saida = []
    for tabela in _tabelas(html, "programados2"):
        turno, linhas = _linhas_de_dados(tabela)
        for tr in linhas:
            c = tr.find_all("td")
            navio = _campo(c, 4)
            if not navio:
                continue
            data = _campo(c, 0)
            hora = _campo(c, 1)
            inicio = hora.split("/")[0].strip() if hora else ""
            momento = ler_data("%s %s" % (data, inicio)) if inicio else ler_data(data)
            saida.append({
                "turno": turno,
                "data": data,
                "hora": hora,
                "momento": momento.isoformat(sep=" ") if momento else "",
                "eta": _campo(c, 2),
                "local": _campo(c, 3),
                "terminal": terminal_de(_campo(c, 3)),
                "navio": navio,
                "chave_navio": normalizar(navio),
                "imo": _campo(c, 5).lstrip("0"),
                "carga": _campo(c, 6),
                "evento": _campo(c, 7),
                "viagem": _campo(c, 8),
                "duv": _campo(c, 9),
            })
    return saida


PARSERS = {
    "atracados": parsear_atracados,
    "programados": parsear_programados,
    "esperados_carga": parsear_esperados,
    "esperados_passageiros": parsear_esperados,
    "fundeados": parsear_fundeados,
}


def coletar(quais=None) -> dict:
    """Baixa e interpreta as listas. Uma fonte que falhar nao derruba as outras."""
    quais = quais or list(config.FONTES)
    resultado = {}
    for nome in quais:
        try:
            html = baixar(nome)
            resultado[nome] = {"ok": True, "dados": PARSERS[nome](html), "erro": ""}
        except Exception as erro:                      # noqa: BLE001
            resultado[nome] = {"ok": False, "dados": [], "erro": "%s: %s" % (
                type(erro).__name__, erro)}
    return resultado
