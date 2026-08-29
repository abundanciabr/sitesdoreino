# O `www.` serve o cert de fábrica — e chega até você como "o site está sem cadeado"

**Sintoma:** o mantenedor manda foto do aviso vermelho "Não seguro" no navegador
e pergunta se o site está com problema de cadeado. Você mede o domínio de fora e
está **tudo certo**: Let's Encrypt válido, cadeia completa até a raiz, HSTS
ligado, `http://` desviando para `https://`, zero conteúdo misto. Os dois fatos
são verdadeiros ao mesmo tempo — e a conversa trava aí.

**Causa:** o endereço com `www.` é OUTRO host, e a arquitetura multissítio esconde
isso. As rotas casam por CAMINHO em qualquer host, então o `www.` **chega** na
plataforma; mas TLS é escolhido por **SNI**, e host que não está em
`tls.domains` (`infra/traefik/dynamic/plataforma.yml`, router `funil`) recebe o
`TRAEFIK DEFAULT CERT` autoassinado do Traefik. O visitante leva
`NET::ERR_CERT_AUTHORITY_INVALID`; passando por cima do aviso, ainda pega o 404
do CONV-SITE, porque o `www.` não está no `infra/sites.json`. E quase ninguém
DECIDIU ter um `www.`: ele costuma existir no DNS como CNAME herdado do registrador.

**A leitura da barra de endereço que poupa três rodadas de conversa.** A foto que
o mantenedor manda já contém a resposta, no prefixo — e os dois casos parecem
iguais para quem não sabe onde olhar:

| O que aparece na barra do Chrome | O que é |
|---|---|
| `https://` **riscado de vermelho** + "Não seguro" | certificado recusado (é este caso) |
| **sem** `https://` nenhum, só o host + "Não seguro" | página em HTTP puro (cache velho, extensão, rede) |

Peça a foto COM a barra inteira antes de investigar. Sem essa leitura, o
diagnóstico de 29/08/2026 queimou três idas e vindas com o mantenedor — inclusive
uma em que ele testou o `www.` de propósito e eu li o teste dele como se fosse o
problema original.

**Solução — as duas peças, porque uma sozinha não serve:**
1. O `www.` entra como **SAN do mesmo certificado** (`sans:` sob
   `- main: <dominio>`), não como entrada nova. Desviar só é possível **depois**
   do TLS fechar: sem cadeado válido no `www.`, o visitante nunca chega a ver o 301.
2. Um **router de desvio** com `redirectRegex` para o domínio nu. Ele precisa de
   `service` mesmo sem usá-lo (exigência do Traefik); o middleware encerra antes.

**A cilada DENTRO da solução — a que o CI pegou:** o instinto é dar priority alta
ao desvio ("no `www.` nada é servido"). Com priority 200 o desvio come também
`/api/checkout`, e `ci/tests/test_rota_da_compra_existe.py` reprova na hora:
**301 num POST faz o navegador reemitir como GET e o pedido de compra morre no
caminho**. A faixa correta é estreita e as duas bordas doem — `> 10` para ganhar
dos prefixos de página (senão `/checkout` e `/entrar` são SERVIDOS no `www.` em
vez de desviados) e `< 20` para perder da API. Use **15**, e ponha
`&& !PathPrefix(`/api`)` na regra como cinto além do suspensório.

**E NÃO cadastre o `www.` no `infra/sites.json`:** o smoke do `deploy-infra`
exige **200 na raiz** de todo host listado, e a raiz do `www.` responde **301**
de propósito. Cadastrar derruba o deploy com um vermelho que não é defeito.

**Vale a `armadilhas/018` inteira junto:** mudar `tls.domains` muda o CONJUNTO de
domínios do certificado ⇒ o ACME pede um certificado NOVO **ao recarregar a
config**, nunca por acesso. Como todo diff em `infra/traefik/**` faz o
`deploy-infra` recriar o container, o merge já é o empurrão — mas se o DNS do
`www.` não estiver apontando para a VPS antes do merge, o autoassinado fica
servindo por ~24h e "ainda sem cadeado" parece falha do trabalho.

**Como conferir sem abrir navegador** (o `-servername` é obrigatório — sem SNI o
Traefik devolve o default e você conclui errado):
```bash
echo | openssl s_client -connect www.<dominio>:443 -servername www.<dominio> 2>&1 | grep -E "subject=|verify"
```

**Origem:** meshcraft.top (29/08/2026), relatado pelo mantenedor como "o site
está com problemas no cadeado?".
