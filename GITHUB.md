# Colocar o painel no GitHub, de graça

O painel passa a coletar sozinho de 2 em 2 horas nos servidores do GitHub e a
ficar no ar num endereço público. Não depende do seu Mac ligado, não depende do
app do Claude aberto, e não consome crédito nenhum por atualização.

Repositório público tem Actions e Pages gratuitos e ilimitados. Uma coleta
dessas leva menos de um minuto.

## Antes de começar, uma escolha

O endereço muda. Hoje o painel está num link do claude.ai; no GitHub ele passa a
ser `https://SEU-USUARIO.github.io/monitor-santos/`. São links diferentes, e o
GitHub não consegue publicar no claude.ai.

Se você já mandou o link antigo para alguém, mande o novo depois que estiver no
ar. Deixei a tarefa agendada do claude.ai pausada, não apagada: se preferir
voltar atrás, é só reativar.

Sobre privacidade: num repositório público, o **código** fica visível para
qualquer um. Os dados do painel são públicos de origem (é tudo da Autoridade
Portuária), mas a comparação de câmbio entre agências é sua. Se isso incomodar,
há duas saídas: deixar `config.AGENCIAS_AUTOMATICAS` vazio no repositório, ou
usar repositório privado, onde o Pages exige plano pago.

## Passo a passo

**1. Criar o repositório.** No GitHub, botão New repository. Nome
`monitor-santos`, visibilidade **Public**, e não marque nada para inicializar.

**2. Subir os arquivos.** No terminal, dentro da pasta do projeto:

```
git init
git add .
git commit -m "primeira versão"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/monitor-santos.git
git push -u origin main
```

**3. Ligar o Pages.** No repositório, Settings → Pages → em "Source", escolha
**GitHub Actions**. Não escolha "Deploy from a branch".

**4. Rodar a primeira vez na mão.** Aba Actions → "Painel Porto de Santos" →
botão "Run workflow". Leva menos de um minuto. Se passar, o endereço aparece em
Settings → Pages.

Daí em diante ele roda sozinho de 2 em 2 horas.

## O que o robô faz a cada rodada

Instala as dependências, roda `python main.py`, que baixa as cinco listas da SPA
e o câmbio, atualiza o banco e escreve o `painel.html`. Depois guarda o banco e
o painel no próprio repositório e publica no Pages.

O banco voltar para o repositório é o que faz a história acumular: é dele que
saem a permanência média por terminal, a hora de atracação deduzida e a coluna
Desatracado. Cada commit do robô é uma foto do porto, então o histórico do
repositório vira, de graça, um arquivo de como o porto estava a cada duas horas.

## Se a primeira rodada falhar

**Erro de certificado.** A SPA publica a cadeia de certificados incompleta. O
navegador se vira sozinho, o Python não. A mensagem vai dizer isso com todas as
letras. Para resolver, pegue o certificado intermediário:

```
openssl s_client -showcerts -connect www.portodesantos.com.br:443 \
  </dev/null 2>/dev/null | openssl x509 -outform PEM > ca-extra.pem
```

Junte esse arquivo ao pacote de certificados do Python e aponte `config.CA_EXTRA`
para ele. Nunca desligue a verificação.

**Erro de permissão no push.** Settings → Actions → General → Workflow
permissions → marque "Read and write permissions".

**O cron não dispara.** O GitHub pausa os agendamentos de repositórios sem
atividade por 60 dias. Um commit qualquer reativa. E ele desativa o agendamento
se o repositório ficar sem push por muito tempo, o que não acontece aqui porque
o próprio robô faz commit a cada rodada.

## Mudar a frequência

No `.github/workflows/painel.yml`, a linha `- cron: "5 */2 * * *"`. É UTC, mas
como o intervalo é de duas em duas horas, o fuso não muda nada. Para quatro em
quatro: `"5 */4 * * *"`.

## Filtrar o que interessa

No `config.py`, o bloco `INTERESSE`. Deixe as listas vazias e o painel mostra o
porto inteiro. Preencha qualquer uma e aparece o botão "Só o que interessa":

```python
INTERESSE = {
    "agencias":    ["WILSON SONS", "MSC", "LACHMANN"],
    "terminais":   ["BTP", "Santos Brasil", "Ecoporto"],
    "mercadorias": ["SUCOS", "CARGA GERAL"],
    "navios":      ["MSC MELINE", "9702077"],
}
SOMENTE_INTERESSE = True   # abre já filtrado
```

Os trechos são procurados sem acento e sem diferença de maiúsculas, então
`"wilson"` casa com `WILSON SONS S/A - COMERCIO, INDUSTRIA E AGENCIA...`. As
quatro listas se somam: o navio entra se casar com qualquer uma.

Com o filtro desligado o painel marca os cartões que interessam com um traço no
canto e apaga um pouco o resto, então dá para ver o porto inteiro sem perder de
vista o que é seu.
