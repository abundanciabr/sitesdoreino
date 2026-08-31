---
schema_version: 2
armadilha: 257
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  detector: services/funil/tests/test_avisos_no_celular.py
  motivo: "test_nenhum_pedido_de_permissao_abre_sem_um_toque reprova qualquer volta do caminho automatico: exige UM unico requestPermission no arquivo servido, alcancavel so pelo clique no botao do cartaz."
sinal:
  - "Site bloqueado devido a excesso de solicitação de notificações"
  - "Malwarebytes Browser Guard"
  - "Heuristics: excesso de solicitação de notificações | ID: 10008"
  - "Notification.requestPermission"
---

# Pedir permissão de notificação sem gesto faz o antivírus bloquear o site INTEIRO

**Sintoma.** O visitante abre o meshcraft.top e, em vez do site, vê uma página
de bloqueio do antivírus dele: "Site bloqueado devido a excesso de solicitação
de notificações... pode conter atividades maliciosas" (Malwarebytes Browser
Guard, heurística ID 10008). O site está no ar, o deploy está verde, nenhum
teste falhou — e mesmo assim o aluno é aconselhado a NÃO entrar.

Aconteceu em 31/08/2026, o dia da inauguração para os alunos, horas depois de
o PR #753 pôr no ar o pedido de aviso que "abre sozinho onde o navegador
deixa" (registro 20260831-075). Quem viu e reportou foi o mantenedor, com
print, marcado URGENTE.

**Causa.** Duas coisas se somaram em `services/funil/static/funil/avisos.js`:

1. `Notification.requestPermission()` era chamado **ao carregar a página**,
   sem nenhum gesto da pessoa, para todo Chrome/Edge/Android logado.
2. Quando o navegador engolia o pedido (Chrome faz isso com pedido sem
   contexto: a promessa volta `"default"`), **nada era silenciado** — e a
   página seguinte pedia DE NOVO. Um aluno navegando gerava um pedido por
   página.

Pedir permissão de notificação sem gesto, repetidamente, é a assinatura
clássica dos sites de golpe que sequestram notificações para empurrar spam. As
ferramentas de segurança (Malwarebytes, e heurísticas parecidas em outros
antivírus) caçam exatamente esse padrão e bloqueiam o DOMÍNIO inteiro, não só
o pedido. O próprio Chrome já pune o padrão de forma mais branda: engole a
caixa e mostra um ícone quase invisível na barra.

**Solução.** A caixa do navegador só nasce de um TOQUE no botão do cartaz
(elemento nosso, dentro da página), para todo navegador por igual, sem caminho
automático. É também o único desenho que funciona em iPhone e Firefox, que já
exigiam o gesto por regra da plataforma. Corrigido no PR que carrega esta
armadilha; o desejo original do mantenedor ("sem botão na página", registro
20260831-075) foi revertido por força maior, com o incidente registrado no
livro.

**Regra de bolso.** Permissão de navegador (notificação, localização, câmera,
microfone) se pede DENTRO de um clique, uma vez, e silencia a recusa. Pedido
automático na carga da página é comportamento de site malicioso aos olhos de
quem protege o visitante — e a punição é o bloqueio do domínio na frente dele.

**Como conferir.** Abrir o site num Chrome limpo (aba anônima, conta de teste
logada): nenhuma caixa de permissão pode aparecer sem clique. O guarda
mecânico é `test_nenhum_pedido_de_permissao_abre_sem_um_toque`.
