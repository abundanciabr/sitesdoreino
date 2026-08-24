<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §3 — Ambiente (Windows, esta máquina)
     ID historico: §3.18  ·  referencias antigas "ARMADILHAS §3.18" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 3.18 Traefik serve `TRAEFIK DEFAULT CERT` para sempre depois de UMA falha do ACME

**Sintoma:** domínio no Modo B (Let's Encrypt direto, `certResolver: le` +
`tls.domains`), DNS já apontando para a VPS — conferido no **autoritativo**, não só
no resolver público — e o handshake continua devolvendo
`issuer=CN=TRAEFIK DEFAULT CERT` indefinidamente. Bater no site não adianta: 10
handshakes em 3 minutos não mudaram nada (medido).
**Causa:** o Traefik dispara a emissão ao **carregar a configuração**, não por SNI de
requisição. Se a primeira tentativa falhou (o caso típico: o deploy que ligou o Modo B
rodou **antes** de o mantenedor trocar o DNS), ele não re-tenta a cada acesso — só na
próxima recarga de config ou no ciclo de renovação (~24h). Ou seja: o cadeado fica
"quase pronto" por um dia inteiro, sem erro visível em lugar nenhum.
**Solução:** forçar recarga pelo caminho do projeto — **qualquer** diff em
`infra/traefik/**` (até um comentário) faz o `deploy-infra` recriar o container
(o `diff -r` do passo 3), e a tentativa acontece na hora. Foi o PR #81; o certificado
saiu em segundos depois do recreate.
**Como conferir sem abrir navegador** (o `-servername` é obrigatório — sem SNI o
Traefik devolve o default e você conclui errado):
```bash
echo | openssl s_client -connect <IP>:443 -servername <dominio> 2>/dev/null | openssl x509 -noout -issuer -dates
```
**Ordem que evita tudo isso:** DNS do domínio apontando para a VPS **antes** do merge
que liga o Modo B para ele. Se não der para garantir a ordem, conte com um segundo
merge de recarga — e diga isso ao mantenedor, para "ainda sem cadeado" não parecer
falha do trabalho.
**Origem:** meshcraft.top (23/08/2026), primeiro domínio direto da plataforma.
