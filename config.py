# -*- coding: utf-8 -*-
"""
Tudo que muda mora aqui.

Editou alguma coisa nos horarios? Rode de novo:
    python instalar_agendamento.py
"""

# ---------------------------------------------------------------- identidade
NOME_PAINEL = "Monitor Porto de Santos"
EMPRESA = "Grupo Ormac"
LOGO = "logo.png"          # opcional; se o arquivo nao existir o painel sai sem logo
ARQUIVO_PAINEL = "painel.html"
BANCO = "monitor_santos.db"

# ------------------------------------------------------------------ horarios
# Coleta completa (navios + cambio), de 2 em 2 horas.
HORARIOS_COLETA_COMPLETA = ["00:00", "02:00", "04:00", "06:00", "08:00", "10:00",
                            "12:00", "14:00", "16:00", "18:00", "20:00", "22:00"]

# De quanto em quanto tempo o servidor.py recoleta sozinho, em minutos.
INTERVALO_COLETA_MINUTOS = 120

# Cambio isolado, sem recoletar navios. Em minutos.
INTERVALO_CAMBIO_MINUTOS = 30

# Porta do servidor local (python servidor.py).
PORTA_SERVIDOR = 8777

# Quantos navios cada grupo mostra antes do botao "ver mais".
LIMITE_CARTOES = 6

# Janela da coluna "Esperado", em dias a frente.
JANELA_ESPERADOS_DIAS = 7

# ------------------------------------------------------------------- janelas
JANELA_MEDIA_DIAS = 45     # permanencia media por terminal
RECENTES_DIAS = 7          # navios ja saidos que continuam aparecendo no painel
TIMEOUT = 45               # segundos por requisicao

# -------------------------------------------------------------------- fontes
BASE_SPA = ("https://www.portodesantos.com.br/informacoes-operacionais/"
            "operacoes-portuarias/navegacao-e-movimento-de-navios/")

FONTES = {
    "atracados": {
        "url": BASE_SPA + "atracados-porto-terminais/",
        "tabela": "atracados",
        "rotulo": "Atracados - Porto/Terminais",
    },
    "programados": {
        "url": BASE_SPA + "atracacoes-programadas/",
        "tabela": "programados2",
        "rotulo": "Atracacoes Programadas",
    },
    "esperados_carga": {
        "url": BASE_SPA + "navios-esperados-carga/",
        "tabela": "esperados",
        "rotulo": "Navios Esperados - Carga",
    },
    "esperados_passageiros": {
        "url": BASE_SPA + "navios-esperados-passageiros/",
        "tabela": "esperados",
        "rotulo": "Navios Esperados - Passageiros",
    },
    "fundeados": {
        "url": BASE_SPA + "navios-fundeados/",
        "tabela": "fundeados",
        "rotulo": "Navios Fundeados",
    },
}

# Certificado intermediario extra, se a SPA publicar a cadeia incompleta.
# Vazio = usa a verificacao padrao do Python. Veja GITHUB.md.
CA_EXTRA = ""

CABECALHO_HTTP = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

# -------------------------------------------------------------------- cambio
MOEDAS = ["USD", "EUR", "GBP"]

PTAX_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
    "CotacaoMoedaPeriodo(moeda=@moeda,dataInicial=@dataInicial,"
    "dataFinalCotacao=@dataFinalCotacao)"
    "?@moeda='{moeda}'&@dataInicial='{ini}'&@dataFinalCotacao='{fim}'"
    "&$top=1&$orderby=dataHoraCotacao%20desc&$format=json"
)

# Agencias com leitor proprio em coleta_cambio.py.
# chave = nome que aparece no painel, valor = nome da funcao leitora.
AGENCIAS_AUTOMATICAS = {
    "MSC": "ler_msc",
}

MSC_URL = "https://mktbrazil.mscbr.com.br/"

# ----------------------------------------------------------------- terminais
# As tres primeiras abas do painel, nesta ordem. As demais entram por movimento.
TERMINAIS_DESTAQUE = ["BTP", "Santos Brasil", "DP World"]

# Tradução exata do codigo do berco (coluna "Local") para o nome do terminal.
MAPA_TERMINAIS = {
    "BTP I": "BTP",
    "BTP II": "BTP",
    "TECON 1.1": "Santos Brasil",
    "TECON 1.2": "Santos Brasil",
    "TECON II": "Santos Brasil",
    "TECON III": "Santos Brasil",
    "TECON IV": "Santos Brasil",
    "DP WORLD": "DP World",
    "DPW I": "DP World",
    "DPW II": "DP World",
    "EMBRAPORT": "DP World",
    "EPORT I": "Ecoporto",
    "EPORT II": "Ecoporto",
    "EPORT I / II": "Ecoporto",
    "EPORT III": "Ecoporto",
    "EPORT IV": "Ecoporto",
    "TERMAG": "Termag",
    "TEAG": "Teag",
    "TEG": "TEG",
    "TGG": "TGG",
    "TEV": "TEV",
    "CUTRALE": "Cutrale",
    "AGEO I": "Ageo",
    "AGEO II": "Ageo",
    "VALONGO": "Valongo",
    "OUTEIRINHOS 1": "Outeirinhos",
    "OUTEIRINHOS 2": "Outeirinhos",
    "OUTEIRINHOS 3": "Outeirinhos",
}

# Quando o codigo do berco nao esta no mapa acima, vale a primeira faixa que casar.
# (fragmento procurado no inicio do codigo, nome do terminal)
FAIXAS_BERCOS = [
    ("BTP", "BTP"),
    ("TECON", "Santos Brasil"),
    ("DP WORLD", "DP World"),
    ("DPW", "DP World"),
    ("EMBRAPORT", "DP World"),
    ("EPORT", "Ecoporto"),
    ("ULTRAFERTIL", "Ultrafértil"),
    ("ULTRAF", "Ultrafértil"),
    ("USIMINAS", "Usiminas"),
    ("ALAMOA", "Alamoa / Transpetro"),
    ("ALA", "Alamoa / Transpetro"),
    ("TERMAG", "Termag"),
    ("TEAG", "Teag"),
    ("TEG", "TEG"),
    ("TGG", "TGG"),
    ("CUTRALE", "Cutrale"),
    ("VALONGO", "Valongo"),
    ("I. BARNABE", "Ilha Barnabé"),
    ("ILHA BARNABE", "Ilha Barnabé"),
    ("SABOO", "Saboó"),
    ("ARMAZEM", "Cais Público"),
    ("TIPLAM", "Tiplam"),
    ("AGEO", "Ageo"),
    ("OUTEIRINHOS", "Outeirinhos"),
    ("COPERSUCAR", "Copersucar"),
    ("CSN", "Tecon CSN"),
    ("RUMO", "Rumo"),
    ("ADM", "ADM"),
    ("TRSP", "Alamoa / Transpetro"),
    ("TEVI", "TEV"),
    ("TEV", "TEV"),
    ("ILHA", "Ilha Barnabé"),
    ("CODESP", "Cais Público"),
    ("CAIS", "Cais Público"),
    ("AR ", "Cais Público"),
    ("SUG", "Cais Público"),
]

# Codigo que comeca com numero e berco do cais publico: "20/21", "12A-13/14", "38".
PREFIXO_NUMERICO_E_CAIS_PUBLICO = True

TERMINAL_DESCONHECIDO = "Não mapeado"

# ------------------------------------------------------------------ escopo
# Filtro do que interessa ao Grupo Ormac. Listas vazias = mostra o porto
# inteiro. Os trechos sao procurados sem acento e sem diferenca de caixa,
# entao "wilson" casa com "WILSON SONS S/A - COMERCIO...".
INTERESSE = {
    "agencias": [],     # ex.: ["WILSON SONS", "MSC", "LACHMANN"]
    "terminais": [],    # ex.: ["BTP", "Santos Brasil", "Ecoporto"]
    "mercadorias": ["CONTEINERES CHEIOS"]
    "navios": [],       # nome ou IMO, ex.: ["MSC MELINE", "9702077"]
}

# True abre o painel ja filtrado. False abre com o porto inteiro e deixa o
# botao "So o que interessa" para voce ligar quando quiser.
SOMENTE_INTERESSE = False

# --------------------------------------------------------------- fase 2 (line-ups)
# Ainda nao coletados. Trazem ETD previsto, deadline de carga e abertura de gate.
LINEUPS_TERMINAIS = {
    "Ecoporto": "https://op.ecoportosantos.com.br/externa/LineUpListaAtracacao",
    "Santos Brasil": "https://www.santosbrasil.com.br/v2021/lista-de-atracacao",
    "DP World": "https://www.embraportonline.com.br/Navios/Escala",
}
