# -*- coding: utf-8 -*-
"""Espera, permanencia e a reconciliacao entre duas coletas.

A SPA nao publica a hora exata em que o navio encostou nem em que soltou
amarras. O que ela publica e uma foto do cais agora. Entao:

  atracacao = evento ATRACACAO programado para esse navio, quando existe;
              senao, o momento da primeira coleta em que ele apareceu atracado
  saida     = momento da primeira coleta em que ele deixou de aparecer

Quando a hora e deduzida assim, o painel marca com "~".
"""

from __future__ import annotations

from datetime import datetime, timedelta

import config
from armazenamento import (abrir_escala, atualizar_escala, escalas_abertas,
                           escalas_fechadas_desde, fechar_escala)
from coleta_navios import ler_data

JANELA_ATRACACAO_DIAS = 4


def _iso(momento: datetime) -> str:
    return momento.isoformat(sep=" ", timespec="seconds")


def _para_datetime(valor) -> datetime | None:
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor
    valor = str(valor).strip()
    for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(valor, formato)
        except ValueError:
            continue
    return ler_data(valor)


def duracao_texto(delta: timedelta | None) -> str:
    if delta is None:
        return ""
    total = int(delta.total_seconds())
    sinal = "-" if total < 0 else ""
    total = abs(total)
    dias, resto = divmod(total, 86400)
    horas, resto = divmod(resto, 3600)
    minutos = resto // 60
    if dias:
        return "%s%dd %02dh" % (sinal, dias, horas)
    return "%s%02dh %02dmin" % (sinal, horas, minutos)


# ------------------------------------------------------------- reconciliacao

def _atracacao_programada(con, chave_navio: str, referencia: datetime):
    """Ultimo evento de atracacao publicado para esse navio, se recente."""
    limite = _iso(referencia - timedelta(days=JANELA_ATRACACAO_DIAS))
    cursor = con.execute(
        """SELECT momento FROM programados
            WHERE chave_navio = ? AND momento >= ? AND momento <= ?
              AND evento IN ('ATRACACAO', 'REATRACACAO')
            ORDER BY momento DESC LIMIT 1""",
        (chave_navio, limite, _iso(referencia + timedelta(hours=6))))
    linha = cursor.fetchone()
    return _para_datetime(linha["momento"]) if linha else None


def _dados_esperado(con, chave_navio: str, referencia: datetime) -> dict:
    """A escala certa do navio, não simplesmente a última vista.

    Um navio que já atracou costuma reaparecer na lista de esperados com a
    chegada da PRÓXIMA viagem. Pegar a linha mais recente daria uma ETA no
    futuro e uma espera negativa. Então vale a chegada mais recente que já
    aconteceu; sem nenhuma, fica em branco em vez de errada.
    """
    cursor = con.execute("SELECT * FROM esperados WHERE chave_navio = ?",
                         (chave_navio,))
    candidatos = [dict(l) for l in cursor.fetchall()]
    if not candidatos:
        return {}

    passadas = []
    for linha in candidatos:
        chegada = _para_datetime(linha.get("chegada"))
        if chegada and chegada <= referencia:
            passadas.append((chegada, linha))
    if not passadas:
        return {}
    passadas.sort(key=lambda par: par[0])
    return passadas[-1][1]


def reconciliar(con, atracados: list[dict], momento: datetime | None = None) -> dict:
    """Compara o cais de agora com as escalas abertas no banco."""
    momento = momento or datetime.now()
    marca = _iso(momento)

    no_cais = {}
    for linha in atracados:
        no_cais.setdefault(linha["chave_navio"], linha)

    abertas = {e["chave_navio"]: e for e in escalas_abertas(con)}

    novas, fechadas = 0, 0

    for chave, linha in no_cais.items():
        esperado = _dados_esperado(con, chave, momento)
        comum = {
            "local": linha.get("local", ""),
            "terminal": linha.get("terminal", ""),
            "carga": linha.get("carga", ""),
            "descarga": linha.get("descarga", ""),
            "embarque": linha.get("embarque", ""),
            "agencia": esperado.get("agencia", ""),
            "imo": esperado.get("imo", ""),
            "viagem": esperado.get("viagem", ""),
            "eta": esperado.get("chegada", ""),
        }
        if chave in abertas:
            atualizar_escala(con, abertas[chave]["id"], comum)
            continue

        programada = _atracacao_programada(con, chave, momento)
        comum.update({
            "chave_navio": chave,
            "navio": linha["navio"],
            "atracacao": _iso(programada) if programada else marca,
            "atracacao_exata": bool(programada),
        })
        abrir_escala(con, comum)
        novas += 1

    for chave, escala in abertas.items():
        if chave not in no_cais:
            fechar_escala(con, escala["id"], marca, exata=False)
            fechadas += 1

    con.commit()
    return {"no_cais": len(no_cais), "novas": novas, "fechadas": fechadas}


# ----------------------------------------------------------------- calculos

def enriquecer(escala: dict, referencia: datetime | None = None) -> dict:
    """Acrescenta espera, permanencia e os rotulos que o painel mostra."""
    referencia = referencia or datetime.now()
    saida = dict(escala)

    eta = _para_datetime(escala.get("eta"))
    atracacao = _para_datetime(escala.get("atracacao"))
    fim = _para_datetime(escala.get("saida"))
    em_curso = not escala.get("saida")

    saida["eta_dt"] = eta
    saida["atracacao_dt"] = atracacao
    saida["saida_dt"] = fim
    saida["em_curso"] = em_curso

    espera = (atracacao - eta) if (eta and atracacao) else None
    if espera is not None and espera.total_seconds() < 0:
        espera = None
    saida["espera"] = espera
    saida["espera_txt"] = duracao_texto(espera)

    marco_final = fim if fim else referencia
    permanencia = (marco_final - atracacao) if atracacao else None
    if permanencia is not None and permanencia.total_seconds() < 0:
        permanencia = None
    saida["permanencia"] = permanencia
    saida["permanencia_txt"] = duracao_texto(permanencia)
    if permanencia is not None and em_curso:
        saida["permanencia_txt"] += " (em curso)"

    saida["eta_txt"] = eta.strftime("%d/%m %H:%M") if eta else "—"
    if atracacao:
        prefixo = "" if escala.get("atracacao_exata") else "~"
        saida["atracacao_txt"] = prefixo + atracacao.strftime("%d/%m %H:%M")
    else:
        saida["atracacao_txt"] = "—"
    if fim:
        prefixo = "" if escala.get("saida_exata") else "~"
        saida["saida_txt"] = prefixo + fim.strftime("%d/%m %H:%M")
    else:
        saida["saida_txt"] = "no cais"
    return saida


def media_permanencia(con, terminal: str, dias: int | None = None):
    """Permanencia media do terminal na janela configurada."""
    dias = dias or config.JANELA_MEDIA_DIAS
    desde = _iso(datetime.now() - timedelta(days=dias))
    total, quantos = timedelta(0), 0
    for escala in escalas_fechadas_desde(con, desde):
        if escala.get("terminal") != terminal:
            continue
        inicio = _para_datetime(escala.get("atracacao"))
        fim = _para_datetime(escala.get("saida"))
        if not inicio or not fim or fim <= inicio:
            continue
        total += (fim - inicio)
        quantos += 1
    if not quantos:
        return None, 0
    return total / quantos, quantos
