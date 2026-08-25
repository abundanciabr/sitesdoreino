# DECISÃO — a célula de identidade nasce agora (o login sai da Caixa)

> **Sessão de arquitetura com o mantenedor presente**, 25/08/2026 — o rito que a
> `DECISAO-onde-mora-a-sessao.md` §7.1 exige por escrito para criar esta célula.
> Palavras dele, na abertura: *"quero resolver a questão do login do site da
> maneira correta, onde o login poderá ser usado em todo o site como em qualquer
> site padrão e não apenas em uma parte e muito menos dentro de Caixa."*
>
> Este documento é a **lei** do assunto e complementa a decisão de 24/08 — não a
> revoga: aquela previu, por escrito, que a célula dedicada nasceria "quando a
> escola nascer, **ou antes, se este atrito incomodar**". Incomodou. E previu o
> preço da espera certo: *"mudar o respondedor é reapontar um endereço"* — é
> exatamente o que este caminho faz.

---

## 1. O que foi decidido

1. **Nasce a célula `identidade`** — dona do fluxo com o Google, do cookie de
   sessão do site (`meshcraft_sessao`, `Path=/`) e da resposta "quem é o dono
   desta sessão?" (`/interno/sessao`). A Caixa deixa de ter login próprio e
   passa a ser **consumidora** da mesma pergunta que o `funil` já fazia.
2. **O passo H19 morre sem ser executado.** O token do par `funil→sugestoes`
   nunca entrou nos envs da VPS — o mantenedor escolheu, com as opções na mesa,
   ir direto à célula própria em vez de ligar a costura provisória. O passo
   humano que o substitui é UM bloco único (banco + env + tokens da
   `identidade`), registrado como **H20** em `ARMADILHAS-OPERACAO.md` §1.
3. **A porta do site não confere matrícula.** Site padrão: qualquer conta
   Google com e-mail verificado entra — entrar significa apenas *ser
   reconhecido*. Quem decide SE PODE alguma coisa é a célula dona do recurso,
   na hora do recurso: a Caixa confere matrícula e staff **na participação**
   (era na porta dela; a porta agora é do site). É a consequência natural do
   invariante *reconhecer não é autorizar* (24/08, §4 — segue valendo palavra
   por palavra).

## 2. O que NÃO muda (herdado por escrito das decisões anteriores)

- **A tela de login mora no `funil`**, nos três idiomas (`/{idioma}/login`) —
  guarda mecânico proíbe célula nova de servir caminho com forma de idioma.
- **O contrato da pergunta é o mesmo** — `getSession`/`Session` (id opaco,
  nome, papel; **e-mail nunca**). Muda o `servers:` e quem assina — o
  consumidor troca endereço, não vocabulário.
- **O papel é derivado a cada requisição** (lista no env), nunca gravado; e o
  papel `professor` continua não existindo (nasce com a escola, lista própria).
- **Fail-OPEN para reconhecimento, fail-CLOSED para autorização** — célula de
  identidade fora do ar ⇒ o site mostra "Entrar" e a página abre; nenhuma
  permissão em nenhuma célula deriva da resposta de `/sessao`.

## 3. O desenho que evita a migração de dados (a parte nova)

A conta de 24/08 previa "6 FKs viram coluna opaca, com dado já em produção".
Este desenho **zera esse custo**:

- A `identidade` nasce com tabela própria (mesma forma: id opaco, e-mail único,
  nome). Nasce **vazia** — na virada todo mundo é deslogado uma vez (o cookie
  muda de assinatura, não de nome) e reentra com um clique.
- A Caixa **mantém** a tabela `Identidade` dela como snapshot local (Virtude da
  Lei 3: *snapshots são sagrados*): as 6 FKs de autoria continuam FKs locais,
  legais e íntegras. O casamento entre a pessoa central e a linha local é por
  **e-mail** — que a Caixa recebe pela resposta completa (§4). Sugestões, votos
  e comentários existentes **não perdem o autor**, sem uma linha de migração de
  dados em produção.

## 4. A resposta completa — e o degrau que protege o e-mail

`/interno/sessao/completa` devolve o que `/sessao` devolve **mais o e-mail** —
o dado que uma célula dona de recurso precisa para conferir as listas DELA.
Dois conjuntos de tokens, dois direitos:

| env da `identidade` | prova | quem tem |
|---|---|---|
| `TOKENS_ACEITOS_<PAR>` | quem chama (as duas operações) | `funil`, `sugestoes` |
| `TOKENS_COMPLETOS_<PAR>` | pode ver e-mail (`/completa`; sem ele, 403) | só `sugestoes` |

O `funil` não vê e-mail por desenho — ele quer um nome para o canto da página.

## 5. A escada de entrega (e por que nesta ordem)

| PR | célula/caminho | por quê nesta posição |
|---|---|---|
| 1 | gênese `services/identidade` + manifesto + rollback.yml + esta lei | H17 item (2): célula nasce COM rollback; `deploy-celula` fica vermelho até o PR 3 — esperado (`armadilhas/088`) |
| 2 | `contracts/identidade.openapi.yaml` + manifesto `required` | Rito §3, o caminho em dois tempos da própria Caixa (#137→#139) |
| — | **passo do mantenedor**: `infra/provisionar-identidade.sh` (banco + `env/identidade.env` + tokens dos dois pares) | ANTES do PR 3, senão o `deploy-infra` reprova em crashloop (lição H18). Escreve os env dos DOIS consumidores, então é pré-requisito dos PRs 4 e 5 também |
| 3 | `infra/` (compose + traefik + env exemplo + provisionamento) | o deploy que põe a célula no ar |
| **4** | **`sugestoes` vira consumidora** (porta central, snapshot por e-mail) | o "muito menos dentro de Caixa" do mandato — e vem ANTES do site, ver a nota abaixo |
| **5** | **`funil` reaponta** (env + chaves de erro na tela de login) | a mudança que 24/08 prometeu barata: `enderecos.py` + env |

O `/interno/sessao` da Caixa fica **deprecado e inerte** ao fim da escada
(nenhum consumidor, nenhum cookie que ele saiba ler); a remoção do contrato
dela é um Rito §3 futuro, registrado como dívida — não trava nada.

### Por que a Caixa vem ANTES do site (corrigido em 25/08/2026)

A ordem original desta tabela era o inverso, e a auditoria de duas bancas
mostrou que ela abria uma janela ruim entre os dois merges. Enquanto a Caixa
ainda tem login próprio E o site já aponta para a porta central, **duas
células assinam o MESMO cookie** (`meshcraft_sessao`, `Path=/`) com **chaves
diferentes**: entrar pelo site desloga da Caixa, entrar pela Caixa desloga do
site — um cabo de guerra, sem erro em lugar nenhum, e que não fecha sozinho
se o merge seguinte reprovar.

Invertendo, a janela vira o oposto: a Caixa para de assinar imediatamente (há
guarda: `test_inv_caixa_nao_assina_sessao.py`) e passa a consumir a
`identidade`; o site ainda pergunta ao `/interno/sessao` da Caixa, que já está
inerte, e portanto mostra "Entrar" para todo mundo — inclusive para quem
acabou de entrar. É **degradação cosmética, fail-open, com a página abrindo
normal** — exatamente o modo de falha que o §4 escolheu tolerar. Trocar um
cookie disputado por um cabeçalho desatualizado por alguns minutos é troca
óbvia.

## 6. O que fica decidido para o próximo agente

1. **Não** dê à `identidade` rota com forma de idioma, página HTML ou consulta
   de matrícula — cada uma dessas três já tem casa, e é outra.
2. **Não** use `papel` (nem o e-mail da resposta completa) como autorização
   pronta: a resposta diz quem é; cada célula decide o que essa pessoa pode,
   nas listas e regras dela.
3. **Não** acrescente par a `TOKENS_COMPLETOS_*` sem registrar AQUI o porquê —
   e-mail é o dado que a EVO-01 §3 concentrou numa linha; cada par novo com
   acesso a ele alarga a superfície de dado pessoal.
4. A partir do PR 5, sessão da Caixa é a do site: **nenhum código novo na
   `sugestoes` pode escrever `request.session`** (guarda lá) — quem grava o
   cookie `meshcraft_sessao` é só a `identidade`.

## 7. Estado

**Decidido em 25/08/2026.** Passo do mantenedor: o bloco H20 (único), entregue
no relatório da sessão de gênese.
