# Inventário de NOMES lido como guarda de COMPORTAMENTO: o teste fica vermelho quando o nome some, e verde quando a coisa quebra

**Sintoma:** existe um teste que lê o arquivo perigoso, tem nome de guarda, e fica
vermelho quando você mexe nele. Todo mundo — auditoria inclusive — conclui "essa
parte está coberta". Aí a mudança que realmente quebra o sistema passa **verde**,
porque ela não mexe no NOME de nada.

O caso medido, em `infra/traefik/dynamic/plataforma.yml`, contra o `origin/main` de
25/08/2026:

| mutação                                             | efeito real            | CI     |
|-----------------------------------------------------|------------------------|--------|
| apagar o bloco inteiro do router `checkout-api`      | ninguém compra         | 🔴     |
| `priority: 20` → `priority: 0` no `checkout-api`     | ninguém compra         | 🟢 !!  |
| `service: checkout` → `service: funil` no mesmo      | ninguém compra         | 🟢 !!  |

As duas verdes são o incidente de 22/08/2026 ("tudo mergeado e ninguém conseguia
comprar") reproduzido em **uma linha de YAML**, com `270 passed` na tela.

**Causa:** o único teste que lia a tabela de rotas
(`ci/tests/test_rotas_sem_forma_de_locale.py`) termina com um inventário por
igualdade exata:

```python
assert segmentos == {"", "quiz", "checkout", "alunos", "api", "forms", "entrar"}
```

Ele existe para **obrigar quem acrescenta rota a passar por ali** e olhar as duas
regras de verdade (forma de locale, colisão com idioma) — e cumpre isso bem. Mas:

1. Ele só enxerga **nomes/segmentos**, nunca comportamento: para onde a rota
   aponta, quem ganha a disputa de prioridade, em qual entryPoint atende — nada
   disso está no conjunto, então nada disso é medido.
2. O vermelho que ele dá quando a rota some é **acidental**, não uma proteção:
   quem apagasse a rota de propósito só precisaria atualizar a linha do conjunto
   para voltar ao verde. Um guarda que a própria mudança desarma não é guarda.
3. **O teste dizia isso de si mesmo, no comentário imediatamente acima do
   `assert`** — *"Esta igualdade é um INVENTÁRIO, não uma regra de segurança"* — e
   ainda assim uma auditoria inteira o leu como cobertura da rota da compra, e
   registrou a dívida com a descrição errada (`ARMADILHAS-OPERACAO.md` §9, item
   (a): dizia "apagar o router continua verde", quando apagar dá vermelho).

A classe, então, tem duas metades e as duas machucam: **o inventário é lido como
guarda** (falso conforto) e **o relato da falha é escrito sem medir** (a dívida
descreve o buraco errado, e quem for pagá-la vai construir a proteção errada).

**Solução — separe os dois papéis e diga qual é qual no nome do teste.**

1. **Inventário continua existindo, e continua útil**: ele é o pedágio que força
   revisão humana quando uma linha nova aparece. Não troque o `==` por `<=`, não o
   apague. `armadilhas/089` é sobre atualizá-lo direito.
2. **Ao lado dele, um guarda de COMPORTAMENTO**, que responde a pergunta do mundo
   real e não a pergunta do arquivo. Para roteamento, a pergunta é a que o próprio
   Traefik responde: *para uma requisição a `/api/checkout`, em cada domínio
   servido, QUEM ganha a disputa de prioridade — e esse vencedor aponta para o
   service certo, que existe, num entryPoint público?* Foi o que virou
   `ci/tests/test_rota_da_compra_existe.py` (302 passed no total; as três mutações
   acima ficam vermelhas nele).
3. **Encontre o alvo pelo COMPORTAMENTO, nunca pelo nome.** O guarda novo acha o
   router avaliando a REGRA contra um caminho sintético — renomear `checkout-api`
   não o fura. Guarda que procura por nome é inventário com outra roupa.
4. **Afirme a ORDEM, não o número.** "Quem casa `/api/checkout` tem de ganhar de
   quem casa `/`" sobrevive a uma renumeração legítima da escala de prioridades;
   `assert priority == 20` viraria mais um inventário.
5. **O teste de aceite do guarda é a mutação**, e ela é barata: mude UMA linha do
   arquivo perigoso, rode a suíte, exija vermelho, restaure. Se a mutação que
   quebra a produção não fica vermelha, o que você escreveu é decoração —
   independentemente de quantos testes passaram.

**Como reconhecer a classe fora do Traefik:** todo teste cujo `assert` é uma
igualdade de conjunto/lista de **identificadores** (nomes de rota, de arquivo, de
variável de ambiente, de migration, de endpoint) é inventário. Ele prova que a
lista não mudou — não prova que a coisa funciona. Pergunte sempre: *qual mudança
de uma linha quebra a produção sem alterar essa lista?* Essa mudança é o teste que
está faltando.

**Origem:** despacho `ci/rota-da-compra` (25/08/2026), fechando o buraco (a) da
AUD1. A auditoria tinha registrado o buraco pela descrição errada; medir por
mutação antes de escrever o guarda foi o que revelou que o alvo era outro — e mais
perigoso do que o relatado.
