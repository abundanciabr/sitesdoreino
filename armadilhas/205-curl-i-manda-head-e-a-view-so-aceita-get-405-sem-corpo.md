---
schema_version: 2
armadilha: 205
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: medio
guarda:
  tipo: sino
  dono: ci/sino_das_armadilhas.py
sinal:
  - `405 Method Not Allowed`
  - `curl -sI`
---

# `curl -I` manda HEAD: numa view `@require_GET` isso é 405 SEM CORPO — e o cabeçalho que você leu não é o da página

**Sintoma.** Você acabou de mergear e deployar um conserto que muda um
**cabeçalho** de resposta. O deploy está verde, a imagem foi construída e o
container recriado. Você confere com o reflexo de sempre:

```bash
curl -sI https://meshcraft.top/docs/ | grep -i content-security-policy
```

e o cabeçalho vem **exatamente como era antes do conserto**. Dez minutos depois,
igual. Você começa a caçar deploy que não pegou, imagem velha, tag fixada na
VPS, cache de CDN — e não há nada disso.

**Causa.** `curl -I` manda **HEAD**, não GET. Uma view decorada com
`@require_GET` (ou `@require_safe` em algumas versões) responde **405 Method Not
Allowed** ao HEAD, com `Content-Length: 0`. Os cabeçalhos que você está lendo são
os do **405**, não os da página.

E aí qualquer cabeçalho **derivado do corpo** desaparece — porque não há corpo.
Foi exatamente o caso medido em 30/08/2026: o CSP que carrega o `sha256` do
`<style>` da página (`armadilhas/199`) sai sem hash nenhum no 405, já que não há
`<style>` para hashear. O conserto estava no ar o tempo todo.

O que torna isto especialmente traiçoeiro: o 405 **também** passa pelo mesmo
middleware de segurança, então ele traz um CSP de aparência perfeitamente
normal. Não é um erro visível — é a resposta certa para outra pergunta.

**Solução.** Meça com o MÉTODO que o navegador usa, e leia o cabeçalho da
resposta real:

```bash
curl -s -D - -o /dev/null https://meshcraft.top/docs/ | grep -i content-security
```

`-D -` despeja os cabeçalhos de um **GET** de verdade; `-o /dev/null` joga fora
o corpo. Confira a linha `HTTP/1.1 200` que vem junto: se ela disser 405, você
caiu nesta armadilha.

**A regra maior:** a prova de fora só vale se o instrumento fizer a MESMA
pergunta que o usuário faz (RETROSPECTIVA-FASE-D §3). Um HEAD não é a página, do
mesmo jeito que `docker compose ps` não é um deploy. Quando dois instrumentos
discordarem — aqui, um Chrome de verdade dizia "nenhuma recusa" enquanto o
`curl -I` dizia "cabeçalho antigo" —, **desconfie do instrumento antes de
desconfiar do sistema**: o navegador estava certo.
