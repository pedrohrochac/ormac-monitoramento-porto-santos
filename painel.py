# -*- coding: utf-8 -*-
"""Monta o painel.html: kanban com uma coluna por terminal.

Dentro de cada coluna os navios ficam agrupados pela situacao:

    No cais      quem esta atracado agora, com a permanencia correndo
    Fundeado     quem chegou e espera vaga, com o tempo de espera
    Esperado     quem ainda navega, com a chegada prevista

Os botoes no topo ligam e desligam cada situacao, entao da para olhar
so a fila de fundeados de um terminal, por exemplo.
"""

from __future__ import annotations

import base64
import html
import os
from datetime import datetime, timedelta

import config
from armazenamento import escalas_do_periodo, fundeados_atuais, ultimas_taxas
from coleta_navios import ler_data, normalizar, terminal_de
from historico import duracao_texto, enriquecer, media_permanencia

SITUACOES = [("cais", "Atracado"), ("fundeado", "Aguardando atracação"),
             ("esperado", "Esperado"), ("saiu", "Desatracado")]

# Situacoes que comecam ligadas no filtro.
LIGADAS = ("cais", "fundeado", "esperado", "saiu")


def _data_txt(rotulo: str, texto: str) -> str:
    """Só mostra hora quando a fonte publicou hora, para não inventar 00:00."""
    if not texto or texto == "—":
        return ""
    return "%s %s" % (rotulo, texto)


def _e(valor) -> str:
    return html.escape(str(valor if valor not in (None, "") else "—"))


def _logo() -> str:
    caminho = config.LOGO
    if not caminho or not os.path.exists(caminho):
        return '<span class="marca-texto">%s</span>' % html.escape(config.EMPRESA)
    with open(caminho, "rb") as arquivo:
        dados = base64.b64encode(arquivo.read()).decode("ascii")
    tipo = "image/png" if caminho.lower().endswith(".png") else "image/jpeg"
    return '<img class="logo" src="data:%s;base64,%s" alt="%s">' % (
        tipo, dados, html.escape(config.EMPRESA))


def _quando(iso: str) -> str:
    if not iso:
        return ""
    for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(iso[:19], formato).strftime("%d/%m %H:%M")
        except ValueError:
            continue
    return iso


def _peso(valor: str) -> str:
    valor = (valor or "").strip()
    if not valor or valor == "0":
        return ""
    partes = []
    for pedaco in valor.split(" / "):
        pedaco = pedaco.strip()
        partes.append("{:,}".format(int(pedaco)).replace(",", ".")
                      if pedaco.isdigit() else pedaco)
    return " / ".join(partes) + " t"


def _interessa(c: dict) -> bool:
    """O cartão casa com alguma lista de config.INTERESSE?

    Sem nenhuma lista preenchida, tudo interessa: o filtro nasce desligado.
    """
    listas = config.INTERESSE
    if not any(listas.values()):
        return True
    campos = {
        "agencias": c.get("agencia_completa") or "",
        "terminais": c.get("terminal") or "",
        "mercadorias": " ".join([c.get("carga") or "", c.get("detalhe") or ""]),
        "navios": " ".join([c.get("navio") or "", c.get("imo") or ""]),
    }
    for chave, trechos in listas.items():
        alvo = normalizar(campos.get(chave, ""))
        for trecho in trechos:
            if trecho and normalizar(trecho) in alvo:
                return True
    return False


def _agencia_curta(agencia: str) -> str:
    if not agencia:
        return ""
    alto = agencia.upper()
    for corte in (" S/A", " LTDA", " S.A", " SERVICOS", " AGENCIA", " AGÊNCIA",
                  " OPERACOES", " AGENCIAMENTO", " SHIPPING", " MARITIME"):
        pos = alto.find(corte)
        if pos > 3:
            return agencia[:pos].strip(" .,-")
    return agencia.strip(" .,-")[:34]


# ------------------------------------------------------------------- cartoes

def _cartoes(con, agora: datetime) -> list[dict]:
    cartoes, vistos = [], set()

    desde = (agora - timedelta(days=config.RECENTES_DIAS)).isoformat(
        sep=" ", timespec="seconds")
    for escala in escalas_do_periodo(con, desde):
        dado = enriquecer(escala, agora)
        if not escala.get("aberta"):
            vistos.add(dado["chave_navio"])
            cartoes.append({
                "terminal": dado.get("terminal") or config.TERMINAL_DESCONHECIDO,
                "situacao": "saiu", "navio": dado.get("navio"),
                "onde": dado.get("local"), "carga": dado.get("carga") or "—",
                "detalhe": "", "agencia": _agencia_curta(dado.get("agencia")),
                "agencia_completa": dado.get("agencia") or "",
                "data": _data_txt("saiu", dado.get("saida_txt")),
                "marca": dado.get("permanencia_txt", ""), "faixa": "", "tag": "",
                "ordem": -(dado["saida_dt"].timestamp() if dado.get("saida_dt") else 0),
            })
            continue
        vistos.add(dado["chave_navio"])
        detalhe = " · ".join(x for x in [
            ("desc " + _peso(dado.get("descarga"))) if _peso(dado.get("descarga")) else "",
            ("emb " + _peso(dado.get("embarque"))) if _peso(dado.get("embarque")) else ""
        ] if x)
        cartoes.append({
            "terminal": dado.get("terminal") or config.TERMINAL_DESCONHECIDO,
            "situacao": "cais", "navio": dado.get("navio"),
            "onde": dado.get("local"), "carga": dado.get("carga") or "—",
            "detalhe": detalhe, "agencia": _agencia_curta(dado.get("agencia")),
            "agencia_completa": dado.get("agencia") or "",
            "imo": dado.get("imo") or "",
            "data": _data_txt("atracou", dado.get("atracacao_txt")),
            "marca": dado.get("permanencia_txt", "").replace(" (em curso)", ""),
            "faixa": "", "tag": "", "ordem": dado.get("local") or "",
        })

    for linha in fundeados_atuais(con):
        chave = linha["chave_navio"]
        vistos.add(chave)
        chegada = ler_data(linha.get("chegada"))
        espera = (agora - chegada) if chegada else None
        dias = espera.days if espera else 0
        cartoes.append({
            "terminal": terminal_de(linha.get("terminal_previsto") or ""),
            "situacao": "fundeado", "navio": linha.get("navio"),
            "onde": linha.get("terminal_previsto"),
            "carga": linha.get("mercadoria") or "—",
            "detalhe": " · ".join(x for x in [linha.get("operacao"),
                                              _peso(linha.get("peso"))] if x),
            "agencia": _agencia_curta(linha.get("agencia")),
            "agencia_completa": linha.get("agencia") or "",
            "data": _data_txt("desde", chegada.strftime("%d/%m %H:%M")
                              if chegada else ""),
            "marca": duracao_texto(espera),
            "faixa": "grave" if dias >= 21 else ("alerta" if dias >= 7 else ""),
            "tag": "programado" if linha.get("programado") else "aguardando",
            "ordem": -(espera.total_seconds() if espera else 0),
        })

    limite = agora + timedelta(days=config.JANELA_ESPERADOS_DIAS)
    cursor = con.execute("SELECT * FROM esperados ORDER BY chegada")
    for linha in cursor.fetchall():
        linha = dict(linha)
        if linha["chave_navio"] in vistos:
            continue
        chegada = ler_data(linha.get("chegada"))
        if not chegada or chegada > limite:
            continue
        vistos.add(linha["chave_navio"])
        faltam = chegada - agora
        if chegada.date() == agora.date():
            marca = "hoje"
        elif faltam.total_seconds() < 0:
            marca = "atrasado"
        elif faltam.total_seconds() < 86400:
            marca = "em " + duracao_texto(faltam)
        else:
            marca = "em %dd" % faltam.days
        cartoes.append({
            "terminal": terminal_de(linha.get("terminal_previsto") or ""),
            "situacao": "esperado", "navio": linha.get("navio"),
            "onde": linha.get("terminal_previsto"),
            "carga": linha.get("mercadoria") or "—",
            "detalhe": ("IMO " + linha["imo"]) if linha.get("imo") else "",
            "agencia": _agencia_curta(linha.get("agencia")),
            "agencia_completa": linha.get("agencia") or "",
            "imo": linha.get("imo") or "",
            "data": _data_txt("ETA", chegada.strftime("%d/%m %H:%M")
                              if ":" in (linha.get("chegada") or "")
                              else chegada.strftime("%d/%m")),
            "marca": marca, "faixa": "", "tag": "",
            "ordem": chegada.timestamp(),
        })

    return cartoes


def _cartao(c: dict) -> str:
    marca = " interessa" if c.get("interessa") else " fora"
    partes = ['<div class="cartao %s%s">' % (c["situacao"], marca)]
    partes.append('<div class="topo"><span class="nome">%s</span>%s</div>'
                  % (_e(c["navio"]),
                     ('<span class="tempo mono %s">%s</span>'
                      % (c["faixa"], html.escape(c["marca"]))) if c["marca"] else ""))
    partes.append('<div class="carga">%s</div>' % _e(c["carga"]))
    meta = " · ".join(x for x in [c.get("onde") or "", c.get("detalhe") or ""] if x)
    if meta:
        partes.append('<div class="meta mono">%s</div>' % html.escape(meta))
    if c.get("data"):
        partes.append('<div class="data">%s</div>' % html.escape(c["data"]))
    pe = []
    if c.get("agencia"):
        pe.append('<span class="ag">%s</span>' % html.escape(c["agencia"]))
    if c.get("tag"):
        pe.append('<span class="selo">%s</span>' % html.escape(c["tag"]))
    if pe:
        partes.append('<div class="pe">%s</div>' % "".join(pe))
    partes.append("</div>")
    return "".join(partes)


# -------------------------------------------------------------------- cambio

def _bloco_cambio(taxas: list[dict]) -> str:
    oficiais = {t["moeda"]: t for t in taxas if t["origem"] == "PTAX"}
    agencias: dict[str, dict] = {}
    for taxa in taxas:
        if taxa["origem"] != "PTAX":
            agencias.setdefault(taxa["origem"], {})[taxa["moeda"]] = taxa

    cartoes = []
    for moeda in config.MOEDAS:
        taxa = oficiais.get(moeda)
        valor = ("%.4f" % taxa["valor"]).replace(".", ",") if taxa else "—"
        rodape = ("PTAX · %s" % (taxa.get("extra") or _quando(taxa["momento"]))
                  ) if taxa else "sem cotação"
        cartoes.append('<div class="moeda"><span class="sigla">%s</span>'
                       '<span class="valor mono">%s</span>'
                       '<span class="rodape">%s</span></div>'
                       % (moeda, valor, html.escape(rodape)))

    blocos = []
    for nome in sorted(agencias):
        linhas = []
        for moeda in config.MOEDAS:
            taxa = agencias[nome].get(moeda)
            if not taxa:
                linhas.append("<tr><th>%s</th><td>—</td><td></td></tr>" % moeda)
                continue
            oficial = oficiais.get(moeda)
            delta = ""
            if oficial and oficial["valor"]:
                pct = (taxa["valor"] / oficial["valor"] - 1) * 100
                delta = "%+.2f%%" % pct
            linhas.append('<tr><th>%s</th><td class="mono">%s</td>'
                          '<td class="mono delta">%s</td></tr>'
                          % (moeda, ("%.4f" % taxa["valor"]).replace(".", ","),
                             delta))
        origem = agencias[nome][list(agencias[nome])[0]]["tipo"]
        blocos.append('<div class="agencia-bloco"><h2>%s <span class="selo">%s</span>'
                      '</h2><p class="nota">Quanto fica acima do PTAX.</p>'
                      '<table class="taxas"><tbody>%s</tbody></table></div>'
                      % (html.escape(nome), origem, "".join(linhas)))

    if not blocos:
        blocos.append('<div class="agencia-bloco"><p class="nota">Nenhuma taxa de '
                      'agência ainda. Use <code>python lancar_taxa.py Maersk USD '
                      '5,42</code>.</p></div>')

    return ('<section class="cambio"><div class="moedas">%s</div>'
            '<div class="lado">%s</div></section>'
            % ("".join(cartoes), "".join(blocos)))


# ----------------------------------------------------------------------- CSS

CSS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "painel.css"), encoding="utf-8").read() \
    if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "painel.css")) else ""


def montar(con, avisos: list[str] | None = None, com_servidor: bool = False) -> str:
    agora = datetime.now()
    cartoes = _cartoes(con, agora)
    for c in cartoes:
        c["interessa"] = _interessa(c)
    tem_filtro = any(config.INTERESSE.values())
    n_interesse = sum(1 for c in cartoes if c["interessa"])

    colunas: dict[str, dict] = {}
    for c in cartoes:
        colunas.setdefault(c["terminal"], {k: [] for k, _ in SITUACOES})
        colunas[c["terminal"]][c["situacao"]].append(c)

    for fixo in config.TERMINAIS_DESTAQUE:
        colunas.setdefault(fixo, {k: [] for k, _ in SITUACOES})
    for grupos in colunas.values():
        for chave, _ in SITUACOES:
            grupos.setdefault(chave, [])

    destaque = [t for t in config.TERMINAIS_DESTAQUE if t in colunas]
    resto = sorted([t for t in colunas if t not in destaque
                    and t != config.TERMINAL_DESCONHECIDO],
                   key=lambda t: (-sum(len(v) for v in colunas[t].values()), t))
    ordem = destaque + resto
    if config.TERMINAL_DESCONHECIDO in colunas:
        ordem.append(config.TERMINAL_DESCONHECIDO)

    blocos = []
    for terminal in ordem:
        grupos = colunas[terminal]
        total = sum(len(v) for v in grupos.values())
        media, quantos = media_permanencia(con, terminal)
        resumo = ("média %s · %d escalas" % (duracao_texto(media), quantos)
                  if media else "sem escala concluída ainda")
        partes = []
        for chave, rotulo in SITUACOES:
            lista = sorted(grupos[chave], key=lambda c: c["ordem"])
            if not lista:
                continue
            visiveis = "".join(_cartao(c) for c in lista[:config.LIMITE_CARTOES])
            extra = ""
            if len(lista) > config.LIMITE_CARTOES:
                sobra = len(lista) - config.LIMITE_CARTOES
                extra = ('<div class="resto" hidden>%s</div>'
                         '<button class="mais" type="button">ver mais %d</button>'
                         % ("".join(_cartao(c)
                                    for c in lista[config.LIMITE_CARTOES:]), sobra))
            partes.append(
                '<section class="grupo" data-situacao="%s">'
                '<h3><span class="ponto %s"></span>%s<span class="cont">%d</span>'
                "</h3>%s%s</section>"
                % (chave, chave, rotulo, len(lista), visiveis, extra))
        if not partes:
            partes.append('<p class="vazio">Nenhum navio nesta janela.</p>')
        blocos.append(
            '<article class="coluna" data-terminal="%s"%s>'
            '<header class="cab"><h2>%s</h2><span class="tot">%d</span></header>'
            '<p class="resumo">%s</p>%s</article>'
            % (html.escape(terminal),
               ' data-fixo="1"' if terminal in config.TERMINAIS_DESTAQUE else "",
               html.escape(terminal), total, html.escape(resumo), "".join(partes)))

    totais = {k: sum(len(colunas[t][k]) for t in ordem) for k, _ in SITUACOES}
    botoes = []
    for chave, rotulo in SITUACOES:
        botoes.append('<button type="button" data-situacao="%s" aria-pressed="%s">'
                      '<span class="ponto %s"></span>%s<span class="cont">%d</span>'
                      "</button>" % (chave, "true" if chave in LIGADAS else "false",
                                     chave, rotulo, totais[chave]))

    if tem_filtro:
        botoes.append(
            '<button type="button" id="escopo" class="escopo" aria-pressed="%s">'
            'Só o que interessa<span class="cont">%d</span></button>'
            % ("true" if config.SOMENTE_INTERESSE else "false", n_interesse))

    avisos_html = "".join('<div class="erro">%s</div>' % html.escape(a)
                          for a in (avisos or []))

    acao = ('<button type="button" id="atualizar">Atualizar agora</button>'
            if com_servidor else
            '<button type="button" id="recarregar">Recarregar</button>')
    nota = ("recoleta sozinho a cada %d min" % config.INTERVALO_COLETA_MINUTOS
            if com_servidor else "abra com <code>python servidor.py</code> "
            "para o botão coletar de verdade")

    return MODELO % {
        "titulo": html.escape(config.NOME_PAINEL),
        "empresa": html.escape(config.EMPRESA),
        "logo": _logo(),
        "agora": agora.strftime("%d/%m/%Y às %H:%M"),
        "nota": nota,
        "acao": acao,
        "css": CSS,
        "js": JS,
        "cambio": _bloco_cambio(ultimas_taxas(con)),
        "avisos": avisos_html,
        "botoes": "".join(botoes),
        "colunas": "".join(blocos),
        "n_terminais": len(ordem),
        "intervalo_ms": config.INTERVALO_COLETA_MINUTOS * 60 * 1000,
    }


def gravar(con, avisos: list[str] | None = None, caminho: str | None = None,
           com_servidor: bool = False) -> str:
    caminho = caminho or config.ARQUIVO_PAINEL
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(montar(con, avisos, com_servidor))
    return os.path.abspath(caminho)


JS = """
(function(){
  var CHAVE='monitor-santos-situacoes';
  var botoes=[].slice.call(document.querySelectorAll('.filtros button[data-situacao]'));
  function aplicar(){
    var ativos=botoes.filter(function(b){return b.getAttribute('aria-pressed')==='true';})
                     .map(function(b){return b.dataset.situacao;});
    var so=document.body.classList.contains('so-interesse');
    [].forEach.call(document.querySelectorAll('.grupo'),function(g){
      var visiveis=[].slice.call(g.querySelectorAll('.cartao')).filter(function(c){
        return !so || c.classList.contains('interessa');}).length;
      g.hidden = ativos.indexOf(g.dataset.situacao)===-1 || visiveis===0;});
    [].forEach.call(document.querySelectorAll('.coluna'),function(c){
      if(c.dataset.fixo){c.hidden=false;return;}
      c.hidden = ![].slice.call(c.querySelectorAll('.grupo')).some(function(g){
        return !g.hidden;});});
    try{localStorage.setItem(CHAVE,ativos.join(','));}catch(e){}
  }
  botoes.forEach(function(b){
    b.addEventListener('click',function(){
      var on=b.getAttribute('aria-pressed')==='true';
      var n=botoes.filter(function(x){return x.getAttribute('aria-pressed')==='true';}).length;
      if(on&&n===1)return;
      b.setAttribute('aria-pressed',on?'false':'true');
      aplicar();});});
  var salvo=null; try{salvo=localStorage.getItem(CHAVE);}catch(e){}
  if(salvo){var l=salvo.split(',').filter(Boolean);
    if(l.length)botoes.forEach(function(b){
      b.setAttribute('aria-pressed',l.indexOf(b.dataset.situacao)===-1?'false':'true');});}
  aplicar();

  [].forEach.call(document.querySelectorAll('.mais'),function(b){
    b.dataset.texto=b.textContent;
    b.addEventListener('click',function(){
      var resto=b.previousElementSibling; if(!resto)return;
      var aberto=!resto.hidden; resto.hidden=aberto;
      b.textContent=aberto?b.dataset.texto:'ver menos';});});

  var escopo=document.getElementById('escopo');
  function aplicarEscopo(){
    if(!escopo) return;
    var so = escopo.getAttribute('aria-pressed')==='true';
    document.body.classList.toggle('so-interesse', so);
    try{ localStorage.setItem('monitor-santos-escopo', so?'1':'0'); }catch(e){}
    aplicar();
  }
  if(escopo){
    var g=null; try{ g=localStorage.getItem('monitor-santos-escopo'); }catch(e){}
    if(g!==null) escopo.setAttribute('aria-pressed', g==='1'?'true':'false');
    escopo.addEventListener('click',function(){
      escopo.setAttribute('aria-pressed',
        escopo.getAttribute('aria-pressed')==='true'?'false':'true');
      aplicarEscopo();});
    aplicarEscopo();
  }

  var recarregar=document.getElementById('recarregar');
  if(recarregar) recarregar.addEventListener('click',function(){location.reload();});

  var atualizar=document.getElementById('atualizar');
  if(atualizar){
    atualizar.addEventListener('click',function(){
      atualizar.disabled=true; atualizar.textContent='Coletando...';
      fetch('/atualizar',{method:'POST'})
        .then(function(r){return r.json();})
        .then(function(d){
          atualizar.textContent = d.ok ? 'Pronto' : 'Falhou';
          setTimeout(function(){location.reload();}, 700);})
        .catch(function(){
          atualizar.textContent='Falhou'; atualizar.disabled=false;});});
  }
  setTimeout(function(){location.reload();}, INTERVALO_MS);
})();
"""

MODELO = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(titulo)s</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo+Narrow:wght@600;700&amp;family=IBM+Plex+Mono:wght@400;500&amp;family=Source+Sans+3:wght@400;600;700&amp;display=swap">
<style>%(css)s</style></head><body>
<div class="faixa-marca"><div class="faixa-interna">%(logo)s
<span class="faixa-tag">Comércio exterior · Porto de Santos</span></div></div>
<div class="envoltorio">
<header>
  <div><h1>%(titulo)s</h1>
  <p class="sub">Cada coluna é um terminal. Dentro dela, os navios aparecem na
  ordem do ciclo: no cais, fundeados esperando vaga, e os esperados que ainda
  estão navegando.</p></div>
  <div class="atualizar"><span class="prox">Atualizado em <b>%(agora)s</b><br>
  %(nota)s</span>%(acao)s</div>
</header>
%(cambio)s
%(avisos)s
<div class="filtros"><span class="rot">Mostrar</span>%(botoes)s
<span class="rot" style="margin-left:auto">%(n_terminais)d terminais</span></div>
<div class="board">%(colunas)s</div>
<footer>
<b>Fundeado</b> é o navio que já chegou a Santos e está ancorado fora do porto
esperando berço. O tempo no cartão conta da chegada ao fundeadouro até agora:
amarelo passa de uma semana, vermelho passa de três.
<b>Esperado</b> é o que ainda está navegando, com o terminal de destino que a
agência declarou. Fonte dos navios: Autoridade Portuária de Santos.
Câmbio oficial: PTAX/Banco Central.
</footer>
</div>
<script>%(js)s</script></body></html>"""

JS = JS.replace("INTERVALO_MS", "%(intervalo_ms)d")
MODELO = MODELO.replace("%(js)s", "JSPLACEHOLDER")


def _montar_modelo():
    return MODELO.replace("JSPLACEHOLDER", JS)


MODELO = _montar_modelo()
