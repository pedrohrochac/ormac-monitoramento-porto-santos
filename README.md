# Monitor Porto de Santos — Grupo Ormac

Acompanha o movimento de navios do Porto de Santos num kanban, com uma coluna
por terminal, e o câmbio do dia. Roda sozinho de 2 em 2 horas.

## O vocabulário, primeiro

O ciclo de uma escala tem quatro estados, e o painel usa exatamente esses nomes:

| Estado | Cor no painel | O que significa |
|---|---|---|
| **Esperado** | cinza | anunciado pela agência, ainda navegando |
| **Aguardando atracação** | âmbar | já chegou a Santos e está fundeado fora do porto, esperando berço |
| **Atracado** | verde | no cais, operando |
| **Desatracado** | vermelho | soltou amarras |

**Aguardando atracação** é o que mais importa no dia a dia: é a fila. Cada dia ali é
sobrestadia em potencial, custo de afretamento correndo sem a carga se mexer.
O painel conta esse tempo desde a chegada ao fundeadouro e pinta de amarelo
acima de uma semana, de laranja acima de três.

## Como o painel se organiza

**Uma coluna por terminal.** BTP, Santos Brasil e DP World ficam sempre nas três
primeiras posições, mesmo sem navio no momento. As demais entram por movimento.
A última é "Não mapeado", com os berços que ainda não têm dono no `config.py`.

**Dentro de cada coluna, um grupo por situação**, na ordem atracado, aguardando
atracação, esperado, desatracado. Cada cartão traz a data e a hora da mudança de
estado (atracou, desde, ETA, saiu) e ao lado quanto tempo já passou. Os botões
"Mostrar" no topo ligam e desligam cada situação, então dá para olhar só a fila
de espera do Ultrafértil, por exemplo. O navegador lembra a sua escolha.

**No cabeçalho de cada coluna**, a permanência média daquele terminal nos
últimos 45 dias.

**Câmbio fixo no topo:** PTAX oficial do Banco Central nas três moedas, e do
lado a taxa de cada agência com o desvio percentual sobre o PTAX. A MSC é lida
automaticamente; as outras entram por lançamento manual, e o painel marca a
origem com o selo `auto` ou `manual`.

## Instalação

Precisa do Python 3.9 ou mais novo ([python.org](https://www.python.org/downloads/)
— no Windows, marque "Add Python to PATH").

```
cd monitor-santos
pip install -r requirements.txt
```

## O jeito recomendado de usar: o servidor

```
python servidor.py
```

Isso faz tudo de uma vez: coleta na hora, abre o painel no navegador, recoleta
sozinho a cada 2 horas e deixa o botão **Atualizar agora** funcionando de
verdade. Clicar nele dispara uma coleta nova e recarrega a página.

O painel fica em `http://localhost:8777`. Enquanto o servidor estiver rodando
você não precisa de cron nem do Agendador de Tarefas. Ctrl+C para parar.

Se preferir só gerar o arquivo e abrir na mão:

```
python main.py                             coleta e escreve painel.html
python main.py --cambio                    só dólar/euro/libra
python lancar_taxa.py Maersk USD 5,42      lança taxa de agência manual
python lancar_taxa.py --listar             mostra as taxas registradas
python verificar_fontes.py                 diagnóstico das origens
```

Aberto como arquivo, o botão vira "Recarregar", porque um HTML solto não tem
como rodar Python. É por isso que o servidor existe.

Antes da primeira coleta você já pode ver o layout: abra
`testes/painel_simulado.html`.

## Agendar sem deixar terminal aberto

```
python instalar_agendamento.py
```

Detecta Windows ou Linux/Mac e usa a ferramenta nativa (Agendador de Tarefas ou
cron). Cria duas coisas:

- **Coleta completa** nos horários de `config.HORARIOS_COLETA_COMPLETA`, hoje de
  2 em 2 horas
- **Câmbio isolado** a cada `config.INTERVALO_CAMBIO_MINUTOS`, hoje 30 minutos.
  Só as moedas, sem recoletar navios: consulta rápida e leve.

Mudou os horários no `config.py`? Rode o instalador de novo, ele substitui o
agendamento anterior. Para desfazer: `python instalar_agendamento.py --remover`

**Uma coisa importante de verdade:** o robô roda no seu computador. Ele precisa
estar ligado no horário agendado.

## De onde vem cada campo

As cinco listas da SPA foram conferidas página por página antes de escrever o
coletor:

| Lista | O que dá |
|---|---|
| Atracados – Porto/Terminais | quem está no cais **agora**, com berço e carga |
| Navios Fundeados | quem aguarda atracação fora do porto, com agência, chegada e terminal de destino |
| Navios Esperados – Carga | Navio · Chegada · **Agência** · Mercadoria · Terminal · IMO |
| Navios Esperados – Passageiros | mesma estrutura |
| Atracações Programadas | Data · Hora · ETA · Local · Navio · IMO · Evento |

Dois detalhes que decidiram o desenho do banco.

**O navio some da lista de esperados quando atraca.** Por isso cada coleta salva
os esperados no SQLite: a ETA e a agência de um navio atracado vêm de uma coleta
anterior. E quando ele reaparece na lista com a chegada da *próxima* viagem, o
código escolhe a chegada mais recente que já aconteceu, nunca uma do futuro.

**A SPA não publica a hora exata da atracação nem da desatracação.** O monitor
resolve assim:

- **Atracação** = o evento `ATRACACAO`/`REATRACACAO` programado para aquele
  navio, quando existe. Sem isso, o momento da primeira coleta em que ele
  apareceu no cais.
- **Saída** = o momento da primeira coleta em que ele deixou de aparecer.

Hora deduzida desse jeito aparece com um til (`~`) na frente. Com coleta de 2 em
2 horas, a margem de erro da saída é de no máximo duas horas.

## Como acrescentar uma agência automática

1. Escrever um leitor em `coleta_cambio.py`. O `ler_msc` serve de molde: ele
   procura o código da moeda e pega o primeiro número depois dele, o que aguenta
   mudança de layout sem quebrar.
2. Registrar em `config.AGENCIAS_AUTOMATICAS`.

Enquanto isso, a agência fica no lançamento manual.

## Ajuste que depende de você

No `config.py`, `MAPA_TERMINAIS` e `FAIXAS_BERCOS` traduzem o código do berço
para o nome do terminal. O mapa foi montado com as listas reais de berços do
Porto, incluindo as formas alternativas que a SPA usa para o mesmo lugar
("BTP I" numa lista, "B.T.P. 1" noutra).

Faltam confirmar os berços do **DP World** e do **Tecon CSN**, que não tiveram
navio nas coletas feitas até agora. Rode uma coleta, olhe a coluna "Não mapeado"
e me diga a quem pertencem os berços que sobrarem. O `verificar_fontes.py` já
imprime o bloco pronto para colar.

## Estrutura dos arquivos

```
config.py                 tudo que muda mora aqui (horários, terminais, escopo)
.github/workflows/        o robô que roda de graça no GitHub
GITHUB.md                 como colocar no ar em 4 passos
servidor.py               serve o painel, recoleta a cada 2h, botão Atualizar
main.py                   coleta completa, ou --cambio para só câmbio
verificar_fontes.py       diagnóstico das origens
coleta_navios.py          lê as cinco listas da SPA
coleta_cambio.py          PTAX três moedas + leitores das agências
historico.py              calcula espera e permanência
armazenamento.py          banco SQLite
painel.py                 monta o kanban
painel.css                o estilo do painel, separado para você mexer
lancar_taxa.py            lançamento manual de taxa
instalar_agendamento.py   agenda tudo sozinho (schtasks / cron)
logo.png                  a logo do Grupo Ormac no painel (opcional)
testes/simular.py         roda o projeto inteiro sem internet e confere tudo
testes/fixtures/          páginas reais da SPA e da MSC, guardadas para o teste
```

`python testes/simular.py` é o teste de regressão: se a SPA mudar o layout e
você mexer nos leitores, ele diz na hora se algo quebrou.

## O link público

O jeito recomendado é o **GitHub Actions**: o coletor roda de graça nos
servidores do GitHub de 2 em 2 horas e o painel fica num endereço público, sem
depender do seu computador e sem consumir crédito nenhum. O passo a passo está
em **GITHUB.md**.

Existe também uma versão publicada no claude.ai, que é uma foto do painel.
A tarefa agendada que a atualizava está pausada, porque cada rodada precisava
passar as quase 300 linhas de navio pela leitura do modelo, e isso custa. O
procedimento continua guardado no projeto, em
`claude/publicar-painel/RUNBOOK.md`, caso você queira retomar.

## Filtrar o que interessa

No `config.py`, o bloco `INTERESSE` tem quatro listas: agências, terminais,
mercadorias e navios. Vazias, o painel mostra o porto inteiro. Preenchida
qualquer uma, aparece o botão "Só o que interessa", e os cartões que casam
ganham um traço no canto. Os trechos são procurados sem acento e sem diferença
de maiúsculas, e as listas se somam. Detalhes em GITHUB.md.

## Próximas fases

**Fase 2 — line-ups dos terminais.** Ecoporto, Santos Brasil e DP World publicam
o que a SPA não tem: ETD previsto, deadline de carga e abertura de gate. Os
endereços já estão em `config.LINEUPS_TERMINAIS`.

**Fase 3 — mais agências automáticas.** Depende de você me mandar os endereços,
como fez com a MSC.

**Fase 4 — alertas.** Avisar quando um navio que te interessa muda de estado, ou
quando a taxa de uma agência foge de uma faixa que você definir.
