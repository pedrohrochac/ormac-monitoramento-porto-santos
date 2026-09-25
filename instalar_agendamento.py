# -*- coding: utf-8 -*-
"""Agenda as coletas na ferramenta nativa do sistema.

    python instalar_agendamento.py            instala (ou substitui)
    python instalar_agendamento.py --remover  desfaz tudo

Windows -> Agendador de Tarefas (schtasks)
Linux/Mac -> cron (crontab)
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys

import config

PREFIXO = "MonitorSantos"
MARCA_CRON = "# monitor-santos (gerado por instalar_agendamento.py)"

PASTA = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable
PRINCIPAL = os.path.join(PASTA, "main.py")


# ------------------------------------------------------------------- windows

def _schtasks(argumentos: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["schtasks"] + argumentos, capture_output=True, text=True)


def windows_instalar() -> int:
    windows_remover(silencioso=True)
    falhas = 0

    for indice, horario in enumerate(config.HORARIOS_COLETA_COMPLETA, start=1):
        nome = "%s_Completa_%d" % (PREFIXO, indice)
        resultado = _schtasks([
            "/Create", "/TN", nome, "/SC", "DAILY", "/ST", horario, "/F",
            "/TR", '"%s" "%s"' % (PYTHON, PRINCIPAL),
        ])
        if resultado.returncode:
            falhas += 1
            print("  falhou %s: %s" % (nome, resultado.stderr.strip()))
        else:
            print("  criada %-24s diária às %s" % (nome, horario))

    nome = "%s_Cambio" % PREFIXO
    resultado = _schtasks([
        "/Create", "/TN", nome, "/SC", "MINUTE",
        "/MO", str(config.INTERVALO_CAMBIO_MINUTOS), "/F",
        "/TR", '"%s" "%s" --cambio' % (PYTHON, PRINCIPAL),
    ])
    if resultado.returncode:
        falhas += 1
        print("  falhou %s: %s" % (nome, resultado.stderr.strip()))
    else:
        print("  criada %-24s a cada %d min"
              % (nome, config.INTERVALO_CAMBIO_MINUTOS))

    print("\nObservação: para a tarefa rodar com a sessão bloqueada, abra o "
          "Agendador de Tarefas, aba Geral, e marque \"Executar estando o "
          "usuário conectado ou não\".")
    return 1 if falhas else 0


def windows_remover(silencioso: bool = False) -> int:
    resultado = _schtasks(["/Query", "/FO", "LIST"])
    nomes = []
    for linha in resultado.stdout.splitlines():
        if linha.strip().lower().startswith("taskname:"):
            nome = linha.split(":", 1)[1].strip().lstrip("\\")
            if nome.startswith(PREFIXO):
                nomes.append(nome)
    for nome in nomes:
        _schtasks(["/Delete", "/TN", nome, "/F"])
        if not silencioso:
            print("  removida %s" % nome)
    if not nomes and not silencioso:
        print("  nada a remover")
    return 0


# ---------------------------------------------------------------- linux / mac

def _ler_crontab() -> str:
    resultado = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return resultado.stdout if resultado.returncode == 0 else ""


def _gravar_crontab(conteudo: str) -> bool:
    if not conteudo.endswith("\n"):
        conteudo += "\n"
    resultado = subprocess.run(["crontab", "-"], input=conteudo,
                               capture_output=True, text=True)
    if resultado.returncode:
        print("  falhou ao gravar o crontab: %s" % resultado.stderr.strip())
        return False
    return True


def _sem_nossas_linhas(conteudo: str) -> list[str]:
    return [l for l in conteudo.splitlines() if MARCA_CRON not in l]


def unix_instalar() -> int:
    linhas = _sem_nossas_linhas(_ler_crontab())

    horas, minutos = [], set()
    for horario in config.HORARIOS_COLETA_COMPLETA:
        hora, minuto = horario.split(":")
        horas.append(str(int(hora)))
        minutos.add(int(minuto))
    minuto_comum = sorted(minutos)[0] if minutos else 0

    if len(minutos) > 1:
        print("  aviso: os horários têm minutos diferentes; o cron agrupado usa "
              "o menor (%02d). Para minutos distintos, uma linha por horário."
              % minuto_comum)

    completa = ('%d %s * * * cd "%s" && "%s" main.py >> monitor.log 2>&1  %s'
                % (minuto_comum, ",".join(horas), PASTA, PYTHON, MARCA_CRON))
    cambio = ('*/%d * * * * cd "%s" && "%s" main.py --cambio >> monitor.log 2>&1  %s'
              % (config.INTERVALO_CAMBIO_MINUTOS, PASTA, PYTHON, MARCA_CRON))

    linhas += [completa, cambio]
    if not _gravar_crontab("\n".join(linhas)):
        return 1

    print("  %s" % completa)
    print("  %s" % cambio)
    print("\nA saída de cada execução fica em %s/monitor.log"
          % PASTA)
    if platform.system() == "Darwin":
        print("No macOS, o sistema pode pedir permissão de acesso a disco para o "
              "cron na primeira execução (Ajustes > Privacidade e Segurança).")
    return 0


def unix_remover() -> int:
    atual = _ler_crontab()
    linhas = _sem_nossas_linhas(atual)
    if len(linhas) == len(atual.splitlines()):
        print("  nada a remover")
        return 0
    if not _gravar_crontab("\n".join(linhas)):
        return 1
    print("  linhas do monitor removidas do crontab")
    return 0


# --------------------------------------------------------------------- main

def main(argumentos: list[str]) -> int:
    remover = "--remover" in argumentos
    sistema = platform.system()
    print("Sistema: %s" % sistema)
    print("Pasta:   %s" % PASTA)
    print("Python:  %s\n" % PYTHON)

    if not os.path.exists(PRINCIPAL):
        print("main.py não está nesta pasta. Rode o instalador de dentro do projeto.")
        return 2

    if sistema == "Windows":
        return windows_remover() if remover else windows_instalar()
    if sistema in ("Linux", "Darwin"):
        return unix_remover() if remover else unix_instalar()

    print("Sistema não reconhecido. Agende na mão: main.py nos horários %s e "
          "main.py --cambio a cada %d minutos."
          % (", ".join(config.HORARIOS_COLETA_COMPLETA),
             config.INTERVALO_CAMBIO_MINUTOS))
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
