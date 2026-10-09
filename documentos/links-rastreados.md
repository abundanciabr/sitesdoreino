---
titulo: Links rastreados de WhatsApp: como funcionam e onde ver
publico: false
ordem: 13
---

# Links rastreados de WhatsApp

## O que é e para que serve

Quando mandamos um link por WhatsApp, queremos saber se a pessoa abriu. Por isso
o sistema troca o endereço da mensagem por um endereço curto nosso, no formato
`https://meshcraft.top/r/<token>`. O token é um código de 10 letras minúsculas e
números, único para cada envio.

Quem toca no link passa por nós e segue para o destino. Nós só anotamos que
"alguém abriu este link".

**Decisão do mantenedor em 09/10/2026.** Ela substitui a nota antiga em
`services/mensageria/apps/jornadas/models.py` (linha 689), que dizia "nada de
link reescrito". Vale só para WhatsApp. **E-mail continua sem pixel** e sem
rastreio de abertura.

**Atenção:** um acesso nunca prova quem tocou. O link pode ter sido encaminhado
para outra pessoa. A contagem mostra sinal, não certeza.

## Como funciona, em quatro partes

1. **Mensageria.** Antes de enviar, troca cada endereço `https://...` do texto
   por `https://meshcraft.top/r/<token>`. Se a mesma mensagem for tentada de
   novo, os tokens são os mesmos. Anota o momento do envio (evento `link.enviado`).
2. **Funil.** Atende `/r/<token>`, pergunta à Mensageria para onde ir e manda a
   pessoa para lá (redirecionamento 302). Nunca grava cookie nem guarda cópia.
3. **Métricas.** Lê os eventos `link.enviado` e `link.acessado` e conta: quantos
   links foram enviados, quantos tiveram acesso provável, quantos ficaram sem
   acesso depois de 24 horas.
4. **Admin.** Mostra tudo em `/admin/links/` e, em cada conversa do CRM, no bloco
   "Links enviados e acessos".

Se a Mensageria não responder, o Funil mostra "Não deu para abrir o link agora.
Tente de novo em instantes." (erro 503 com pedido para tentar em 30 segundos). Se
o token não existe, é 404.

## Acesso provável, automático e indeterminado

Cada abertura é classificada:

- **Provável:** parece uma pessoa num navegador (começa com `Mozilla/` e aceita
  `text/html`). É o único tipo que conta como "abriu".
- **Automático:** o WhatsApp e outros robôs abrem o link sozinhos para montar a
  prévia. Isso não é a pessoa. Entram aqui o pedido HEAD e agentes como
  WhatsApp, facebookexternalhit, Googlebot, curl, wget, preview, crawler e
  parecidos.
- **Indeterminado:** não deu para saber (sem identificação do navegador, ou um
  padrão que não reconhecemos). Não conta como visita.

Cada acesso guarda o motivo da classificação, para conferir depois.

## Destinos e versões

Cada link aponta para um **destino**. O destino tem uma ou mais **versões**, e a
versão com o maior número é a atual.

- Link de uma mensagem comum cria sozinho um destino "automático" (nome = o
  endereço sem o que vem depois de `?` ou `#`) ou reaproveita um destino do mesmo
  site cuja versão atual é exatamente esse endereço.
- Em `/admin/links/` dá para cadastrar um destino com nome e endereço.
- **Trocar o endereço de um destino cria uma versão nova.** Os links já enviados
  passam a levar para a versão nova, porque o redirecionamento sempre usa a
  versão atual. As versões antigas ficam guardadas.
- Dá para arquivar e desarquivar um destino. Cada gesto fica na auditoria.

## O que NÃO é guardado

Não guardamos IP, telefone, nome nem o texto da mensagem. Nos eventos também não
vão telefone nem texto. Do acesso ficam: momento, método, identificação do
navegador (até 300 caracteres), classificação e motivo.

## O que NÃO é reescrito

- modelos aprovados da Meta (`services/mensageria/apps/conversas/envio.py`:
  só reescreve quando não há modelo): o texto é fixo e aprovado, mexer nele
  poderia reprovar o envio;
- e-mail: decisão de não colocar pixel nem trocar endereços;
- sino (avisos internos): não é mensagem para cliente;
- áudio: não há texto de link para trocar.

Endereços que já começam com `https://meshcraft.top/r/` ficam como estão. A
pontuação no fim (como `.`, `,` ou `)`) e marcas do WhatsApp (`*`, `_`, `~`) ficam
fora do link.

## Onde ver

**Tela `/admin/links/`** (menu "Links"):

- filtros por data (De, Até), campanha, destino e situação (todos, com acesso
  provável, sem acesso);
- resumo por destino (enviados, com acesso provável, sem acesso após 24 h,
  acessos automáticos);
- lista dos links enviados e cadastro de destinos e versões;
- **CSV** em `/admin/links/exportar.csv` (até 5.000 linhas, abre no Excel com
  acentos certos). Células que começam com `=`, `+`, `-` ou `@` são protegidas
  para não virarem fórmula.

**Na conversa do CRM:** o bloco "Links enviados e acessos" lista os links daquela
conversa. Se a leitura falhar, aparece "Sem leitura dos links agora." e a conversa
segue normal.

O Admin não guarda cópia: lê tudo da Mensageria e da Métricas na hora.

## Configuração em produção

Só nomes aqui. Os valores ficam nos arquivos de ambiente, nunca neste texto.

- `LINKS_URL_BASE` (Mensageria). Padrão: `https://meshcraft.top/r/`.
- `MENSAGERIA_API_URL` e `MENSAGERIA_API_TOKEN` (Funil), nos dois arquivos:
  `/opt/plataforma/env/funil.env` e `/opt/plataforma/env-celulas/funil.env`.
  A URL de produção é `http://mensageria:8000/api/mensageria`.
- `TOKENS_SOMENTE_LEITURA_FUNIL` (Mensageria), em `/opt/plataforma/env/mensageria.env`.
  O Funil usa um token só de leitura: ele consegue registrar acesso, mas não
  consegue criar nem mudar destinos.
- A ponte `meshcraft-funil-api` é o caminho do Funil até a Mensageria. O Funil
  não tem banco de dados.

## Limites conhecidos

- A classificação olha só o cabeçalho do navegador: pode errar (robô disfarçado
  de navegador conta como provável; pessoa com navegador incomum vira
  indeterminado).
- Quem clicou não é comprovável: o link pode ser encaminhado.
- O token tem 10 caracteres (letras minúsculas e números).

- Não existe evento de entrega. A contagem é sobre links **enviados**.
- É correlação, não causa: abrir o link não prova que a mensagem causou a visita.
- Menos de 30 envios num grupo: a Métricas marca "amostra insuficiente".
- Endereços com mais de 2.000 caracteres não são rastreados (ficam como estão).
- Só endereços `https://` são reescritos.
- Links só são marcados como enviados quando o WhatsApp aceitou a mensagem
  (aceito, enviado, entregue ou lido).

## Como testar de verdade

1. Abra `https://meshcraft.top/admin/whatsapp/` e envie para seu número um texto
   contendo `https://meshcraft.top/cursos/`.
2. No celular, a mensagem deve mostrar `https://meshcraft.top/r/<token>`. Toque
   nele: deve abrir a página de cursos.
3. Em `https://meshcraft.top/admin/links/` o link aparece como enviado e, em
   instantes, com acesso provável. A prévia do WhatsApp conta como automático.

## Como testar localmente

Da raiz do repositório, uma célula por vez:

```
python ci/testar_celula.py mensageria tests/test_links_rastreados.py
python ci/testar_celula.py funil tests/test_link_rastreado.py
python ci/testar_celula.py metricas tests/test_links_rastreados.py
python ci/testar_celula.py admin tests/test_links_rastreados.py
```

## Endereços dos arquivos principais

Mensageria:

- `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\services\mensageria\apps\links\models.py`
- `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\services\mensageria\apps\links\classificacao.py`
- `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\services\mensageria\apps\links\servico.py`
- `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\services\mensageria\apps\links\api.py`
- `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\services\mensageria\apps\conversas\envio.py`
- `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\services\mensageria\apps\jornadas\despacho.py`
- `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\services\mensageria\apps\whatsapp\api.py`

Funil:

- `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\services\funil\apps\core\links.py`
- `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\services\funil\apps\core\clients.py`

Métricas:

- `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\services\metricas\apps\fatos\links.py`
- `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\services\metricas\apps\fatos\api.py`

Admin:

- `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\services\admin\apps\core\links_rastreados.py`
- `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\services\admin\apps\core\templates\admin\links_rastreados.html`

Observação: estes endereços são do clone principal. Até o commit e o envio, o
trabalho está no clone `C:\Users\davia\abundanciabr\wt-links-20261009`.
