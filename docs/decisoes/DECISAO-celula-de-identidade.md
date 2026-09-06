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
| `TOKENS_ACEITOS_<PAR>` | quem chama (as duas operações) | `funil`, `sugestoes`, `admin`, `cursos`, `pages` |
| `TOKENS_COMPLETOS_<PAR>` | pode ver e-mail (`/completa`; sem ele, 403) | `sugestoes`, `admin`, `cursos`, `pages` |

O `funil` não vê e-mail por desenho — ele quer um nome para o canto da página.

### O par `admin` — o registro que o §6.3 exige (25/08/2026)

O §6.3 abaixo proíbe acrescentar par a `TOKENS_COMPLETOS_*` **sem registrar
aqui o porquê**. Este é o registro do segundo par a receber esse direito:

**Quem:** a célula `admin`, a área administrativa
(`DECISAO-celula-admin.md`), a partir do H21.

**Por quê o e-mail, e não o id opaco:** a porta administrativa autoriza por
**lista de e-mails** (`ADMIN_EMAILS`), e o e-mail é o único identificador que o
mantenedor consegue gerir sozinho num env — ele não tem como descobrir, nem
conferir, um `Identidade.id` opaco de dentro de uma área em que ainda não
conseguiu entrar. A alternativa (autorizar por `ADMIN_IDS`) foi levantada pela
cadeira de IAM na auditoria de 25/08/2026, é melhor em superfície de dado
pessoal, e foi **descartada por esse custo de bootstrap** — com a ressalva
registrada lá: se um dia a lista nomear endereço em domínio administrado por
terceiro, quem administra aquele domínio cunha uma conta naquele endereço e
entra.

**O que este par NÃO ganha:** nada além de conferir a própria lista. A resposta
da `identidade` continua não autorizando coisa alguma (§4 da
`DECISAO-onde-mora-a-sessao`), e a área admin **não escreve** em célula
nenhuma — o token dela nas provedoras de métrica entra em
`TOKENS_SOMENTE_LEITURA_*`, que é assunto da fase 2.

**Escopo:** um e-mail por requisição, o da própria sessão do chamador. A
listagem de TODOS os e-mails da plataforma (a seção "Usuários", fase 4) é
autorização categoricamente maior, **não coberta por este registro** — ela
exige operação interna nova, Rito §3 e registro próprio aqui.

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
   - **`cursos` (05/09/2026, degrau 1.8 da sala de aula):** para perguntar à
     `alunos` se a pessoa está matriculada, que é por e-mail; o e-mail nunca é
     guardado nem exibido (a `Pessoa` da célula é espelho por id opaco, e a
     tela só mostra a própria pessoa, [INV-CUR-P1]). É a mesma razão da Caixa.
   - **`pages` (06/09/2026, degrau 06 da Prancheta do aluno):** pela mesma
     razão da `cursos`, e por nenhuma outra. A porta de `services/pages` só
     abre para quem tem matrícula ativa, essa resposta mora na `alunos`
     (`getStudentStanding`), e a `alunos` a dá por e-mail. O e-mail é usado
     nessa pergunta e DESCARTADO: esta célula não o guarda em campo nenhum e
     não o exibe em tela nenhuma (`services/pages/apps/core/porta.py`). Sem o
     degrau, a resposta completa devolve 403, a Prancheta fica sem o e-mail e
     fecha para todo mundo, inclusive para aluno matriculado, em silêncio. Os
     dois lados do par são escritos por
     `infra/provisionar-pares-da-prancheta.sh`, com o MESMO valor nas duas
     listas.
4. A partir do PR 5, sessão da Caixa é a do site: **nenhum código novo na
   `sugestoes` pode escrever `request.session`** (guarda lá) — quem grava o
   cookie `meshcraft_sessao` é só a `identidade`.

### 6.1 Registro de grau novo (31/08/2026): `TOKENS_SENHA_*`

`DECISAO-login-por-senha.md` acrescenta um grau de autorização IRMÃO de
`TOKENS_COMPLETOS_*` (não uma variação dele): `TOKENS_SENHA_*`, que autoriza
GRAVAR a senha de uma pessoa (`setPassword`/`resetPassword`), ao contrário
de `TOKENS_COMPLETOS_*`, que só autoriza LER o e-mail da sessão. Concedido a
`funil` (grava a senha escolhida em `/cadastro`) e a `admin` (reset manual
pelo mantenedor). Este parágrafo é o registro que o item 3 acima exige —
adaptado, porque o grau novo não é `TOKENS_COMPLETOS_*` em si, mas nasce do
mesmo espírito: nenhum grau de acesso cresce sem que este arquivo diga por
quê.

## 7. Estado

**Decidido em 25/08/2026.** Passo do mantenedor: o bloco H20 (único), entregue
no relatório da sessão de gênese.
