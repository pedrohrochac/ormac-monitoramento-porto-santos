# -*- coding: utf-8 -*-
"""Diagnostico das origens.

Testa cada fonte, mostra o que voltou e aponta os bercos que ainda nao
tem terminal no config.MAPA_TERMINAIS.

    python verificar_fontes.py
"""

from __future__ import annotations

import sys
import traceback

import coleta_cambio
import coleta_navios
import config


def _titulo(texto: str) -> None:
    print("\n" + texto)
    print("-" * len(texto))


def testar_navios() -> list[str]:
    nao_mapeados = set()
    for nome, fonte in config.FONTES.items():
        _titulo("%s  [%s]" % (fonte["rotulo"], nome))
        print(fonte["url"])
        try:
            html = coleta_navios.baixar(nome)
        except Exception as erro:                       # noqa: BLE001
            print("  FALHOU no download: %s: %s" % (type(erro).__name__, erro))
            continue

        print("  HTTP ok, %d KB" % (len(html) // 1024))
        tabelas = html.count('id="%s"' % fonte["tabela"])
        print("  tabelas com id='%s': %d" % (fonte["tabela"], tabelas))
        if not tabelas:
            print("  ATENÇÃO: o id da tabela mudou. Ajuste config.FONTES"
                  "['%s']['tabela']." % nome)
            continue

        try:
            linhas = coleta_navios.PARSERS[nome](html)
        except Exception:                               # noqa: BLE001
            print("  FALHOU ao interpretar:")
            traceback.print_exc(limit=3)
            continue

        print("  linhas lidas: %d" % len(linhas))
        if linhas:
            print("  campos: %s" % ", ".join(linhas[0].keys()))
            print("  exemplo:")
            for chave, valor in list(linhas[0].items()):
                print("    %-18s %s" % (chave, valor))

        for linha in linhas:
            local = linha.get("local")
            if local and linha.get("terminal") == config.TERMINAL_DESCONHECIDO:
                nao_mapeados.add(local)

    return sorted(nao_mapeados)


def testar_cambio() -> None:
    _titulo("PTAX / Banco Central")
    for moeda in config.MOEDAS:
        try:
            cotacao = coleta_cambio.ler_ptax(moeda)
            if cotacao:
                print("  %s  venda %.4f  compra %.4f  %s  %s"
                      % (moeda, cotacao["venda"], cotacao["compra"],
                         cotacao["boletim"], cotacao["momento"]))
            else:
                print("  %s  sem cotação na janela consultada" % moeda)
        except Exception as erro:                       # noqa: BLE001
            print("  %s  FALHOU: %s: %s" % (moeda, type(erro).__name__, erro))

    for agencia, leitura in coleta_cambio.ler_agencias().items():
        _titulo("Agência %s (automática)" % agencia)
        if "erro" in leitura:
            print("  FALHOU: %s" % leitura["erro"])
            continue
        if not any(m in leitura for m in config.MOEDAS):
            print("  A página abriu mas nenhuma moeda foi encontrada. "
                  "O layout deve ter mudado.")
        for chave, valor in leitura.items():
            print("  %-8s %s" % (chave, valor))


def main() -> int:
    print("Verificação das fontes do %s" % config.NOME_PAINEL)
    nao_mapeados = testar_navios()
    testar_cambio()

    _titulo("Berços sem terminal definido")
    if not nao_mapeados:
        print("  Nenhum. Todos os berços vistos agora caem em algum terminal.")
    else:
        print("  Estes berços apareceram e ainda não têm dono no config.py.")
        print("  Copie o bloco abaixo para dentro de MAPA_TERMINAIS e preencha:\n")
        for local in nao_mapeados:
            print('    "%s": "",' % local)

    print("\nPronto. Se algo falhou acima, é isso que precisa de ajuste.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
