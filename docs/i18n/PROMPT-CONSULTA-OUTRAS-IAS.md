# Prompt de consulta — i18n da plataforma (para colar em outras IAs)

Uso: copie TUDO abaixo da linha e cole em cada IA (ChatGPT, Gemini, etc.).
Traga as respostas para uma sessão do agente, que as confronta com o
`PLANO-I18N.md` e ajusta as decisões `[CONSULTA]` antes de implementar.

---

Sou dono de uma plataforma de sites e cursos, e quero uma segunda opinião
técnica sobre o desenho de internacionalização (i18n) dela. Responda em
português do Brasil. Seja direto: recomendação concreta + porquê + o que
evitar. Não precisa de código pronto; o desenho é o que importa.

## Contexto do sistema (resumido, mas fiel)

- **Um deploy, N domínios**: plataforma multissite em Django 5.x, dividida em
  células (microsserviços) — catálogo, funil (páginas públicas), checkout,
  alunos, leads, etc. Um Traefik na frente roteia por PREFIXO DE CAMINHO
  (`/quiz`, `/checkout`, `/alunos`); tudo que sobra cai na célula "funil"
  (catch-all), que serve a página certa olhando o Host: um middleware resolve
  `Host → Site` consultando o catálogo (site não cadastrado = 404). Sites são
  DECLARADOS num JSON versionado no Git; merge na main converge a produção a
  ele por pipeline.
- **Páginas**: templates Django + "ilhas" Alpine.js, mobile-first, SEM build
  step de front-end (sem Node, sem bundler). Textos hoje estão fixos nos
  templates, em português.
- **Quem trabalha no código são agentes de IA** (Claude Code e similares), em
  PRs pequenos: há um portão mecânico de CI que REPROVA PR com mais de 15
  arquivos alterados. A cultura do projeto é fail-closed: o que pode quebrar
  em silêncio vira teste que reprova o merge.
- **Objetivo imediato**: o site `meshcraft.top` (escola de criação de jogos)
  com padrão em INGLÊS e, desde já, `pt-br` e `es` — primeira página:
  `meshcraft.top/pt-br/cadastro`. Depois virão outros idiomas, inclusive
  variantes regionais (`pt-pt` etc.). Outros sites da plataforma continuam
  monolíngues em pt-br e NÃO podem mudar de comportamento.
- **Critérios de decisão**: escalável (dezenas de páginas e ~10+ idiomas sem
  dor), sustentável (sem passo manual recorrente), e operável por agentes de
  IA com velocidade — criar página nova ou idioma novo tem de ser um diff
  pequeno, legível e verificável mecanicamente por teste.

## O desenho que estamos inclinados a adotar (critique-o)

1. URL com prefixo de idioma, inglês (padrão do site) sem prefixo:
   `/cadastro`, `/pt-br/cadastro`, `/es/cadastro`; prefixo não habilitado
   para o site = 404.
2. Traduções em dicionários YAML por idioma dentro da célula
   (`traducoes/en.yaml`, `pt-br.yaml`, `es.yaml`), chaves com namespace por
   página (`cadastro.titulo`), template tag própria `{% t "chave" %}` —
   em vez do stack gettext do Django (`.po`/`.mo`, makemessages), que exige
   binários GNU gettext e falha aberto (msgid em silêncio) quando falta
   tradução.
3. Teste de CI que reprova o merge se alguma chave existir num idioma e
   faltar em outro (paridade total); em produção, chave ausente cai para o
   inglês com aviso em log.
4. Quais idiomas cada site tem é DADO declarado (no registro de sites), não
   `if` no código; site sem declaração segue monolíngue como hoje.
5. `<html lang>`, `hreflang` alternates, `x-default` e canonical por idioma
   emitidos pelo template base desde a primeira página.

## As perguntas

1. **URL**: prefixo com padrão-sem-prefixo vs todos-com-prefixo (com redirect
   na raiz) — o que envelhece melhor para SEO e cache/CDN? Redirecionar `/`
   por Accept-Language é boa ideia ou armadilha?
2. **YAML próprio vs gettext** no nosso contexto (agentes de IA traduzindo,
   sem build step, CI fail-closed): qual escala melhor? O que perdemos ao
   abrir mão do gettext (plurais, interpolação, RTL futuramente) e como
   mitigar barato? Existe uma terceira via melhor (fluent, i18next-style JSON,
   banco)?
3. **Estrutura de chaves**: namespace por página vs global vs híbrido —
   o que minimiza conflito de merge com vários agentes em paralelo e facilita
   tradução automática confiável?
4. **Fallback e variantes regionais**: quando existir `pt-pt`, vale árvore de
   fallback (`pt-pt → pt-br → en`) ou paridade total obrigatória por idioma?
   Prós e contras no nosso modelo de CI.
5. **SEO multilíngue**: além de hreflang/x-default/canonical, o que mais é
   essencial no dia 1 (sitemap por idioma? Content-Language? nada)? O que é
   mito?
6. **Roteamento**: nosso gateway roteia células por prefixo de caminho, então
   `/pt-br/checkout/...` cairia na célula errada. Para quando formos além das
   páginas do funil: idioma depois do prefixo da célula, regra regex no
   gateway, ou outra convenção? O que os grandes multissites fazem?
7. **Conteúdo que é dado** (nomes de produto/oferta em banco, por site):
   padrão recomendado para traduzir dados — tabela de traduções, JSON por
   locale na própria linha, serviço próprio? Critério para escolher?
8. **O que quebra em 10+ idiomas** que é barato decidir agora e caro
   corrigir depois? (encoding, ordenação, datas/números/moeda, tamanho de
   texto em UI, direção de escrita…)

Se discordar do desenho inclinado, diga exatamente qual peça trocaria e por
quê — contra-argumentos fortes valem mais do que confirmação.
