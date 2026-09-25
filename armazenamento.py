# -*- coding: utf-8 -*-
"""Banco SQLite. Um arquivo so, do lado do projeto."""

from __future__ import annotations

import sqlite3
from datetime import datetime

import config

ESQUEMA = """
CREATE TABLE IF NOT EXISTS coletas (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    momento  TEXT NOT NULL,
    tipo     TEXT NOT NULL,
    resumo   TEXT
);

CREATE TABLE IF NOT EXISTS esperados (
    chave_navio      TEXT NOT NULL,
    viagem           TEXT NOT NULL DEFAULT '',
    navio            TEXT,
    imo              TEXT,
    agencia          TEXT,
    chegada          TEXT,
    mercadoria       TEXT,
    classe           TEXT,
    peso             TEXT,
    prioridade       TEXT,
    duv              TEXT,
    terminal_previsto TEXT,
    visto_em         TEXT,
    PRIMARY KEY (chave_navio, viagem)
);

CREATE TABLE IF NOT EXISTS programados (
    chave_navio TEXT NOT NULL,
    momento     TEXT NOT NULL,
    evento      TEXT NOT NULL,
    local       TEXT,
    imo         TEXT,
    viagem      TEXT,
    duv         TEXT,
    eta         TEXT,
    visto_em    TEXT,
    PRIMARY KEY (chave_navio, momento, evento)
);

CREATE TABLE IF NOT EXISTS escalas (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    chave_navio       TEXT NOT NULL,
    navio             TEXT,
    imo               TEXT,
    viagem            TEXT,
    agencia           TEXT,
    carga             TEXT,
    local             TEXT,
    terminal          TEXT,
    descarga          TEXT,
    embarque          TEXT,
    eta               TEXT,
    atracacao         TEXT,
    atracacao_exata   INTEGER DEFAULT 0,
    saida             TEXT,
    saida_exata       INTEGER DEFAULT 0,
    aberta            INTEGER DEFAULT 1,
    criada_em         TEXT,
    atualizada_em     TEXT
);

CREATE INDEX IF NOT EXISTS ix_escalas_aberta   ON escalas (aberta);
CREATE INDEX IF NOT EXISTS ix_escalas_navio    ON escalas (chave_navio);
CREATE INDEX IF NOT EXISTS ix_escalas_terminal ON escalas (terminal);

CREATE TABLE IF NOT EXISTS fundeados (
    chave_navio       TEXT PRIMARY KEY,
    navio             TEXT,
    chegada           TEXT,
    agencia           TEXT,
    operacao          TEXT,
    mercadoria        TEXT,
    peso              TEXT,
    terminal_previsto TEXT,
    programado        INTEGER DEFAULT 0,
    visto_em          TEXT
);

CREATE TABLE IF NOT EXISTS cambio (
    momento  TEXT NOT NULL,
    origem   TEXT NOT NULL,   -- 'PTAX' ou o nome da agencia
    tipo     TEXT NOT NULL,   -- 'oficial', 'auto', 'manual'
    moeda    TEXT NOT NULL,
    valor    REAL NOT NULL,
    extra    TEXT
);

CREATE INDEX IF NOT EXISTS ix_cambio_busca ON cambio (origem, moeda, momento);
"""


def agora() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def conectar(caminho: str | None = None) -> sqlite3.Connection:
    con = sqlite3.connect(caminho or config.BANCO)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    return con


# ------------------------------------------------------------------ registros

def registrar_coleta(con, tipo: str, resumo: str = "") -> None:
    con.execute("INSERT INTO coletas (momento, tipo, resumo) VALUES (?,?,?)",
                (agora(), tipo, resumo))


def gravar_esperados(con, linhas: list[dict]) -> None:
    """Guarda o que a SPA publica antes do navio atracar.

    Depois que ele encosta no cais some da lista, entao a ETA e a agencia
    so existem porque foram salvas aqui antes.
    """
    momento = agora()
    for linha in linhas:
        con.execute(
            """INSERT INTO esperados
               (chave_navio, viagem, navio, imo, agencia, chegada, mercadoria,
                classe, peso, prioridade, duv, terminal_previsto, visto_em)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(chave_navio, viagem) DO UPDATE SET
                 navio=excluded.navio,
                 imo=COALESCE(NULLIF(excluded.imo,''), esperados.imo),
                 agencia=COALESCE(NULLIF(excluded.agencia,''), esperados.agencia),
                 chegada=COALESCE(NULLIF(esperados.chegada,''), excluded.chegada),
                 mercadoria=excluded.mercadoria,
                 terminal_previsto=excluded.terminal_previsto,
                 visto_em=excluded.visto_em""",
            (linha["chave_navio"], linha.get("viagem_curta") or linha.get("viagem", ""),
             linha["navio"], linha.get("imo", ""), linha.get("agencia", ""),
             linha.get("chegada", ""), linha.get("mercadoria", ""),
             linha.get("classe", ""), linha.get("peso", ""),
             linha.get("prioridade", ""), linha.get("duv", ""),
             linha.get("terminal_previsto", ""), momento))


def gravar_programados(con, linhas: list[dict]) -> None:
    momento = agora()
    for linha in linhas:
        if not linha.get("momento"):
            continue
        con.execute(
            """INSERT OR IGNORE INTO programados
               (chave_navio, momento, evento, local, imo, viagem, duv, eta, visto_em)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (linha["chave_navio"], linha["momento"], linha.get("evento", ""),
             linha.get("local", ""), linha.get("imo", ""), linha.get("viagem", ""),
             linha.get("duv", ""), linha.get("eta", ""), momento))


def gravar_fundeados(con, linhas: list[dict]) -> None:
    """Foto do fundeadouro. Substitui a anterior: quem saiu da lista, saiu."""
    momento = agora()
    con.execute("DELETE FROM fundeados")
    for linha in linhas:
        navio = linha.get("navio", "")
        programado = "PROGRAMADO" in navio.upper()
        nome = navio.split("/")[0].strip() if programado else navio.strip()
        con.execute(
            """INSERT OR REPLACE INTO fundeados
               (chave_navio, navio, chegada, agencia, operacao, mercadoria,
                peso, terminal_previsto, programado, visto_em)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (linha["chave_navio"], nome, linha.get("chegada", ""),
             linha.get("agencia", ""), linha.get("operacao", ""),
             linha.get("mercadoria", "") or linha.get("tipo", ""),
             linha.get("peso", ""), linha.get("terminal_previsto", ""),
             int(programado), momento))


def fundeados_atuais(con) -> list[dict]:
    cursor = con.execute("SELECT * FROM fundeados ORDER BY chegada")
    return [dict(l) for l in cursor.fetchall()]


def gravar_cambio(con, origem: str, tipo: str, moeda: str,
                  valor: float, extra: str = "", momento: str | None = None) -> None:
    con.execute("INSERT INTO cambio (momento, origem, tipo, moeda, valor, extra)"
                " VALUES (?,?,?,?,?,?)",
                (momento or agora(), origem, tipo, moeda, float(valor), extra))


def ultimas_taxas(con) -> list[dict]:
    """Ultimo valor de cada par origem+moeda."""
    cursor = con.execute(
        """SELECT c.origem, c.moeda, c.valor, c.tipo, c.momento, c.extra
             FROM cambio c
             JOIN (SELECT origem, moeda, MAX(momento) AS m
                     FROM cambio GROUP BY origem, moeda) u
               ON u.origem = c.origem AND u.moeda = c.moeda AND u.m = c.momento
            ORDER BY c.origem, c.moeda""")
    return [dict(l) for l in cursor.fetchall()]


# -------------------------------------------------------------------- escalas

def escalas_abertas(con) -> list[dict]:
    cursor = con.execute("SELECT * FROM escalas WHERE aberta = 1")
    return [dict(l) for l in cursor.fetchall()]


def abrir_escala(con, dados: dict) -> None:
    momento = agora()
    con.execute(
        """INSERT INTO escalas
           (chave_navio, navio, imo, viagem, agencia, carga, local, terminal,
            descarga, embarque, eta, atracacao, atracacao_exata,
            aberta, criada_em, atualizada_em)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)""",
        (dados["chave_navio"], dados["navio"], dados.get("imo", ""),
         dados.get("viagem", ""), dados.get("agencia", ""), dados.get("carga", ""),
         dados.get("local", ""), dados.get("terminal", ""),
         dados.get("descarga", ""), dados.get("embarque", ""),
         dados.get("eta", ""), dados.get("atracacao", ""),
         int(dados.get("atracacao_exata", 0)), momento, momento))


def atualizar_escala(con, id_escala: int, dados: dict) -> None:
    campos = ["local", "terminal", "carga", "descarga", "embarque",
              "agencia", "imo", "viagem", "eta"]
    trechos, valores = [], []
    for campo in campos:
        if dados.get(campo):
            trechos.append("%s = ?" % campo)
            valores.append(dados[campo])
    trechos.append("atualizada_em = ?")
    valores.append(agora())
    valores.append(id_escala)
    con.execute("UPDATE escalas SET %s WHERE id = ?" % ", ".join(trechos), valores)


def fechar_escala(con, id_escala: int, saida: str, exata: bool = False) -> None:
    con.execute("UPDATE escalas SET aberta = 0, saida = ?, saida_exata = ?,"
                " atualizada_em = ? WHERE id = ?",
                (saida, int(exata), agora(), id_escala))


def escalas_do_periodo(con, desde: str) -> list[dict]:
    cursor = con.execute(
        "SELECT * FROM escalas WHERE aberta = 1 OR saida >= ? ORDER BY terminal, navio",
        (desde,))
    return [dict(l) for l in cursor.fetchall()]


def escalas_fechadas_desde(con, desde: str) -> list[dict]:
    cursor = con.execute(
        "SELECT * FROM escalas WHERE aberta = 0 AND saida >= ?"
        " AND atracacao <> '' AND saida <> ''", (desde,))
    return [dict(l) for l in cursor.fetchall()]
