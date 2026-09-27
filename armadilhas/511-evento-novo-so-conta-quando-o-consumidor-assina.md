---
schema_version: 2
armadilha: 511
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
gatilho:
  - "contracts/eventos/*"
  - "services/*/apps/*/management/commands/consume_eventos.py"
licao: publicar um evento no relay nao faz nenhuma celula guarda-lo. Cada consumidor tem uma lista FECHADA de streams (STREAMS em consume_eventos.py); evento fora da lista trafega, o relay confirma, e ninguem escreve fato nenhum. Provedor e consumidor sao dois PRs do MESMO plano, nunca um "a metricas nao muda porque ja e generica".
guarda:
  tipo: nenhum
  motivo: nao ha uma regra geral que ligue todo contrato de evento a toda lista de streams de toda celula sem reescrever o desenho do relay; o que evita a queda e conferir, a cada evento novo, se algum STREAMS o inclui, e isso e leitura, nao maquina
sinal:
  - "funil.pagina-vista"
  - "STREAMS = "
---

# Evento novo só conta quando o consumidor o assina; provedor e consumidor no mesmo plano

**Data:** 26/09/2026 · **Onde:** todo PR que publica evento novo (RITOS.md,
Rito de Contrato) numa célula que não é a dona do livro de fatos · **Custo
evitado:** semanas de evento publicado em produção sem nenhuma linha gravada,
e a falsa sensação de que "a metricas já é genérica, não precisa mudar"

## Sintoma

A `DECISAO-a-pagina-real-antes-do-experimento.md` (19/09/2026) planejou sete
PRs em quatro células e disse, no §9, "O que esta decisão NÃO muda": **"A
`metricas` não muda. O livro de fatos recebe os quatro eventos novos como
recebe qualquer outro, e nenhum PR da escada toca nela."**

`funil.pagina-vista` foi publicado em produção seguindo essa premissa. O
relay confirmou a publicação, nenhum contrato reprovou, nenhum teste falhou.
E durante semanas nenhuma linha de `funil.pagina-vista` chegou ao livro,
porque `services/metricas/apps/fatos/management/commands/consume_eventos.py`
declara uma lista FECHADA:

```python
STREAMS = [
    "eventos.identidade.pessoa-cadastrada",
    "eventos.quiz.completado",
    "eventos.forum.topico-criado",
    ...
]
```

`funil.pagina-vista` (e os outros três eventos da mesma decisão) não estão
nessa lista. O `XREADGROUP` do worker nunca pede aquele stream, então nunca o
lê: não é erro, não é exceção, é o comportamento correto de uma lista fechada
que ninguém atualizou.

## Causa

O livro de fatos (`services/metricas`) parece genérico porque o modelo
`Evento` aceita qualquer `event_type` sem schema fixo (Lei 9, evento
carrega ID e versão). Essa generalidade é do **armazenamento**, não da
**assinatura**: o consumidor Redis Streams só lê os streams que ele mesmo
lista, por desenho, para poder confirmar deliverable e balancear carga com
`XREADGROUP` grupo por grupo. Nenhum contrato novo em `contracts/eventos/`
altera essa lista sozinho; a lista é código Python numa célula diferente do
provedor do evento.

Quem planeja "o evento novo cai no livro porque o livro já recebe qualquer
evento" está confundindo o armazenamento genérico com o pipeline de
ingestão, que é fechado por lista.

## Solução

**Evento novo com contrato em `contracts/eventos/` sempre vem acompanhado de
um PR (ou item explícito na mesma escada) que adiciona o stream a `STREAMS`
em `consume_eventos.py` de toda célula que precisa gravá-lo.** Provedor e
consumidor entram no mesmo plano de execução, nunca "a consumidora genérica
não muda":

1. Ao desenhar a escada de PRs de um evento novo, pergunte explicitamente:
   quem assina isto? Se a resposta é `services/metricas`, um PR (ou degrau)
   da escada altera `STREAMS`.
2. Para conferir hoje se um evento publicado está sendo ouvido:
   ```bash
   grep -n "<stream>" services/metricas/apps/fatos/management/commands/consume_eventos.py
   ```
   Sem saída, o evento trafega e morre no relay.
3. Depois de adicionar o stream, confira em produção (ou no ambiente de
   staging) que o `Evento.objects.filter(event_type="<stream>").exists()`
   vira verdadeiro depois da primeira publicação.

## O que NÃO fazer

Escrever "a metricas não muda" numa decisão de arquitetura só porque o
modelo de armazenamento é genérico. Generalidade de schema não é o mesmo que
assinatura de stream: a segunda é uma lista fechada e precisa de linha nova
a cada evento novo.

## Origem

`DECISAO-a-pagina-real-antes-do-experimento.md` (19/09/2026), evento
`funil.pagina-vista`, descoberto durante o fechamento do sistema de
experimentos (frente ESCRIVÃO, 26/09/2026) ao conferir `STREAMS` em
`services/metricas/apps/fatos/management/commands/consume_eventos.py` contra
a lista de eventos que a decisão previa. Relacionada: a frente F2 do mesmo
sistema de experimentos existe exatamente para fechar esta lacuna
(`consume_eventos.py` aprende a assinar `funil.*`).
