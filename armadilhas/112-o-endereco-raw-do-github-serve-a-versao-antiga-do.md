# O endereço `raw.githubusercontent.com/.../main/...` serve a versão ANTIGA do script — às vezes

**Sintoma:** você mergeia a correção de um script de provisionamento, entrega ao
mantenedor a linha de sempre —

```
curl -fsSL https://raw.githubusercontent.com/<dono>/<repo>/main/infra/<script>.sh -o /tmp/p.sh && bash /tmp/p.sh
```

— e ele roda **a versão anterior**. Para ele isso não aparece como cache: aparece
como *"o script não funcionou"*, ou pior, como um script que faz exatamente o que
você acabou de consertar. Nenhuma mensagem indica que o arquivo é velho.

**Causa:** o `raw.githubusercontent.com` é servido por um cache de borda
(Varnish) com **`Cache-Control: max-age=300`** — cinco minutos. Medido nos
cabeçalhos, em 25/08/2026:

```
Cache-Control: max-age=300
Via: 1.1 varnish
X-Served-By: cache-gru-sbgr1930054-GRU
Expires: Tue, 25 Aug 2026 19:28:50 GMT
```

E a referência `/main/` é justamente a que envelhece: ela é um ponteiro móvel, e
o cache guarda o **conteúdo** que aquele ponteiro tinha. A URL fixada num SHA de
commit (`/8da31abe6322/...`) nunca serve conteúdo velho, porque o par
(SHA, caminho) é imutável.

## O que torna esta armadilha pior do que parece: ela é INTERMITENTE

Duas medições no mesmo dia, em sessões diferentes, com o mesmo procedimento:

| Sessão | Depois do merge | O que `/main/` serviu |
|---|---|---|
| lote da Caixa (PR #184) | imediato, e de novo aos 45 s, 90 s e ~2 min | a versão **ANTIGA** (`CHAVES_QUE_EU_GERO` ausente) |
| lote da área admin (PR #186) | imediato | a versão **NOVA**, `Source-Age: 0`, byte a byte igual à `main` |

Quem testar **uma vez** e vir conteúdo fresco vai concluir, de boa-fé, que o
problema não existe — e escreverá isso num documento. É a mesma classe do
falso-verde: a medição única confirma a hipótese confortável.

**Não caia na regra errada.** "Espere 5 minutos depois do merge" é conselho ruim
por dois motivos: às vezes é desnecessário (a segunda medição acima), e às vezes
não basta (a primeira ainda estava velha depois de dois minutos de espera).

## Solução

**Confira o conteúdo servido, não o relógio.** Antes de entregar a linha a um
humano, baixe do MESMO endereço que ele vai usar e procure uma marca que só
existe na versão nova:

```bash
curl -s https://raw.githubusercontent.com/<dono>/<repo>/main/infra/<script>.sh \
  | grep -c '<marca da versão nova>'      # 0 = ainda é a velha, NÃO entregue
```

A "marca" é qualquer string que a correção introduziu — o nome de uma variável
nova, uma frase da mensagem de erro nova. Cabe numa linha e responde a pergunta
certa: *o que ele vai baixar é o que eu consertei?*

Se estiver velho, as saídas são esperar e remedir, ou entregar a URL **fixada no
SHA** do commit — que é o caminho certo quando a linha é para uma execução única.
Para um script que a pessoa vai rodar de novo no futuro (*"trocar quem aprova é
rodar esta mesma linha com outro e-mail"*), `/main/` continua sendo o endereço
certo; o que muda é só a conferência antes de entregar.

## Por que isto importa neste projeto em particular

O padrão "passo do mantenedor = script versionado + uma linha de invocação"
nasceu em 24/08/2026, depois de um bloco de colar falhar **três vezes seguidas**
com ele — e é hoje o único formato aprovado para pedir algo à mão
(`ARMADILHAS-OPERACAO.md` §1, H18–H21). Este cache é a única peça daquele padrão
que o agente **não** controla: o script está certo no Git, o `bash -n` passa, os
guardas passam — e mesmo assim o que chega na VPS pode ser outro arquivo.

**Origem:** lote 4 da Caixa de Sugestões, 25/08/2026, ao entregar a trava de
deriva do `provisionar-sugestoes.sh` (PR #184). A segunda medição veio da sessão
da área administrativa, que rodou o mesmo teste no PR #186 e obteve o resultado
oposto — e foi essa divergência, não o cache em si, que virou a lição.
