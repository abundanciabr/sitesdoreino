// =============================================================================
// GERADO por painel/gerar_manifesto.js — NÃO EDITE À MÃO.
// Para regenerar: node painel/gerar_manifesto.js
// =============================================================================
// O livro INTEIRO num arquivo só: 97 registros, um pedido.
// A fonte de verdade continua em painel/registros/, um arquivo por ocorrência;
// isto aqui é só o empacotamento que a página carrega.

// ---- 20260819-001-h3-trava-de-merge-nativa ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260819-001-h3-trava-de-merge-nativa",
  tipo: "pendencia",
  quando: "2026-08-19",
  titulo: "Ligar a trava de merge nativa do GitHub (agora é grátis)",
  detalhe: "O botão verde de merge do site do GitHub continua funcionando mesmo com tudo vermelho — a proteção nativa nunca foi ligada. Quando o pedido nasceu (19/08) ela era paga; desde que o repositório virou público (23/08), é grátis. Hoje quem segura é a catraca do robô (mergear.py, que recusa merge com check vermelho) e o portão de deploy, provado sob ataque. A trava nativa é o cinto extra por cima.\n\nNada quebra enquanto espera — mas é uma decisão sua, e só sua, no site do GitHub. Quando quiser, peça numa sessão: 'me guie para ligar a trava de merge' — sai o passo a passo com telas.",
  autoridade: "sessao",
  evidencia: "ARMADILHAS-OPERACAO.md, tabela §1, linha H3",
  verificado_em: "2026-08-26",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "info",
  frente: null,
  vence_em_dias: null
});})();
// ---- 20260819-002-h4-docker-junto-com-windows ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260819-002-h4-docker-junto-com-windows",
  tipo: "pendencia",
  quando: "2026-08-19",
  titulo: "Deixar o Docker Desktop iniciar junto com o Windows",
  detalhe: "Toda sessão de robô começa esperando 1 a 2 minutos o Docker Desktop acordar. A correção é uma caixinha nas configurações do Docker Desktop ('Start Docker Desktop when you sign in'), no seu PC — só você pode marcar.\n\nÉ o pedido mais antigo da fila. Nada quebra enquanto espera; só custa uns minutos por sessão.",
  autoridade: "sessao",
  evidencia: "ARMADILHAS-OPERACAO.md, tabela §1, linha H4",
  verificado_em: "2026-08-26",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "info",
  frente: null,
  vence_em_dias: null
});})();
// ---- 20260821-001-h7-rito-de-contrato-do-502 ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260821-001-h7-rito-de-contrato-do-502",
  tipo: "pendencia",
  quando: "2026-08-21",
  titulo: "Uma sessão COM você para registrar o 502 no contrato da célula do dinheiro (rito de contrato)",
  detalhe: "O código já está certo desde 21/08: quando o Mercado Pago falha, a célula do dinheiro responde 'deu erro' (502) em vez de fingir sucesso. Mas o contrato congelado — o documento oficial do que a célula pode responder — ainda não lista esse 502, e a regra que ele protege não está no livro de invariantes.\n\nMudar contrato é rito que exige a sua presença (é caminho protegido, com etiqueta própria). Risco de deixar como está: baixo, mas real — nenhum documento diz ao checkout que 502 significa 'tente de novo com a mesma chave'. Quando quiser, peça numa sessão: 'toque o rito de contrato do H7'.",
  autoridade: "sessao",
  evidencia: "ARMADILHAS-OPERACAO.md, tabela §1, linha H7 (código: PR 44, mergeado)",
  verificado_em: "2026-08-26",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "info",
  frente: null,
  vence_em_dias: null
});})();
// ---- 20260822-001-h8-cartao-de-teste-no-cofre ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260822-001-h8-cartao-de-teste-no-cofre",
  tipo: "pendencia",
  quando: "2026-08-22",
  titulo: "Guardar a credencial de teste do Mercado Pago no cofre do GitHub (era do pagamento — sem urgência)",
  detalhe: "Destravaria um teste diário automático de ponta a ponta da compra (hoje o teste do esqueleto só roda manualmente, quando alguém lembra). Só você pode colar a credencial no cofre do GitHub — segredo nunca passa pelo robô.\n\nSem urgência nenhuma: é da era do pagamento, que está pausada por sua ordem ('pagamento por último'). Fica aqui para não se perder — a caixa calculada não esquece.",
  autoridade: "sessao",
  evidencia: "ARMADILHAS-OPERACAO.md, tabela §1, linha H8",
  verificado_em: "2026-08-26",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "info",
  frente: null,
  vence_em_dias: null
});})();
// ---- 20260822-002-frente-vender-pausada ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260822-002-frente-vender-pausada",
  tipo: "frente",
  quando: "2026-08-22",
  titulo: "Pausada por sua ordem: pagamento por último",
  detalhe: "Nada deste capítulo se move até você dizer 'o site vai vender'. O que já está adiantado e não se perde: as credenciais de teste funcionam no servidor (um QR Pix real foi gerado em produção em 22/08) e o caminho 'pagou, virou matrícula' está provado. Quando você der a ordem, o capítulo começa do meio.\n\nO que fica para essa hora: a tela de pagar com cartão (robô), o aviso oficial de 'pagou' no painel do Mercado Pago + a senha no servidor (só você), a troca das chaves de teste pelas reais (só você), e a compra de teste completa com evidência — os critérios 2 e 4 da fase do esqueleto fecham juntos aí (item H16 da tabela).",
  autoridade: "mantenedor",
  evidencia: "Ordem de 22/08 registrada (memória do projeto e CLAUDE.md); detalhe técnico em ARMADILHAS-OPERACAO §1 H16",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "vender",
  vence_em_dias: null
});})();
// ---- 20260823-001-h15-porta-lateral-do-servidor ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260823-001-h15-porta-lateral-do-servidor",
  tipo: "pendencia",
  quando: "2026-08-23",
  titulo: "Fechar a porta lateral do servidor (segurança, item H15)",
  detalhe: "Quando o repositório virou público (23/08), o endereço do servidor (IP da VPS) ficou visível. Quem souber o endereço consegue bater direto no servidor, passando por fora da proteção. O conserto é um firewall na VPS — mas com cuidado: meshcraft.top é servido direto, e uma regra ingênua derrubaria o site. Quando você quiser fechar, peça numa sessão: 'monte o bloco de colar do H15' — sai um bloco único, com a janela certa rotulada.\n\nEste pedido ficou dias na gaveta 'sem pressa' de um painel que você não abre todo dia — foi o exemplo real de pedido perdido que a auditoria das consultorias encontrou. Por isso ele é um dos primeiros registros do livro.",
  autoridade: "sessao",
  evidencia: "ARMADILHAS-OPERACAO.md, tabela §1, linha H15",
  verificado_em: "2026-08-25",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: null,
  vence_em_dias: null
});})();
// ---- 20260823-002-retrotraducao-chave-paga ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260823-002-retrotraducao-chave-paga",
  tipo: "pendencia",
  quando: "2026-08-23",
  titulo: "Segunda conferência automática de tradução (precisa de chave de API paga)",
  detalhe: "O site fala 3 línguas e já barra sozinho tradução faltando, texto desatualizado e nome de marca traduzido por engano. Existe uma conferência extra possível — a retrotradução automática (traduzir de volta e comparar) — mas ela precisa de uma chave de API paga, e assinar serviço é decisão sua.\n\nSem ela, a conferência humana continua valendo. Nada quebra enquanto espera.",
  autoridade: "sessao",
  evidencia: "arquivos/painel-retomada.html, seção 6 (25/08)",
  verificado_em: "2026-08-25",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "info",
  frente: null,
  vence_em_dias: null
});})();
// ---- 20260825-001-frente-site-no-ar ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260825-001-frente-site-no-ar",
  tipo: "frente",
  quando: "2026-08-25",
  titulo: "No ar com prova: 3 idiomas, cadastro, login próprio em todo o site",
  detalhe: "meshcraft.top responde com cadeado, em inglês (na raiz), português e espanhol. A página de cadastro funciona, e dá para entrar e sair com a conta do Google em qualquer página. Provado de fora em 25/08: 17 verificações pela internet, 17 aprovadas — e a raiz respondeu 200 de novo em 26/08, medida desta máquina.\n\nO que falta aqui não é técnica — é conteúdo: a vitrine de verdade da escola (frente 'curso').",
  autoridade: "sonda",
  evidencia: "17/17 verificações externas (25/08, H20) + curl da raiz 200 em 26/08",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "site",
  vence_em_dias: 14
});})();
// ---- 20260825-002-frente-comunidade-caixa-no-ar ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260825-002-frente-comunidade-caixa-no-ar",
  tipo: "frente",
  quando: "2026-08-25",
  titulo: "A Caixa de Sugestões está no ar, com rosto e com a sua trava",
  detalhe: "Só aluno matriculado entra (conta do Google). O quadro de ideias funciona: ver, votar, sugerir — com aviso de ideia repetida, histórico por ideia, sininho de avisos dentro da Caixa e o mural 'o que vem por aí'. O corredor final tem a trava que é sua: nada sai de 'Planejado' sem autorização registrada no seu nome.\n\nO próximo passo grande (o sininho em todo o site, não só na Caixa) teve as 3 decisões respondidas por você em 25/08 e está na fila dos robôs.",
  autoridade: "sonda",
  evidencia: "meshcraft.top/forms/sugestoes/ responde 302 para login (regra certa), medido em 25/08",
  verificado_em: "2026-08-25",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: 14
});})();
// ---- 20260825-003-frente-curso-e-sua ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260825-003-frente-curso-e-sua",
  tipo: "frente",
  quando: "2026-08-25",
  titulo: "O capítulo que é SEU: o curso e a história que convence — ainda não começou",
  detalhe: "As aulas da escola de criação 3D para Roblox, a promessa, o preço, a página de vendas: nenhum robô escreve isso por você. As 4 consultorias de estratégia foram unânimes: o maior risco do projeto não é um erro técnico — é uma fortaleza perfeita que ninguém visita. Uma hora sua investida aqui vale mais que qualquer melhoria técnica.\n\nSem prazo e no seu ritmo. O nome está escolhido (Meshcraft Academy, 23/08); o domínio da Academy segue livre, sem registrar — sua decisão, quando quiser.",
  autoridade: "mantenedor",
  evidencia: null,
  verificado_em: null,
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "curso",
  vence_em_dias: null
});})();
// ---- 20260825-004-frente-fabrica-onda1-auditada ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260825-004-frente-fabrica-onda1-auditada",
  tipo: "frente",
  quando: "2026-08-25",
  titulo: "A fábrica de robôs: Onda 1 fechada e auditada; faltam 3 peças de bastidor",
  detalhe: "A esteira que constrói, testa e publica sozinha está madura: deploy automático com portão provado sob ataque, volta-atrás cronometrada em 76 segundos, e a auditoria AUD1 fechou a Onda 1 do plano de aceleração provando os guardas por sabotagem proposital.\n\nFaltam 3 peças, todas de bastidor e nenhuma depende de você: o vigia dos vigias (confere se cada teste-guarda prometido existe), o alarme completo da linha principal, e a partida em 1 comando. Estão na fila dos robôs.",
  autoridade: "rito",
  evidencia: "AUD1 (auditoria da Onda 1, 25/08) + rollback 76s cronometrado (23/08)",
  verificado_em: "2026-08-25",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: 21
});})();
// ---- 20260825-005-decisao-sininho-3-respostas ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260825-005-decisao-sininho-3-respostas",
  tipo: "decisao",
  quando: "2026-08-25",
  titulo: "Você respondeu as 3 perguntas do sistema de avisos (o sininho em todo o site)",
  detalhe: "As três escolhas que travavam o plano das notificações foram respondidas por você em 25/08: (1) SIM — nasce uma peça nova só para avisos; (2) SIM — o aviso pode chegar 'em segundos' em vez de 'no mesmo instante' (fica rastreável e não se perde); (3) a primeira versão avisa só sobre a Caixa de Sugestões, já desenhada para os outros assuntos entrarem depois como pedacinho, não reforma.\n\nO raciocínio completo de cada escolha está preservado na fotografia do Roadmap de 25/08 (a versão de antes do lote), na prateleira da memória.",
  autoridade: "mantenedor",
  evidencia: "docs/notificacoes/PLANO-MESTRE.md + fotografia do Roadmap de 25/08",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: null,
  vence_em_dias: null
});})();
// ---- 20260826-001-reforma-dos-paineis-aprovada ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-001-reforma-dos-paineis-aprovada",
  tipo: "decisao",
  quando: "2026-08-26",
  titulo: "Você aprovou a reforma dos painéis: registros no Git e reforma completa",
  detalhe: "Depois de 8 rodadas de consultoria externa (5 IAs, análise completa no veredito), você respondeu SIM às duas perguntas: (1) os registros do painel passam a morar no repositório, onde as travas do projeto os protegem; (2) a reforma é a completa — livro de ocorrências + painel calculado — e não só a fusão dos painéis antigos. Este é o primeiro registro do livro que essa decisão criou.",
  autoridade: "mantenedor",
  evidencia: "docs/paineis/VEREDITO-DAS-CONSULTORIAS.html",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: null,
  vence_em_dias: null
});})();
// ---- 20260826-002-nota-fila-dos-robos ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-002-nota-fila-dos-robos",
  tipo: "nota",
  quando: "2026-08-26",
  titulo: "A fila dos robôs em 26/08 — nada nela depende de você",
  detalhe: "Em ordem de proposta, tudo trabalho de robô e nada toca pagamento: (1) o sistema de avisos em todo o site — suas 3 respostas de 25/08 destravaram o plano; (2) apresentar o site à Caixa (item H19: as duas peças ainda guardam a mesma pessoa em fichas separadas — as três entregas já estão decididas em documento); (3) as 3 peças da fábrica (vigia dos vigias, alarme completo da linha principal, partida em 1 comando); (4) o teste que faltou na rota da compra (proteção da plataforma, achado da auditoria AUD1 — não é desenvolvimento de pagamento); (5) o fuso horário das células com página na rua.\n\nPara despachar: 'Leia RUNBOOK-LOTES.md e toque um lote com [os itens que quiser]'.",
  autoridade: "sessao",
  evidencia: "arquivos/painel-retomada.html §5 (25/08) + ARMADILHAS-OPERACAO §1 H19",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: null,
  vence_em_dias: 10
});})();
// ---- 20260826-003-nota-o-que-a-obra-deixou-de-fora ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-003-nota-o-que-a-obra-deixou-de-fora",
  tipo: "nota",
  quando: "2026-08-26",
  titulo: "A reforma dos painéis: o que ficou DE FORA da primeira obra, de propósito e declarado",
  detalhe: "A obra de 26/08 entregou o livro de ocorrências, a porta única, a trava no robô de conferência e as lápides. Três peças recomendadas pelas consultorias ficaram para despachos futuros, e este registro existe para elas não sumirem em silêncio: (1) registros escritos pela máquina — o robô do GitHub registrando merge e publicação sozinho, sem passar por sessão nenhuma; (2) a exigência dura 'trabalho sem registro não mergeia' — precisa de desenho fino sobre o que conta como trabalho; (3) gráficos que nascem do acúmulo de registros com o tempo (o gráfico de subida, os 4 números da fábrica) — o livro é novo, a matéria-prima ainda é curta.\n\nQuando alguém notar a falta de uma delas: não é esquecimento, é fila. Peça numa sessão que ela vira despacho.",
  autoridade: "sessao",
  evidencia: "docs/paineis/VEREDITO-DAS-CONSULTORIAS.html, seções 6 e 9",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: null,
  vence_em_dias: null
});})();
// ---- 20260826-004-obra-da-reforma-concluida ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-004-obra-da-reforma-concluida",
  tipo: "entrega",
  quando: "2026-08-26",
  titulo: "A reforma dos painéis foi executada: o livro de ocorrências está no ar",
  detalhe: "Os seis movimentos, todos mergeados com a esteira verde: (1) o livro de ocorrências e a porta única nasceram (PR 217); (2) os fatos vivos dos painéis antigos viraram registros (PR 218); (3) as 8 consultorias e o veredito entraram no Git (PR 219); (4) a muralha-do-painel entrou no robô de conferência — PR que toca o livro sem regenerar o manifesto reprova, e apagar o livro reprova (PR 220); (5) a lei mudou no CLAUDE.md: registrar é o gesto obrigatório, e nenhum fato mora em dois lugares (PR 221); (6) os painéis antigos viraram fotografias datadas na prateleira e lápides que apontam para cá.\n\nO seu jeito de usar: abra painel/painel.html com duplo clique (os atalhos antigos redirecionam sozinhos). Ficou de fora, declarado no registro 20260826-003: registros de máquina, a trava dura registro-por-PR, e os gráficos que precisam de histórico acumulado.",
  autoridade: "github",
  evidencia: "PRs 217, 218, 219, 220 e 221 — todos MERGED, mergeados pelo rito (mergear.py) com checks verdes",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: null,
  vence_em_dias: null
});})();
// ---- 20260826-005-auditoria-achou-documentos-com-o-mapa-velho ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-005-auditoria-achou-documentos-com-o-mapa-velho",
  tipo: "incidente",
  quando: "2026-08-26",
  titulo: "A auditoria achou uma falha real da obra: 7 documentos ainda mandavam usar o painel morto",
  detalhe: "A lei mudou no CLAUDE.md, mas a varredura dos documentos ficou de fora da obra — e ela estava no escopo (uma das consultorias avisou: 'a migração dos hábitos é parte da obra, não acabamento'). O pior caso era o PLAYBOOK.md, o PRIMEIRO documento que toda sessão lê: ele dizia que o agente NÃO consegue editar o painel por estar fora do Git — exatamente o contrário do que passou a valer. Uma sessão nova leria isso e iria atrás do painel morto.\n\nCorrigidos nesta varredura: PLAYBOOK.md, ARMADILHAS.md (a tabela 'onde cada coisa mora' e o bloco que explicava por que o painel não era versionado), ARMADILHAS-OPERACAO.md (as seções 7.2 e 7.4, que ensinavam o método antigo), PROMPTS-INICIAIS.md (2 lugares), RUNBOOK-LOTES.md (2 lugares), o molde de despacho da Caixa e uma nota no plano da área administrativa.\n\nFICA PARA DEPOIS, por regra da casa: services/checkout/LICOES.md e services/pagamentos/LICOES.md também citam o painel velho, mas são CÉLULAS DIFERENTES e a cerca do CI proíbe um PR tocar duas. São menções de passagem, sem instrução errada. Entram de carona no próximo despacho que tocar cada uma dessas células.",
  autoridade: "sessao",
  evidencia: "PR da varredura pós-reforma (busca por 'painel-fundacao|painel-roadmap|painel-dados|arquivos/painel' em todo .md versionado)",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: null,
  vence_em_dias: null
});})();
// ---- 20260826-006-auditoria-da-obra-veredito ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-006-auditoria-da-obra-veredito",
  tipo: "nota",
  quando: "2026-08-26",
  titulo: "Auditoria da reforma: tudo o que foi prometido está de pé, com 3 ressalvas declaradas",
  detalhe: "A obra foi auditada item a item contra o plano. Os 6 movimentos e as 6 regras estão executados e medidos: a porta não guarda nenhum fato próprio; nenhum controle finge gravar; nenhum dado vira HTML; verde exige prova; a caixa é calculada; o teto da capa se recusa a crescer. A auditoria achou e consertou uma falha real (7 documentos ainda mandavam usar o painel morto — registro 005).\n\nAS 3 RESSALVAS, todas declaradas e nenhuma escondida: (1) o painel NUNCA foi aberto num navegador de verdade — a extensão do Chrome não estava conectada; a costura sem prova é o carregamento dos registros pelo manifesto (a pré-visualização que o mantenedor viu tinha tudo embutido, então provou o desenho e as contas, não essa costura). Ele confirma em 10 segundos abrindo painel/painel.html. (2) A muralha-do-painel roda em todo PR, mas NÃO no alarme da linha principal — buraco pequeno, porque a main só recebe por PR. (3) Numa das conferências eu encadeei o portão de merge com um pipe e perdi o veredito dele; o merge saiu legítimo porque o portão refaz a própria medição antes de agir, mas o erro virou a lição 123.",
  autoridade: "sessao",
  evidencia: "PRs 217-224 MERGED; ci.py --apenas muralhas 4/4 PASS; 504 testes do testador; armadilhas 122 e 123",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: null,
  vence_em_dias: null
});})();
// ---- 20260826-007-evidencias-que-apontavam-para-a-lapide ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-007-evidencias-que-apontavam-para-a-lapide",
  tipo: "nota",
  quando: "2026-08-26",
  titulo: "Correção: dois registros apontam a prova deles para um arquivo que a própria reforma aposentou",
  detalhe: "Registro não se edita — então a correção é esta nota, e ela vale como o endereço certo para quem for conferir.\n\nOs registros 20260823-002 (a retrotradução da chave paga) e 20260826-002 (a fila dos robôs) citam como evidência 'arquivos/painel-retomada.html', seções 6 e 5. Esse arquivo virou LÁPIDE na reforma do mesmo dia: ele hoje só tem um aviso e um redirecionamento, e a pasta arquivos/ nem entra no Git. Quem seguisse a pista não acharia nada.\n\nO endereço certo, congelado e versionado, é a fotografia: docs/paineis/fotografias/fotografia-20260825-retomada.html — as seções 5 e 6 estão lá, intactas, como eram em 25/08.\n\nA lição, que vale para qualquer obra futura: quando uma obra aposenta um arquivo, ela precisa varrer as evidências que apontam para ele. Prova que aponta para o vazio não é prova — e, num livro em que nada se edita, o conserto custa um registro novo em vez de uma linha corrigida.",
  autoridade: "sessao",
  evidencia: "docs/paineis/fotografias/fotografia-20260825-retomada.html (seções 5 e 6) — conferido que existe e contém o conteúdo citado",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: null,
  vence_em_dias: null
});})();
// ---- 20260826-008-auditoria-de-fora-quatro-consertos ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-008-auditoria-de-fora-quatro-consertos",
  tipo: "entrega",
  quando: "2026-08-26",
  titulo: "Uma segunda auditoria, de sessão nova, achou quatro defeitos no painel — os quatro foram corrigidos",
  detalhe: "A obra da reforma foi auditada por uma sessão que não a construiu, com o painel aberto num Chrome de verdade (o que fecha a ressalva do registro 006: a costura entre o manifesto e os registros funciona — 18 registros carregaram, o placar calculou sozinho). O que estava de pé continua de pé. O que estava errado:\n\n1) O cartão 'As últimas conferências automáticas' pintava VERDE contando execução que ainda não tinha terminado. Medido ao vivo: 2 das 6 estavam na fila e o cartão dizia 'as últimas 6 execuções fecharam verdes'. Era o falso-verde nº 1 da casa dentro do instrumento feito para matá-lo. Agora, execução ainda correndo pinta CINZA 'sem veredito'.\n\n2) A caixa 'Precisa de você' CONSEGUIA esquecer, por três portas: o campo que põe o pedido nela escrito com aspas, o campo esquecido, e um registro que respondia a si mesmo. As três passavam pela validação e o pedido sumia calado. As três agora reprovam na entrada.\n\n3) A muralha do painel perdia o veredito do próprio instrumento: imprimia '(exit 0)' ao reprovar e rebaixava ERROR a FAIL. O estado que o teste dizia cobrir era o único que ninguém media.\n\n4) Rótulos que mentiam: dois documentos citavam um gerador '.py' que não existe, e duas listas anunciavam 3 muralhas quando são 4.\n\nFICA PARA VOCÊ DECIDIR, e está registrado como pedido separado: a vista 'Meu mapa' que o veredito prometeu não foi construída, e essa omissão não estava declarada.",
  autoridade: "sessao",
  evidencia: "PR #227 — vermelho→verde medido nos quatro: cartão verde com 2 de 6 execuções 'queued'; validação aprovando os 3 casos que esvaziavam a caixa; muralha devolvendo exit 1 com '(exit 0)' impresso onde devia ser 2. Portões depois: muralhas 4/4 PASS, testador 505 passed",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: null,
  vence_em_dias: null
});})();
// ---- 20260826-009-decisao-a-vista-meu-mapa-nao-foi-construida ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-009-decisao-a-vista-meu-mapa-nao-foi-construida",
  tipo: "pendencia",
  quando: "2026-08-26",
  titulo: "Decisão sua: a vista 'Meu mapa' foi prometida no veredito e não foi construída — reconstruir ou aposentar?",
  detalhe: "O QUE ACONTECEU: o veredito que você aprovou diz, em três lugares, que a experiência do Roadmap seria preservada quase intacta como uma vista chamada 'Meu mapa', ao lado de Operação e Memória. O painel entregue tem Capa, Operação e Memória — e o Roadmap virou fotografia congelada. Dele sobrou uma linha calculada por frente, dentro do bloco 'As frentes'.\n\nPOR QUE IMPORTA: a capa responde 'o que aconteceu'. O Roadmap respondia 'para onde estamos indo' — os capítulos, o que vem depois, onde cada frente está na subida. Nenhuma outra tela responde isso hoje.\n\nPOR QUE VOCÊ ESTÁ SABENDO SÓ AGORA: a obra declarou três omissões num registro próprio (20260826-003) e esta não estava lá. Não foi decisão anunciada, foi peça que caiu no caminho — é isso que a torna sua para decidir, e não do robô.\n\nSE VOCÊ NÃO DECIDIR: nada quebra. O painel segue funcionando e a fotografia do Roadmap continua guardada. O que se perde é a resposta para 'para onde vamos', que hoje só existe congelada em 26/08.\n\nRECOMENDAÇÃO: construir a vista 'Meu mapa', calculada dos registros como as outras. É a opção completa, e a regra da casa é fazer completo — a redução aqui não foi escolhida, aconteceu.\n\nALTERNATIVAS: (a) construir a vista, trabalho de robô, sem passo seu; (b) declarar que a capa basta e aposentar a promessa, o que exige um registro dizendo isso — para nenhum agente futuro achar que ficou faltando; (c) adiar, e ela continua nesta caixa.\n\nÉ REVERSÍVEL: sim, dos dois lados.",
  autoridade: "sessao",
  evidencia: "docs/paineis/VEREDITO-DAS-CONSULTORIAS.html — tabela da seção 8, o parágrafo 'A correção' da rodada 2 e o desenho da arquitetura final, os três citando a vista 'Meu mapa'",
  verificado_em: "2026-08-26",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: null,
  vence_em_dias: null
});})();
// ---- 20260826-010-rumo-fabrica-tres-pecas ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-010-rumo-fabrica-tres-pecas",
  tipo: "rumo",
  quando: "2026-08-26",
  titulo: "Próximo na fábrica: as três peças que faltam — vigia dos vigias, alarme completo e partida em 1 comando",
  detalhe: "Tudo trabalho de robô; nada aqui depende de você e nada toca pagamento.\n\n1) O vigia dos vigias: um portão que confere se os outros portões continuam mordendo — hoje um guarda pode ser afrouxado sem ninguém notar.\n2) O alarme completo da linha principal: o aviso automático quando algo quebra no tronco do projeto, cobrindo o que hoje fica de fora por escrito.\n3) A partida em 1 comando: subir o projeto inteiro na máquina com uma linha só, em vez da sequência de hoje.\n\nPara despachar: 'Leia RUNBOOK-LOTES.md e toque um lote com as três peças da fábrica'.",
  autoridade: "sessao",
  evidencia: "registro 20260826-002 (a fila dos robôs), item 3",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: 30
});})();
// ---- 20260826-011-rumo-site-fuso-horario ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-011-rumo-site-fuso-horario",
  tipo: "rumo",
  quando: "2026-08-26",
  titulo: "Próximo no site: acertar o fuso horário das peças que têm página na rua",
  detalhe: "Algumas peças do site mostram hora com fuso errado — o projeto já teve o caso documentado de três células exibindo hora de Chicago, cinco horas atrás. Para quem visita, é data e hora erradas na tela.\n\nÉ trabalho de robô, sem passo seu. Não trava nada enquanto não for feito: nenhuma função do site depende disso para funcionar, só a informação fica torta.\n\nPara despachar: 'Leia RUNBOOK-LOTES.md e toque um lote com o fuso horário das células com página na rua'.",
  autoridade: "sessao",
  evidencia: "registro 20260826-002 (a fila dos robôs), item 5",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "site",
  vence_em_dias: 30
});})();
// ---- 20260826-012-rumo-comunidade-sininho-e-apresentacao ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-012-rumo-comunidade-sininho-e-apresentacao",
  tipo: "rumo",
  quando: "2026-08-26",
  titulo: "Próximo na comunidade: o sininho de avisos em todo o site, e apresentar o site à Caixa",
  detalhe: "1) O SININHO EM TODO O SITE: hoje ele só existe dentro da Caixa de Sugestões. A ideia é ele aparecer ao lado do seu nome em qualquer página. Suas três respostas de 25/08 já destravaram o plano e viraram lei do projeto. Uma etapa mais à frente vai pedir uma conversa sua — é a regra da casa quando duas peças passam a conversar de um jeito novo; você será avisado, e nada trava até lá.\n\n2) APRESENTAR O SITE À CAIXA: as duas peças ainda guardam a mesma pessoa em fichas separadas. É o conserto de fundo que destrava o resto; as três entregas já estão decididas em documento.\n\nOs dois são trabalho de robô. Para despachar: 'Leia RUNBOOK-LOTES.md e toque um lote com o sininho no site e a apresentação à Caixa'.",
  autoridade: "sessao",
  evidencia: "registro 20260826-002 (a fila dos robôs), itens 1 e 2 + docs/notificacoes/PLANO-MESTRE.md",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "comunidade",
  vence_em_dias: 30
});})();
// ---- 20260826-013-rumo-curso-o-capitulo-do-dono ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-013-rumo-curso-o-capitulo-do-dono",
  tipo: "rumo",
  quando: "2026-08-26",
  titulo: "O curso é o único capítulo que nenhum robô faz por você — e é o de maior retorno",
  detalhe: "O que falta aqui, e que só você pode dar a direção:\n\n1) O conteúdo do curso — as aulas da escola de criação 3D para Roblox.\n2) A página de vendas: a promessa, o preço, a história que convence. Você dá a direção; os robôs constroem as páginas.\n3) O endereço definitivo da escola (registrar o domínio), quando você quiser — os nomes seguem livres.\n\nSem prazo e no seu ritmo. Fica registrado o que quatro conselheiros externos disseram, sem combinar entre si: o maior risco deste projeto não é um erro técnico — é uma fortaleza perfeita que ninguém visita. Uma hora sua investida aqui rende mais que qualquer melhoria técnica.\n\nEste rumo não vence: ele fica aqui até você mexer nele.",
  autoridade: "mantenedor",
  evidencia: "docs/paineis/fotografias/fotografia-20260826-roadmap-final.html, capítulo 4",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "curso",
  vence_em_dias: null
});})();
// ---- 20260826-014-rumo-vender-comeca-do-meio ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-014-rumo-vender-comeca-do-meio",
  tipo: "rumo",
  quando: "2026-08-26",
  titulo: "Vender está parado por ordem sua — e quando você liberar, começa do meio, não do zero",
  detalhe: "'Pagamento por último' é a sua regra, e ela está sendo cumprida: nada deste capítulo se move até você dizer que o site vai vender.\n\nO que espera, quando a ordem vier: a tela de pagar com cartão (robô); ligar o aviso oficial de 'pagou' no painel do Mercado Pago (passo seu, com nossa ajuda); trocar as chaves de teste pelas de verdade no servidor (passo seu, com bloco pronto para colar); e a primeira compra de teste completa, provada de ponta a ponta.\n\nO adiantado que não se perde: o coração do pagamento já foi provado em ambiente de teste — um QR de Pix de verdade foi gerado no servidor, e o caminho 'pagou virou matrícula' funciona.\n\nEste rumo não vence: ele espera a sua palavra, não o calendário.",
  autoridade: "mantenedor",
  evidencia: "ordem de 22/08/2026 (CLAUDE.md e registro 20260822-002) + fotografia do Roadmap de 26/08, capítulo 5",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "vender",
  vence_em_dias: null
});})();
// ---- 20260826-015-resposta-pode-construir-o-meu-mapa ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-015-resposta-pode-construir-o-meu-mapa",
  tipo: "resposta",
  quando: "2026-08-26",
  titulo: "Você mandou construir o 'Meu mapa' — e ele está construído",
  detalhe: "Perguntado se a vista prometida devia ser construída ou aposentada, você respondeu: pode construir.\n\nO que existe agora: uma aba nova no painel, com os cinco capítulos na ordem do Roadmap antigo — a fábrica, o site, a comunidade, o curso e vender. Cada capítulo diz onde a frente está, para onde ela vai, o que espera por você ali e o que andou por último. Nada disso é escrito à mão: é o mesmo livro de registros, agrupado por capítulo.\n\nA peça que faltava para isso existir era um jeito de guardar o FUTURO — um livro de acontecimentos, sozinho, só sabe contar de onde viemos. Por isso nasceu o registro de 'rumo'. Ele tem uma regra que vale a pena você conhecer, porque protege você: rumo NUNCA fica verde. Verde neste painel quer dizer 'provado', e ninguém prova o futuro. Plano é plano; verde só quando virar entrega com prova conferida.\n\nEste registro fecha o pedido 20260826-009 — e a caixa 'Precisa de você' se atualiza sozinha por causa dele, sem ninguém apagar linha nenhuma.",
  autoridade: "mantenedor",
  evidencia: "PR #228 — 14 casos novos de teste-guarda, muralhas 4/4 PASS, testador 505 passed, e a vista aberta num Chrome de verdade por file:// com os 5 capítulos montados",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: "20260826-009-decisao-a-vista-meu-mapa-nao-foi-construida",
  gravidade: "info",
  frente: null,
  vence_em_dias: null
});})();
// ---- 20260826-016-os-consertos-e-o-mapa-entraram ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-016-os-consertos-e-o-mapa-entraram",
  tipo: "entrega",
  quando: "2026-08-26",
  titulo: "Entraram no projeto: os quatro consertos da auditoria e a vista 'Meu mapa'",
  detalhe: "Os dois trabalhos do dia estão na linha principal, mergeados pelo rito, com as duas provas obrigatórias verdes no commit certo.\n\nO QUE MUDOU PARA VOCÊ: o painel agora tem quatro abas — a Capa, o Meu mapa, a Operação e a Memória. E três coisas que o painel conseguia esconder deixaram de ser possíveis: contar como verde uma verificação que ainda não terminou; perder um pedido da caixa 'Precisa de você' por um campo mal escrito; e disfarçar instrumento quebrado de erro de conteúdo.\n\nO DIA TAMBÉM DEIXOU LIÇÃO: a esteira do GitHub teve uma pane de mais de duas horas, e no meio dela eu enviei um commit vazio para tentar destravar — foi justamente o que travou o merge, porque as verificações atrasadas ficaram presas ao commit anterior. Virou a lição 125, com o padrão inteiro descrito, para a próxima sessão reconhecer em dois minutos o que custou uma hora aqui.\n\nEste registro fecha o dia. A caixa 'Precisa de você' segue com 6 pedidos, todos antigos e nenhum criado hoje.",
  autoridade: "github",
  evidencia: "PR #227 MERGED (commit af33c24ded) e PR #228 MERGED (commit 9c188f5b7e), os dois pelo rito ci/mergear.py --confirmo, com muralhas e ci-celula-gate verdes; nenhum deploy disparado (as mudanças não tocam infra/ nem services/)",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260826-017-trava-de-merge-nativa-ligada ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-017-trava-de-merge-nativa-ligada",
  tipo: "resposta",
  quando: "2026-08-26",
  titulo: "A trava de merge do GitHub está LIGADA — nem o dono consegue mais mergear com vermelho",
  detalhe: "Você perguntou qual das duas opções da tela clicar. A resposta é: nenhuma — a trava foi ligada pelo robô, pelo mesmo canal que ele usa para abrir e mergear PR. Você não precisa clicar em nada.\n\nO que passou a valer na main, a partir de hoje: ninguém escreve direto nela (todo trabalho entra por Pull Request); ninguém apaga a main; ninguém reescreve a história dela; e o botão de merge só destrava depois que as DUAS provas do robô ficam verdes (as muralhas e o portão da célula). Antes, o botão verde funcionava com tudo vermelho — quem segurava era só a disciplina do robô.\n\nNão existe exceção para ninguém, nem para você como dono da conta: o GitHub responde 'current_user_can_bypass: never'. A porta de emergência não é um atalho escondido, é desligar a trava — um ato visível, que fica registrado.\n\nA prova não é print de tela: o robô TENTOU escrever na main por fora, como um invasor faria, e o GitHub recusou com a mensagem 'as mudanças precisam passar por um Pull Request; 2 de 2 verificações obrigatórias são esperadas'. Nada foi gravado.\n\nCom isso fecha a pendência mais velha do seu painel — aberta em 19/08, quando essa proteção ainda era paga.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/rules/21570247 — recusa medida: HTTP 409 'Repository rule violations found / Changes must be made through a pull request / 2 of 2 required status checks are expected'",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: "20260819-001-h3-trava-de-merge-nativa",
  gravidade: "verde",
  frente: null,
  vence_em_dias: null
});})();
// ---- 20260826-018-a-trava-entrou-na-main ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-018-a-trava-entrou-na-main",
  tipo: "entrega",
  quando: "2026-08-26",
  titulo: "A trava de merge foi provada no próprio PR que a documenta — e ele entrou",
  detalhe: "O PR #226 (que escreve nos documentos do projeto que a trava existe) serviu de cobaia dela. Enquanto as duas provas do robô não ficaram verdes, o GitHub manteve o PR como 'bloqueado' — e nem o robô, nem você como dono da conta, conseguiriam mergear. Quando as provas ficaram verdes, o estado virou 'liberado' sozinho e o merge passou pelo caminho normal.\n\nÉ o ciclo completo, medido no mesmo dia: vermelho barra, verde libera.\n\nUm atraso honesto, que não foi culpa do projeto: o GitHub teve uma pane de mais de duas horas na esteira de testes. Nesse período nenhum teste conseguia nem começar, e o PR ficou parado sem veredito nenhum. A pane passou, os testes rodaram em 30 segundos e tudo entrou. Ficou registrado o que fazer da próxima vez, para ninguém perder uma hora achando que o problema era nosso.\n\nDepois do merge, as duas rondas automáticas da main rodaram e ficaram verdes. Nada de servidor foi tocado — este PR só mexe em documentos.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/226 — MERGED em 2026-08-26T18:54:49Z, commit 356d188f; estado do PR passou de BLOCKED para CLEAN quando muralhas e ci-celula-gate ficaram verdes; rondas pos-merge alarme-main (run 33002306828) e ci-celula (run 33002307021) ambas success",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: null,
  vence_em_dias: null
});})();
// ---- 20260826-019-a-lista-dupla-do-precisa-de-voce ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-019-a-lista-dupla-do-precisa-de-voce",
  tipo: "pendencia",
  quando: "2026-08-26",
  titulo: "Decisão sua: o que espera por você ainda mora em DOIS lugares — e eles já discordam",
  detalhe: "O ACHADO: a lei da reforma diz que nenhum fato do projeto mora em dois lugares. Mas o CLAUDE.md, no mesmo arquivo que declara essa lei, continua mandando o robô escrever o que depende de você numa tabela mantida à mão (a seção 1 do ARMADILHAS-OPERACAO.md). Ou seja: existem hoje duas listas do 'precisa de você' — a calculada, no painel, e a escrita à mão, no documento.\n\nELES JÁ DISCORDAM, medido em 26/08: a tabela tem 7 itens em aberto; a caixa do painel mostra 6. O item H17 não tem registro nenhum, então ele é invisível no seu painel. É exatamente a doença do H18, que a reforma foi feita para curar, sobrevivendo por dentro da própria lei.\n\nPOR QUE É SEU: consertar significa mexer no CLAUDE.md, que é arquivo-lei, e decidir o destino da tabela antiga. Robô não muda a lei do projeto sozinho.\n\nSE VOCÊ NÃO DECIDIR: nada quebra hoje, e as duas listas continuam se afastando devagar — que é o jeito silencioso pelo qual um painel volta a mentir.\n\nRECOMENDAÇÃO: fazer a completa — a tabela vira lápide apontando para o painel, os itens em aberto viram registros (inclusive o H17, que hoje some), e o CLAUDE.md passa a mandar registrar num lugar só. É trabalho de robô; o que é seu é a palavra.\n\nALTERNATIVAS: (a) a completa, acima; (b) a tabela guarda só o COMO FAZER de cada passo manual, e o que está pendente vive só no painel; (c) deixar como está, sabendo do risco.\n\nÉ REVERSÍVEL: sim.",
  autoridade: "sessao",
  evidencia: "CLAUDE.md (a seção que manda registrar na tabela §1) × painel/LEIA-ME.md (a lei anti-duplicação); contagem de 26/08: 7 linhas abertas em ARMADILHAS-OPERACAO §1 (H3, H4, H7, H8, H15, H16, H17) contra 6 na caixa calculada",
  verificado_em: "2026-08-26",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260826-020-h11-prova-do-primeiro-deploy-de-infra ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-020-h11-prova-do-primeiro-deploy-de-infra",
  tipo: "pendencia",
  quando: "2026-08-23",
  titulo: "O deploy automático da infraestrutura está mecanizado, mas nunca foi visto rodando de verdade",
  detalhe: "Migrado da tabela §1 do ARMADILHAS-OPERACAO (item H11) para o livro, na mudança de 26/08 que deu uma casa só ao que está em aberto.\n\nO que é: a publicação automática das peças de infraestrutura foi construída e testada, mas o primeiro run de verdade ainda não aconteceu — então ela é uma promessa mecanizada, não uma prova.\n\nNão espera por você: espera pelo próximo trabalho que toque infraestrutura, que é quem vai disparar o run. Nada trava enquanto isso.\n\nEnquanto não houver run verde de verdade, isto NÃO conta como funcionando — é a regra da casa: verde é conquistado, não escrito.",
  autoridade: "sessao",
  evidencia: "ARMADILHAS-OPERACAO.md §1, linha H11 (as instruções técnicas continuam lá)",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260826-021-h16-criterio-de-pagamento-parado-por-ordem-sua ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-021-h16-criterio-de-pagamento-parado-por-ordem-sua",
  tipo: "pendencia",
  quando: "2026-08-23",
  titulo: "Um critério antigo de pagamento segue parado — por ordem sua, e é para continuar assim",
  detalhe: "Migrado da tabela §1 do ARMADILHAS-OPERACAO (item H16) para o livro, na mudança de 26/08 que deu uma casa só ao que está em aberto.\n\nEste item existe aqui para NÃO sumir, não para pedir nada de você. Ele faz parte do capítulo 'Vender', que está parado por decisão sua desde 22/08 — 'pagamento por último'. A decisão de 23/08 foi literalmente 'parar e deixar registrado', e é isso que este registro faz.\n\nPor isso ele NÃO entra na sua caixa: nada aqui espera resposta sua. Ele volta a se mexer no dia em que você disser que o site vai vender, e nem um minuto antes.\n\nO detalhe técnico do que falta continua na tabela §1, para quando a hora chegar.",
  autoridade: "mantenedor",
  evidencia: "ARMADILHAS-OPERACAO.md §1, linha H16 + a ordem de 22/08 registrada em 20260822-002",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "vender",
  vence_em_dias: null
});})();
// ---- 20260826-022-h17-celula-nova-nasce-com-o-portao-vermelho ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-022-h17-celula-nova-nasce-com-o-portao-vermelho",
  tipo: "pendencia",
  quando: "2026-08-24",
  titulo: "Toda peça nova do site nasce com um portão vermelho, e o conserto exige mandato seu",
  detalhe: "Migrado da tabela §1 do ARMADILHAS-OPERACAO (item H17) para o livro, na mudança de 26/08 que deu uma casa só ao que está em aberto. Este era o item invisível: estava aberto na tabela e não existia no painel — a prova de que as duas listas tinham se afastado.\n\nO que é, sem tecniquês: quando os robôs criam uma peça nova do site, um dos conferidores automáticos reprova de cara, porque a peça precisa ser declarada num arquivo que fica numa pasta protegida — e robô de peça não tem permissão de mexer lá. O contorno funciona (a sessão que rege o trabalho faz a declaração), mas custa uma volta a cada peça nova.\n\nNão espera por você no sentido de tarefa: o que ele precisa é que o próximo trabalho nessa área venha com autorização para tocar a pasta protegida — coisa que se resolve na hora de despachar, não agora.\n\nParte dele já foi resolvida em 24/08; o resto continua descrito na tabela §1.",
  autoridade: "sessao",
  evidencia: "ARMADILHAS-OPERACAO.md §1, linha H17 (o detalhe técnico e o histórico continuam lá)",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260826-023-a-lista-dupla-foi-desfeita ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-023-a-lista-dupla-foi-desfeita",
  tipo: "resposta",
  quando: "2026-08-26",
  titulo: "Resolvido: o que espera por você passou a morar num lugar só",
  detalhe: "Você mandou resolver, e a opção escolhida foi a completa.\n\nO QUE MUDOU: a tabela antiga (a seção 1 do arquivo de operação) parou de dizer o que está aberto. Ela continua inteira — com o histórico de cada atrito e as instruções técnicas de cada passo manual, que ninguém perdeu —, mas o ESTADO saiu de lá. O que espera por você agora se lê num lugar só: a caixa do painel, que é calculada e por isso não consegue esquecer nem inventar.\n\nOS TRÊS ITENS INVISÍVEIS ENTRARAM: havia três atritos abertos na tabela que não existiam no painel — inclusive um (o H17) que era o caso mais gritante da divergência. Os três viraram registro. Nenhum dos três entra na sua caixa, porque nenhum depende de decisão sua: um espera um trabalho de infraestrutura acontecer, outro está parado pela sua própria ordem de 'pagamento por último', e o terceiro precisa só de autorização na hora de despachar.\n\nA TRAVA: a lei nova não depende de ninguém lembrar dela. Um portão do robô de conferência reprova se a tabela voltar a declarar estado, e reprova também se alguém apagar a explicação de por que ela foi aposentada. Provado quebrando de propósito: com o marcador de volta, o portão fica vermelho e diz qual linha; sem ele, verde.\n\nFICA REGISTRADO um parente do mesmo problema, na seção 9 do mesmo arquivo — veja o registro seguinte.",
  autoridade: "mantenedor",
  evidencia: "as 7 linhas que declaravam estado deixaram de declarar; 3 registros novos (H11, H16, H17); ci/tests/test_uma_casa_para_o_precisa_de_voce.py com prova vermelho→verde no arquivo real",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: "20260826-019-a-lista-dupla-do-precisa-de-voce",
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260826-024-a-secao-9-e-o-mesmo-problema-de-novo ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-024-a-secao-9-e-o-mesmo-problema-de-novo",
  tipo: "pendencia",
  quando: "2026-08-26",
  titulo: "O mesmo problema, mais fraco, sobrou na seção 9 — declarado para não sumir",
  detalhe: "Ao consertar a tabela da seção 1, vi que a seção 9 do mesmo arquivo ('dívidas abertas') tem uma coluna de estado com a mesma natureza: uma lista mantida à mão, com marcadores de aberto. A maioria das linhas são dívidas técnicas do código, que não são assunto seu — mas pelo menos duas dizem esperar por você.\n\nPOR QUE NÃO CONSERTEI JUNTO: você mandou resolver a lista dupla, e o pedido registrado falava da seção 1. Ampliar sozinho para outra seção de um documento que você lê seria decidir por você o tamanho da obra. Prefiro declarar e perguntar.\n\nNÃO ESTÁ NA SUA CAIXA de propósito: é trabalho de robô, não decisão sua. Basta dizer numa sessão que a seção 9 recebe o mesmo tratamento — as dívidas viram registros, a tabela fica com o histórico, e o mesmo portão passa a vigiar as duas seções.\n\nRISCO enquanto isso: baixo. A seção 9 é lida por robô, não por você, e as duas linhas que esperam por você estão paradas pela ordem de 'pagamento por último'.",
  autoridade: "sessao",
  evidencia: "ARMADILHAS-OPERACAO.md §9 — coluna 'Estado' com marcadores mantidos à mão; ao menos 2 linhas declaram depender do mantenedor",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260826-025-tres-celulas-passaram-a-mostrar-hora-do-brasil ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-025-tres-celulas-passaram-a-mostrar-hora-do-brasil",
  tipo: "entrega",
  quando: "2026-08-26",
  titulo: "Três peças do site passaram a mostrar hora do Brasil — e ganharam um guarda que reprova se alguém desfizer",
  detalhe: "Havia uma linha de configuração que nunca foi escolhida nesta plataforma: a que diz QUE HORA MOSTRAR. Sem ela vale o padrão de fábrica da ferramenta, que é o fuso de Chicago — cinco horas atrás. Perto da meia-noite isso troca até o DIA na tela.\n\nO detalhe que torna isso perigoso: não é um erro. Não aparece vermelho em lugar nenhum, o site responde normal, e quem descobre é o visitante lendo a data errada.\n\nO QUE ENTROU HOJE: a linha certa em três peças — o site (funil), o catálogo e a que envia e-mails (mensageria) — cada uma com um teste que NÃO confere se a linha existe (isso seria conferir o próprio texto), e sim se a hora sai certa. Apaguei a linha de propósito antes de cada entrega e vi o teste ficar vermelho acusando '24/08/2026 23:00' onde devia ler '25/08/2026 01:00'. Depois repus e ficou verde.\n\nO caso do envio de e-mail era o mais grave dos três: uma hora errada numa tela se conserta; num e-mail já enviado, não.\n\nHONESTIDADE SOBRE O TAMANHO DO ESTRAGO: nenhuma dessas peças mostra data na tela hoje. O defeito estava dormindo, esperando a primeira página que mostrasse hora — foi assim que a Caixa de Sugestões foi pega em 24/08. Então isto não conserta nada que você veria hoje; impede o que você veria depois.\n\nTrês PRs, um por peça, os três mergeados com os portões verdes e a plataforma no ar o tempo todo (conferi de fora: os três endereços responderam 200 depois de cada entrega).",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/233 · /pull/234 · /pull/235 — os três MERGED, deploys 33013333493, 33013598246 e 33014036704 com conclusão success; meshcraft.top/healthz, meshcraft.top e basileiatoutheou.org em 200 depois da janela",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: "20260826-011-rumo-site-fuso-horario",
  gravidade: "verde",
  frente: "site",
  vence_em_dias: null
});})();
// ---- 20260826-026-o-rumo-da-fabrica-descrevia-trabalho-ja-feito ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-026-o-rumo-da-fabrica-descrevia-trabalho-ja-feito",
  tipo: "nota",
  quando: "2026-08-26",
  titulo: "As três peças da fábrica que eu ia construir hoje já estavam prontas desde ontem",
  detalhe: "Antes de despachar, fui conferir no código o que o rumo da fábrica dizia faltar — o vigia dos vigias, o alarme completo da linha principal e a partida em 1 comando. As três estão no ar desde 25/08/2026, entregues nos PRs #173, #171 e #174.\n\nInclusive conferi a única dúvida que sobrou: o vigia dos vigias parecia não rodar na esteira automática. Roda — por dentro da suíte que os dois portões já executam, e o próprio arquivo explica isso. Não há buraco.\n\nPOR QUE O RUMO ESTAVA ERRADO: ele foi escrito a partir de uma fotografia de painel antiga, e a fotografia se contradizia — uma seção dizia 'faltam 3 peças' e outra, no mesmo arquivo, listava as três como entregues. Quem leu de cima para baixo escreveu o rumo de boa-fé.\n\nO QUE ISSO CUSTOU E O QUE EVITOU: custou alguns minutos de medição. Evitou gastar um lote inteiro refazendo trabalho pronto. A lição virou regra escrita para as próximas sessões (armadilhas/128): rumo é o único tipo de registro que afirma uma AUSÊNCIA, e ausência não se lê em documento — se mede no código.\n\nNada a fazer nesta frente. Ela está em dia.",
  autoridade: "sessao",
  evidencia: "PRs #171, #173 e #174 mergeados em 25/08/2026; ci/guarda_dos_guardas.py em disco, invocado por ci/tests/test_guarda_dos_guardas.py, que roda em `muralhas` e `alarme-main`; alarme-main.yml declara por escrito o skip medido das duas muralhas de diff",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: "20260826-010-rumo-fabrica-tres-pecas",
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260826-027-metade-do-rumo-da-comunidade-ja-estava-pronta ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-027-metade-do-rumo-da-comunidade-ja-estava-pronta",
  tipo: "nota",
  quando: "2026-08-26",
  titulo: "O site já foi apresentado à Caixa em 25/08 — o que falta para o sininho é uma conversa com você",
  detalhe: "O rumo da comunidade tinha duas metades. Medi as duas no código.\n\nA PRIMEIRA JÁ ESTÁ FEITA. 'Apresentar o site à Caixa' era o conserto de fundo: as duas peças guardavam a mesma pessoa em fichas separadas, sem nada que as ligasse. Isso entrou em 25/08 — a ficha da Caixa passou a guardar, ao lado, o identificador da pessoa no site. Era a peça que destrava todo o resto do plano do sininho.\n\nA SEGUNDA ESTÁ PARADA, E A PORTA É SUA. O sininho aparecer em qualquer página do site é o quinto degrau de um plano de sete. O próximo degrau é o segundo, e ele não é trabalho de robô: é uma das conversas de arquitetura que a lei da casa exige ter COM VOCÊ presente, porque muda o formato em que as peças conversam entre si — e formato, uma vez publicado, não se desfaz barato. A regra dos lotes proíbe explicitamente mudar isso sem você.\n\nEntão não é o robô esperando robô: é o plano chegando na porta que só você abre. Registrei o pedido em separado, para ele aparecer na sua caixa e não sumir aqui dentro.\n\nO rumo em si não estava errado — ele já avisava que 'uma etapa mais à frente vai pedir uma conversa sua'. Chegou nela.",
  autoridade: "sessao",
  evidencia: "services/sugestoes/apps/sugestoes/models.py — campo id_da_plataforma com CheckConstraint, entregue em 25/08/2026; docs/notificacoes/PLANO-MESTRE.md §6 Fase 2 e docs/decisoes/DECISAO-notificacoes.md §4.1 exigem Rito de Contrato; RUNBOOK-LOTES.md §7 proíbe contrato dentro de lote",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: "20260826-012-rumo-comunidade-sininho-e-apresentacao",
  gravidade: "info",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260826-028-o-sininho-espera-uma-conversa-de-arquitetura ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-028-o-sininho-espera-uma-conversa-de-arquitetura",
  tipo: "pendencia",
  quando: "2026-08-26",
  titulo: "Para o sininho andar, precisamos de uma sessão juntos — marcar quando você quiser",
  detalhe: "O QUE EU PRECISO DE VOCÊ: uma sessão sua, no computador, comigo — não um comando para colar, e sim uma conversa. Você responde perguntas em português; eu escrevo o resultado e abro o PR.\n\nPOR QUE NÃO POSSO FAZER SOZINHO: o próximo passo muda o FORMATO em que duas peças da plataforma conversam. É como mudar o formulário que um setor manda para o outro: depois que o formulário novo está em uso, voltar atrás é caro. A lei da casa (Rito de Contrato) manda que mudanças assim tenham você presente, e a regra dos lotes proíbe robô fazer isso sozinho. Não é burocracia inventada agora — é a regra que já existia, chegando na vez dela.\n\nQUANTO TEMPO: é uma sessão curta. O plano inteiro já está escrito e decidido; o que falta é você confirmar o formato e eu executar.\n\nO QUE DESTRAVA: os degraus 3, 4 e 5 do plano — a caixa de avisos ganhar casa própria, o site aprender a perguntar quantos avisos você tem, e o sininho aparecer ao lado do seu nome em qualquer página. Todos os três são trabalho de robô depois desta conversa.\n\nNÃO HÁ URGÊNCIA e nada quebra enquanto isso. O sininho continua funcionando dentro da Caixa de Sugestões, como funciona hoje.",
  autoridade: "sessao",
  evidencia: "docs/notificacoes/PLANO-MESTRE.md §6 (Fase 2 — Rito de Contrato) · docs/decisoes/DECISAO-notificacoes.md §4.1 · RITOS.md §3 · RUNBOOK-LOTES.md §7",
  verificado_em: "2026-08-26",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260826-029-duas-celulas-de-dinheiro-ficaram-de-fora-do-fuso ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-029-duas-celulas-de-dinheiro-ficaram-de-fora-do-fuso",
  tipo: "pendencia",
  quando: "2026-08-26",
  titulo: "Duas peças de dinheiro ficaram sem a correção da hora — parei por causa da sua ordem, e quero sua palavra",
  detalhe: "A CORREÇÃO DE HOJE cobriu três das cinco peças que faltavam. As duas que sobraram são a do carrinho (checkout) e a do pagamento.\n\nPOR QUE PAREI: você deu uma ordem clara — pagamento por último, não mexer nessas duas até você dizer que o site vai vender. Eu poderia argumentar que uma linha de configuração de fuso horário não é 'mexer em pagamento': ela não toca preço, não toca cobrança, não toca o Mercado Pago. Mas ordem sua eu não reinterpreto sozinho. Prefiro perguntar.\n\nO QUE EU FARIA, SE VOCÊ AUTORIZAR: exatamente o mesmo que fiz nas outras três — uma linha de configuração e um teste que reprova se alguém a apagar. Dois PRs pequenos, nenhuma lógica de dinheiro tocada, nenhuma tela mudada.\n\nO RISCO DE DEIXAR COMO ESTÁ: baixo hoje, e é honesto dizer por quê — nenhuma dessas duas peças mostra data na tela. O defeito fica dormindo. Ele acorda no dia em que uma tela de compra ou de recibo mostrar um horário, e aí mostra cinco horas atrás.\n\nBASTA RESPONDER 'pode corrigir as duas' numa sessão qualquer. Se preferir deixar para quando o pagamento for retomado, também está certo — fica registrado aqui e não se perde.",
  autoridade: "sessao",
  evidencia: "ARMADILHAS-OPERACAO.md §9 — a dívida do fuso, agora com duas células em aberto; armadilhas/099 traz a receita completa, a mesma aplicada nos PRs #233, #234 e #235",
  verificado_em: "2026-08-26",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "vender",
  vence_em_dias: null
});})();
// ---- 20260826-030-a-vps-recusou-o-robo-tres-vezes-na-janela ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-030-a-vps-recusou-o-robo-tres-vezes-na-janela",
  tipo: "incidente",
  quando: "2026-08-26",
  titulo: "O servidor recusou a conexão do robô três vezes durante a entrega — sem um minuto de site fora do ar",
  detalhe: "O QUE ACONTECEU: na hora de colocar cada peça no servidor, a conexão do robô com a máquina expirou três vezes — uma na segunda entrega e duas seguidas na terceira. Cada uma virou uma tentativa nova, e todas as três peças acabaram entrando.\n\nO QUE NÃO ACONTECEU: o site não saiu do ar em momento nenhum. Conferi de fora durante a janela inteira — os três endereços responderam normalmente o tempo todo. Quando essa conexão falha, a versão nova simplesmente não sobe e a versão anterior continua atendendo. Ninguém que estivesse visitando percebeu nada.\n\nCOMO SEI QUE NÃO É PROBLEMA DA MÁQUINA: conferi do meu lado que o servidor estava respondendo na porta certa durante toda a janela. A máquina estava viva; o que falhou foi o caminho entre o robô da nuvem e ela. Detalhe importante porque existe uma falha ANTIGA com a mesma mensagem de erro, e aquela sim exigiria mexer numa configuração sua — não é o caso.\n\nO QUE FIZ ALÉM DE REPETIR: escrevi a diferença entre os dois casos na memória de campo (armadilhas/127), com a medição de uma linha que separa um do outro e a regra de quando parar de repetir e te avisar. A próxima sessão que topar com isso não vai gastar tempo suspeitando da configuração errada.\n\nNÃO PRECISA DE VOCÊ. Se voltar a acontecer com frequência, vira conversa sobre o provedor — por ora, foi ruído.",
  autoridade: "github",
  evidencia: "Runs 33013598246 (1 falha, verde no rerun) e 33014036704 (2 falhas, verde na 3a tentativa), ambos 'dial tcp ***:22: i/o timeout'; banner SSH-2.0-OpenSSH_9.6p1 respondendo do PC durante a janela; meshcraft.top/healthz, meshcraft.top e basileiatoutheou.org em 200",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260826-031-a-divida-do-fuso-fechou-nas-onze-celulas ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-031-a-divida-do-fuso-fechou-nas-onze-celulas",
  tipo: "entrega",
  quando: "2026-08-26",
  titulo: "A hora certa agora vale nas onze peças da plataforma — e a dívida antiga fechou",
  detalhe: "Você autorizou as duas peças de dinheiro, e com elas a dívida inteira fechou. O carrinho e o pagamento receberam exatamente o mesmo conserto das outras: uma linha de configuração e um teste que reprova quem apagar. Nenhuma rota, nenhum valor, nenhum contrato, nenhuma ligação com o Mercado Pago foi tocada.\n\nNo carrinho isso importa mais do que parece: prazo de Pix e horário do pedido são a hora que o CLIENTE lê para decidir se ainda dá tempo de pagar. Um Pix que expira às 23:00 aparecendo como 18:00 é uma venda perdida com o cliente achando que tinha tempo.\n\nOS DOIS MERGES EM CAMINHO PROTEGIDO, ANUNCIADOS COM NOME: carrinho (PR 237) e pagamento (PR 238). São as duas áreas onde a lei da casa exige que eu diga o que mergeei, em vez de mergear em silêncio. Foi com a sua autorização de hoje.\n\nO estado agora, conferido peça por peça: onze de onze com a linha certa e com guarda. Antes de hoje eram seis.",
  autoridade: "github",
  evidencia: "PRs #237 e #238 MERGED; deploys 33018885098 e 33019097167 com conclusão success; verificação peça por peça: 11/11 com TIME_ZONE e com tests/test_fuso_horario.py ancorado em -03:00; meshcraft.top/healthz, meshcraft.top e basileiatoutheou.org em 200 depois dos deploys",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: "20260826-029-duas-celulas-de-dinheiro-ficaram-de-fora-do-fuso",
  gravidade: "verde",
  frente: "vender",
  vence_em_dias: null
});})();
// ---- 20260826-032-um-guarda-que-parecia-guardar-e-nao-guardava ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-032-um-guarda-que-parecia-guardar-e-nao-guardava",
  tipo: "incidente",
  quando: "2026-08-26",
  titulo: "Antes de dizer 'dívida fechada', conferi um por um — e três peças não estavam protegidas de verdade",
  detalhe: "Eu ia escrever que a dívida da hora estava fechada. Antes de escrever, fui contar os protetores em disco, um por um. Não fechava.\n\nDUAS PEÇAS (a área administrativa e a do login) tinham a configuração certa e NENHUM protetor. Nascer certo não é continuar certo: uma linha de configuração é a coisa mais fácil do mundo de se perder num merge, e ninguém acusaria.\n\nA TERCEIRA É A QUE DÓI. A Caixa de Sugestões — justamente a peça onde esse defeito foi descoberto — estava listada no documento como 'corrigida COM protetor que morde'. O protetor existia e NÃO mordia. Apaguei a configuração de propósito, com banco de dados de verdade, e ele continuou verde.\n\nPOR QUÊ: ele comparava a data da tela com o resultado da MESMA conversão que a tela usa. Apagando a configuração, os dois lados vão juntos para o fuso errado e a comparação continua batendo. Ele provava o formato da data — que é útil — mas não provava qual fuso estava valendo. O nome dele prometia mais do que ele entregava, e o documento acreditou na promessa.\n\nCONSERTADO em três PRs (239, 240 e 241), sem afrouxar nada: não toquei no protetor antigo, que continua provando o que sempre provou. Entrou um protetor novo do lado, medindo contra um valor fixo em vez de contra a própria conversão. Provei os dois lado a lado, com a configuração apagada: o novo fica vermelho, o velho fica verde.\n\nA REGRA VIROU MEMÓRIA DA CASA: o valor esperado de um teste nunca pode ser produzido pela mesma engrenagem que o teste existe para vigiar. E, ao declarar uma dívida fechada, contar os protetores em disco e sabotar um por um — frase de documento não é medição.",
  autoridade: "sessao",
  evidencia: "PRs #239, #240 e #241 MERGED, deploys success; prova lado a lado com Postgres real: sem TIME_ZONE, o guarda novo da sugestoes falha (offset -1 day, 19:00:00) e o antigo passa (1 passed); armadilhas/129",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260826-033-a-conversa-do-sininho-aconteceu ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-033-a-conversa-do-sininho-aconteceu",
  tipo: "decisao",
  quando: "2026-08-26",
  titulo: "A conversa do sininho aconteceu — você decidiu três coisas, e o degrau que travava saiu do caminho",
  detalhe: "Você marcou a conversa e ela está feita. Três escolhas suas, todas já viradas em código e em lei:\n\n1) UMA CARTA POR PESSOA. Quando a equipe muda o status de uma ideia, a Caixa passa a mandar um aviso separado, endereçado, para cada interessado — em vez de uma lista com o nome de todo mundo circulando pela plataforma. Ninguém mais no sistema chega a ver quem votou em quê. E quando uma ideia bombar, a mensagem não vira um monstro.\n\n2) QUEM MEXEU: GUARDA SIM, MOSTRA NÃO. O sistema registra qual pessoa da equipe mudou o status, para você conseguir reconstruir a história se alguém questionar uma decisão. A tela do aluno diz apenas 'a equipe'. Você pode mudar de ideia e passar a mostrar o nome depois; o contrário não existe — o que não for guardado agora se perde para sempre.\n\n3) OS AVISOS ANTIGOS MUDAM DE CASA JUNTO. Quando a caixa nova nascer, os avisos que já existem vão junto, de uma vez. Nada de dois lugares mostrando números diferentes.\n\nO QUE JÁ ESTÁ NO AR: os dois formatos novos de mensagem (PR 243). Conferi 11 situações diferentes contra eles, incluindo tentar enfiar um e-mail de contrabando nos dois lugares onde caberia — recusado nos dois.\n\nO QUE VEM AGORA, tudo trabalho de robô: a Caixa passa a usar o formato novo, e depois nasce a caixa central com os avisos mudando de casa. Uma etapa mais à frente — quando o site aprender a perguntar quantos avisos você tem — vai pedir outra conversa sua. Aviso quando chegar lá.",
  autoridade: "mantenedor",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/243 — MERGED, só contracts/, com a etiqueta 'contrato' (Rito de Contrato, RITOS.md §3); lei escrita em docs/decisoes/DECISAO-fase-2-do-sininho.md; 11 casos de validação, todos como esperado",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: "20260826-028-o-sininho-espera-uma-conversa-de-arquitetura",
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260826-034-rumo-comunidade-os-proximos-degraus-do-sininho ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-034-rumo-comunidade-os-proximos-degraus-do-sininho",
  tipo: "rumo",
  quando: "2026-08-26",
  titulo: "Próximo na comunidade: a Caixa adota o formato novo, e depois nasce a caixa central de avisos",
  detalhe: "MEDIDO NO CÓDIGO HOJE, não copiado de painel (é a regra que aprendemos de manhã): a célula 'sugestoes' ainda publica o formato antigo; a célula 'notificacoes' não existe em disco; e nada fora da Caixa consome o formato antigo — o que torna a troca barata.\n\nSÃO DOIS PASSOS, os dois trabalho de robô:\n\n1) A Caixa passa a publicar no formato novo, incluindo as cartas endereçadas. É PR pequeno, na célula dela.\n\n2) Nasce a caixa central de avisos, e os avisos que já existem mudam de casa junto — como você decidiu hoje. Este passo precisa de UM comando seu na hora de criar o espaço no servidor; virá como uma linha só para colar, do jeito que já funcionou nas outras vezes, e eu aviso antes.\n\nO QUE AINDA VAI PEDIR CONVERSA SUA: o degrau em que o site aprende a perguntar quantos avisos você tem. É a mesma lei de hoje — muda o formato em que duas peças conversam. Só depois disso o sininho aparece ao lado do seu nome em qualquer página. Nada trava até lá.\n\nPara despachar: 'Leia RUNBOOK-LOTES.md e toque um lote com a adoção do formato novo na Caixa'.",
  autoridade: "sessao",
  evidencia: "services/sugestoes/apps/sugestoes/eventos.py ainda emite version=1; services/notificacoes não existe; grep de 'status-alterado' fora da sugestoes: vazio; plano em docs/notificacoes/PLANO-MESTRE.md §6 Fases 3 a 5",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260826-035-a-caixa-adotou-o-formato-novo ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-035-a-caixa-adotou-o-formato-novo",
  tipo: "entrega",
  quando: "2026-08-26",
  titulo: "A Caixa já fala o formato novo — e cada aviso agora sai como uma carta endereçada",
  detalhe: "O que você decidiu de manhã virou código no ar. Quando a equipe muda o status de uma ideia, a Caixa passa a fazer duas coisas novas, na mesma operação:\n\n1) Registra o fato dizendo QUEM mexeu, no identificador que vale para a plataforma inteira. É o dado que permite reconstruir a história depois; a tela do aluno continua dizendo 'a equipe'.\n\n2) Emite uma carta separada para cada interessado, endereçada com o identificador que qualquer parte do sistema entende. É o que a caixa central vai receber quando nascer.\n\nUM DETALHE HONESTO SOBRE QUEM FICA DE FORA: quem não voltou ao site desde 25/08 ainda não tem esse identificador. Essas pessoas não recebem carta — mas continuam recebendo o aviso normal dentro da Caixa, que é o que a tela mostra hoje. Na próxima vez que entrarem, o sistema anota o identificador e elas passam a receber.\n\nE UMA SITUAÇÃO RARA QUE PODE APARECER PARA A EQUIPE: se o site não conseguir confirmar quem é a pessoa que está moderando, a mudança de status é RECUSADA e nada é gravado — com uma tela em português pedindo para sair e entrar de novo. Preferi recusar a gravar pela metade: uma mudança registrada sem saber quem fez é pior do que uma mudança que não aconteceu.\n\nACHEI DOIS TESTES QUE MENTIAM enquanto fazia isso, e os dois estão consertados. Um deles fingia ser o site com um identificador falso que continha o e-mail da pessoa — e por isso um alarme de privacidade disparou. O alarme estava certo; o falso é que estava errado. Se eu tivesse 'consertado' desligando o alarme, teria aberto a porta para o vazamento de verdade.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/245 — MERGED, deploy 33021 success; 348 testes da célula verdes (eram 341); guarda de volume provado por sabotagem (10 consultas viram 46 com o desenho errado); /forms/sugestoes/healthz responde 200 e a Caixa redireciona normalmente depois da migração",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260826-036-a-caixa-central-de-avisos-nasceu ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-036-a-caixa-central-de-avisos-nasceu",
  tipo: "entrega",
  quando: "2026-08-26",
  titulo: "A caixa central de avisos nasceu e está no ar — o comando que você rodou funcionou",
  detalhe: "Você rodou o comando na VPS, eu subi a peça pelo pipeline, e ela está de pé. É a décima segunda peça da plataforma, e a primeira que nasce sem nenhuma tela.\n\nO QUE ELA FAZ: guarda os avisos de cada pessoa num lugar só, e sabe responder em um piscar de olhos a pergunta que o site vai fazer em toda página — 'quantos avisos eu tenho'. Ela ouve as cartas que a Caixa de Sugestões passou a enviar hoje de manhã e escreve uma linha para cada.\n\nCONFERI DE FORA, e conferi as duas coisas: que ela está viva (o servidor só aceita subir uma peça que responde 'estou bem', e ela respondeu) e que ela está INVISÍVEL para quem não deveria vê-la — os dois endereços que alguém tentaria adivinhar respondem 'não existe'. Ela não tem porta para a rua, de propósito: a tela vem depois da nossa última conversa.\n\nO resto da plataforma continuou respondendo normalmente o tempo inteiro.\n\nDETALHES QUE VOCÊ NÃO PRECISA GUARDAR, mas que estão feitos: banco próprio e fechado só para ela; o botão de desfazer (voltar à versão anterior) já configurado no mesmo dia em que ela nasceu — peça que nasce sem isso é armadilha conhecida daqui; e o arquivamento automático dos avisos antigos, para a caixa não ficar lenta no dia em que der muito certo.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/248 (a célula) e /pull/252 (o compose) — mergeados; deploy-infra 33029480849 success e deploy-celula 33029073463 success, com os containers plataforma-notificacoes-1 e plataforma-notificacoes-consumer-1 em Healthy; de fora: meshcraft.top, /healthz, /forms/sugestoes/healthz e basileiatoutheou.org em 200, e /notificacoes/healthz e /api/notificacoes/ em 404",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260826-036-o-painel-agora-tem-endereco-na-internet ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-036-o-painel-agora-tem-endereco-na-internet",
  tipo: "entrega",
  quando: "2026-08-26",
  titulo: "O painel agora tem endereço na internet — atrás do seu login, e se atualiza sozinho",
  detalhe: "Você abriu a noite dizendo que o painel que estava vendo continuava desatualizado, e pediu um link. Agora existe um:\n\nmeshcraft.top/admin/painel/\n\nÉ o MESMO painel que você abre no computador — não uma cópia, não um resumo. Funciona no celular. E ele acompanha o livro sozinho: toda vez que um robô registrar uma tarefa aqui, o painel online muda junto, sem ninguém apertar nada.\n\nQUEM VÊ: só você e quem você autorizar. Quem não está na lista recebe 'esta página não existe' — não um 'acesso negado', que já contaria que existe algo ali.\n\nO QUE EU DESCOBRI NO MEIO DO CAMINHO, e você precisa saber: o seu repositório é PÚBLICO. Tudo que está nele — este livro, o código, os documentos de decisão — já é visível para qualquer pessoa na internet hoje, pelo site do GitHub. Isso não mudou com este trabalho; o painel novo é fechado. Mas se você preferir que o projeto inteiro deixe de ser público, é uma decisão sua e eu faço.\n\nO CAMINHO MAIS BARATO EXISTIA E VOCÊ RECUSOU, com razão: dava para publicar o painel hoje de graça pelo GitHub, mas seria um endereço público. Você escolheu a obra fechada. Ela custou um PR só, não os três que eu tinha estimado.\n\nO QUE AINDA NÃO FOI PROVADO: eu não consigo entrar com o seu login, então a última conferência é sua — abra o link e veja se o painel aparece. Tudo que uma máquina podia provar está provado (a imagem subiu com os 47 registros dentro, o deploy terminou em success, 44 testes verdes). Se abrir em branco ou pedir login em looping, me diga que eu conserto.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/249 — MERGED (commit dac60a9d); run de deploy 33028361068 completed/success nos três jobs; log do build: 'painel embutido: 47 registros'; /admin/healthz responde 200 com a imagem nova; 44/44 testes da célula admin, 5/5 na guarda da carona, muralhas PASS",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260826-037-o-dono-abriu-o-painel-online-e-ele-apareceu ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-037-o-dono-abriu-o-painel-online-e-ele-apareceu",
  tipo: "medicao",
  quando: "2026-08-26",
  titulo: "Você abriu o painel online e ele apareceu — a última prova, a que nenhuma máquina podia dar",
  detalhe: "O registro anterior entregou o painel em meshcraft.top/admin/painel/ e disse, em voz alta, o que ainda NÃO estava provado: eu não tenho o seu login, então a conferência final dependia de você abrir e olhar. Você abriu. Apareceu certinho.\n\nCom isso a entrega está fechada de verdade, e não por afirmação minha. Vale registrar por que essa distinção importa aqui: eu cheguei a testar o endereço de fora e recebi 'redireciona para o login' — e por um instante isso pareceu prova de que a página existia. Não era. Testei um endereço inventado e ele responde exatamente igual, porque a porta redireciona qualquer caminho antes de olhar a rota. Um relatório apressado teria vendido esse redirecionamento como prova; o que provou mesmo foi você.\n\nO QUE ESTÁ VALENDO A PARTIR DE AGORA: o painel do seu computador continua funcionando e continua sendo o mesmo. O endereço na internet é uma segunda porta para o MESMO painel, não um segundo painel — os dois leem o mesmo livro, e por construção não conseguem discordar.",
  autoridade: "mantenedor",
  evidencia: "confirmação do mantenedor em 26/08/2026, ao abrir https://meshcraft.top/admin/painel/ com a própria conta: 'abri o link, apareceu certinho'",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: "20260826-036-o-painel-agora-tem-endereco-na-internet",
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260826-037-o-impasse-dos-dois-portoes-na-subida ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-037-o-impasse-dos-dois-portoes-na-subida",
  tipo: "incidente",
  quando: "2026-08-26",
  titulo: "Na hora de subir, duas travas boas se trancaram uma na outra — e nada quebrou",
  detalhe: "A primeira tentativa de subir a peça nova ficou vermelha, e vale contar porque o motivo é curioso: NENHUMA das duas travas estava errada.\n\nO QUE ACONTECEU: subir uma peça nova envolve duas entregas ao servidor — a lista de peças (que diz que ela existe) e a peça em si. As duas foram disparadas ao mesmo tempo. A peça chegou primeiro, procurou o próprio nome na lista do servidor, não achou, e parou — corretamente, porque a alternativa seria mandar reiniciar a plataforma inteira. E aí a entrega da LISTA viu que algo tinha ficado vermelho e se recusou a continuar — também corretamente, porque a regra é não avançar com alarme aceso.\n\nResultado: cada uma esperando a outra, e repetir não resolvia — o problema e a solução estavam no mesmo pacote.\n\nA SAÍDA foi entregar a lista sozinha, num pacote separado, e só então repetir a peça. Funcionou de primeira.\n\nNADA QUEBROU E NINGUÉM VIU: a plataforma continuou respondendo o tempo todo. O que ficou vermelho foi a subida da peça nova, que ainda não estava sendo usada por ninguém.\n\nO QUE FIZ ALÉM DE RESOLVER: escrevi a regra no lugar onde o próximo robô vai olhar — dentro do próprio arquivo da lista — e uma entrada completa na memória da casa, inclusive com o atalho errado que alguém poderia ser tentado a usar (desligar a trava que reclamou). Aquele atalho resolveria hoje e cegaria a plataforma para sempre.",
  autoridade: "github",
  evidencia: "Runs 33029073463 (deploy-celula, 'não tem serviço algum em docker-compose.yml') e 33029073525 (deploy-infra, 'vermelhos-nao-previstos'); destravado pelo PR #252 (só o compose) e pelo rerun do primeiro, ambos verdes; armadilhas/134",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260826-038-a-muralha-que-impede-um-robo-de-pisar-no-outro ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-038-a-muralha-que-impede-um-robo-de-pisar-no-outro",
  tipo: "entrega",
  quando: "2026-08-26",
  titulo: "Agora um robô não consegue mais apagar o trabalho de outro sem querer",
  detalhe: "Hoje dois robôs trabalharam ao mesmo tempo na mesma pasta do projeto, e um deles, ao trocar de tarefa, apagou sem perceber as mudanças que o outro tinha feito. Isso custou retrabalho e dinheiro — e podia acontecer de novo a qualquer momento, porque a regra de cada robô trabalhar na sua própria cópia já existia no papel, mas nada obrigava ninguém a cumprir.\n\nAgora obriga. Foi construída uma muralha automática: a partir de hoje, qualquer robô que tentar editar arquivos ou mexer no histórico dentro da pasta principal compartilhada é barrado na hora, e a própria mensagem de bloqueio ensina o caminho certo (criar a sua cópia isolada e trabalhar lá). Cada robô também recebe um aviso logo que abre uma sessão na pasta compartilhada. A pasta principal virou um espelho: serve para consultar, nunca para mexer.\n\nA muralha foi provada de verdade antes de entrar: 36 testes automáticos, incluindo uma sabotagem de propósito (com a muralha quebrada, 11 testes acusaram na hora — ou seja, os vigias vigiam). Esse tipo de colisão entre robôs não deve se repetir; se alguma forma nova de colisão aparecer, o caminho é alargar a muralha, nunca voltar a confiar na sorte.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/253",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260826-039-o-livro-deixou-de-depender-da-memoria-dos-robos ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-039-o-livro-deixou-de-depender-da-memoria-dos-robos",
  tipo: "entrega",
  quando: "2026-08-26",
  titulo: "O livro deixou de depender da memória dos robôs — agora existe trava, e existe testemunha",
  detalhe: "Você fez a pergunta certa: de que adianta o painel se ele só mostra o que alguém lembrou de escrever? Fui auditar, e a resposta foi pior do que parecia.\n\nO QUE EU ACHEI: a regra 'ao terminar, registre' estava escrita na lei do projeto e NADA no sistema a obrigava. Conferi as três peças que pareciam garantir isso, uma a uma. A muralha do painel só confere se o livro está coerente — quem não mexe no livro passa limpo. A porta do merge IMPRIMIA um lembrete na tela. O alarme do projeto nem olha o livro. Ou seja: um robô podia terminar, mergear e ir embora sem registrar nada, com todos os sinais verdes, e o seu painel mostraria um projeto parado — sem nada indicando que faltava informação.\n\nAGORA SÃO DOIS REMÉDIOS, e eles curam metades diferentes:\n\n1) A PORTA DO MERGE COBRA. Enquanto houver trabalho mergeado sem registro, o próximo merge não sai. Esquecer deixou de ser possível — o robô esbarra na trava antes de conseguir continuar.\n\n2) O PAINEL TE MOSTRA. Ao abrir, ele pergunta ao GitHub quais trabalhos entraram sem virar registro, e aparece uma faixa vermelha no topo: 'N trabalhos concluídos que ninguém te contou', com a lista. Não é uma lista que alguém mantém à mão — é calculada, como a caixa 'Precisa de você'. Se a trava do remédio 1 falhar, você vê pelos seus próprios olhos.\n\nDUAS ESCOLHAS QUE VALE VOCÊ SABER, porque elas parecem detalhe e não são:\n\nA faixa SOME quando não há nada devendo. Escrever 'tudo em dia' ali competiria com o resto por atenção e treinaria o seu olho a pular aquela parte — e aí ela não seria vista no dia em que tivesse algo.\n\nSe a medição não conseguir falar com o GitHub, a faixa DIZ isso. Ela nunca mostra 'nada devendo' quando não sabe: seria a mentira mais cara possível, o painel afirmando que está tudo contado justamente quando perdeu a capacidade de conferir.\n\nUMA COISA QUE NÃO COBREI, de propósito: o passado. Rodando a regra contra o histórico, 17 merges apareciam como devedores — e a maioria TINHA sido contada a você, em registros que narravam o acontecimento sem citar o número do pedido. Cobrar isso criaria uma dívida falsa de 17 itens que travaria o próximo merge de qualquer sessão. Dívida impagável não é rigor: é o caminho mais curto para alguém desligar o guarda. A cobrança vale de hoje 23h em diante.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/256 (a trava na porta do merge) e https://github.com/abundanciabr/sitesdoreino/pull/257 (a faixa na tela) — os dois MERGED; deploy 33030968735 completed/success, com 'painel embutido: 52 registros' e 'regra da divida embutida' no log do build; 52/52 testes na célula admin, 21/21 nas guardas de ci/, muralhas PASS. Os dois guardas críticos provados por sabotagem (falha de medição virando lista vazia deixa os testes vermelhos)",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260826-040-a-licao-da-crase-que-corrompeu-uma-mensagem ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-040-a-licao-da-crase-que-corrompeu-uma-mensagem",
  tipo: "nota",
  quando: "2026-08-26",
  titulo: "Um erro meu, registrado: o terminal executou parte de um texto que eu estava escrevendo",
  detalhe: "Isto é pequeno e não afetou nada do que você usa — mas é do tipo que volta se ninguém escrever, então fica registrado.\n\nAo gravar a explicação de um dos trabalhos de hoje, usei um sinal de pontuação que o terminal do Windows entende como 'execute isto'. Resultado: pedaços do meu texto viraram comandos, a explicação foi gravada com buracos, e três arquivos vazios de nome absurdo apareceram na pasta do projeto.\n\nPor que isso importa mesmo sendo pequeno: o comando não falhou. Ficou tudo verde, com o texto estragado por dentro. E é nesse texto que o projeto guarda o PORQUÊ de cada decisão — alguém iria ler daqui a meses para entender uma escolha e encontraria lixo no lugar do argumento.\n\nCorrigido na hora: reescrevi a explicação, apaguei os três arquivos um a um (não com o comando de limpeza geral, que levaria junto o trabalho das outras sessões que estão na mesma pasta), e a lição virou entrada nova na memória de campo do projeto, com o jeito certo de fazer.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/259 — armadilhas/136; o commit corrompido foi corrigido com --amend antes do PR #257, e a árvore ficou limpa (git status vazio, conferido)",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260826-041-o-livro-passou-a-recusar-numero-repetido ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-041-o-livro-passou-a-recusar-numero-repetido",
  tipo: "entrega",
  quando: "2026-08-26",
  titulo: "O livro passou a recusar número repetido — o defeito que quatro robôs criaram hoje sem errar nada",
  detalhe: "Você mandou consertar, e está feito.\n\nO QUE ESTAVA ACONTECENDO: cada registro do livro tem um número do dia, e a instrução dizia 'escolha o próximo livre'. Com três robôs trabalhando ao mesmo tempo, os três liam a pasta no mesmo minuto, os três viam que o 036 estava livre — e os três usavam o 036. Não é descuido de ninguém: é corrida. E corrida não se resolve pedindo atenção, se resolve com trava.\n\nAconteceu QUATRO vezes só hoje. Nada se perdeu — o nome completo do registro continua único, e é ele que o sistema usa para ligar um registro a outro. O que se perdeu foi o número como referência: 'o 037' virou pergunta em vez de resposta.\n\nO QUE MUDOU: quem tentar gravar um registro com número já usado no mesmo dia recebe uma recusa que explica o conserto, e nada é gravado. É a mesma trava que o catálogo de armadilhas do projeto já tinha; agora o livro tem também.\n\nOS DOIS CASOS DE HOJE FICAM COMO ESTÃO, de propósito. Renomear registro que já entrou seria reescrever história — e é justamente a regra número um deste livro: registro não se edita, nunca. Além disso quebraria as ligações entre registros. Então o passado fica, e a regra vale daqui para a frente.\n\nUMA NOTA SOBRE COMO ISSO FOI FEITO, porque diz algo sobre a máquina que você montou: você pediu o mesmo conserto em duas janelas, e dois robôs começaram a fazer a mesma coisa ao mesmo tempo. Avisei o outro assim que percebi, e ele parou — mas antes disso ele tinha achado um buraco no meu desenho: do jeito que eu tinha escrito, congelar um número repetido de hoje abriria aquele número para sempre. Corrigi com o achado dele, com crédito no código. Quase criamos uma colisão de trabalho enquanto consertávamos a colisão de numeração.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/260 — provado por sabotagem (colisão de mentira faz o gerador sair com erro e não gravar nada) e por quatro casos novos no teste-guarda, incluindo o que garante que o mesmo número em DIAS diferentes continua válido; 54 registros válidos, muralhas PASS",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260826-042-a-vps-recusou-o-robo-pela-quarta-vez-hoje ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-042-a-vps-recusou-o-robo-pela-quarta-vez-hoje",
  tipo: "incidente",
  quando: "2026-08-26",
  titulo: "O servidor recusou a conexão do robô pela quarta vez hoje — de novo sem tirar o site do ar",
  detalhe: "Mesma falha do registro 030, agora na entrega da trava de número repetido: a conexão do robô da nuvem com o servidor expirou na hora de subir a versão nova. Repeti a etapa sem mergear nada de novo e passou.\n\nO SITE NÃO SAIU DO AR. Conferi de fora durante a falha: tanto o site público quanto a área administrativa responderam normalmente o tempo todo. Quando essa conexão falha, a versão nova simplesmente não sobe e a anterior continua atendendo.\n\nO FATO NOVO NÃO É A FALHA, É A CONTAGEM. O registro 030 contou três vezes numa janela; esta é a quarta do mesmo dia. Uma falha que se conserta sozinha com uma repetição não vale o seu tempo — mas quatro num dia é padrão, e padrão vale ser medido antes de virar rotina que ninguém questiona.\n\nPOR QUE NÃO ESTOU TE PEDINDO NADA AINDA: não dá para consertar isto de dentro (o robô não tem acesso ao servidor, por lei do projeto), e a causa provável está entre a nuvem do GitHub e a máquina — não na máquina, que estava viva e respondendo durante toda a falha. Colocar isso na sua caixa hoje seria te entregar um problema sem ação possível do seu lado. O gatilho para virar pedido seu: se passar a acontecer com deploy PARADO no meio (versão nova que sobe pela metade) ou se a repetição deixar de resolver.",
  autoridade: "github",
  evidencia: "run 33032286871 — 'deploy (admin)' falhou com 'dial tcp ***:22: i/o timeout'; repetido com gh run rerun --failed e concluído completed/success, com 'painel embutido: 55 registros' no log; /admin/healthz e o site público responderam 200 durante a falha e depois dela",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260826-043-apaguei-tres-arquivos-do-projeto-por-engano ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-043-apaguei-tres-arquivos-do-projeto-por-engano",
  tipo: "incidente",
  quando: "2026-08-26",
  titulo: "Apaguei três arquivos do projeto por engano — outro robô percebeu e restaurou",
  detalhe: "Erro meu, e registro porque é assim que este livro serve para alguma coisa.\n\nO QUE EU FIZ: de manhã, quando me mudei para uma cópia isolada de trabalho, deixei três arquivos para trás na pasta principal. À noite fui 'limpar a sujeira' e apaguei os três. Só que naquela altura eles já não eram sobra nenhuma: tinham entrado no projeto pela entrega da tarde. Apagar do disco foi, na prática, remover três arquivos do projeto.\n\nO QUE ISSO CAUSOU: a pasta principal ficou com três remoções pendentes, e a trava nova que impede robôs de se atrapalharem passou a recusar operações lá — corretamente, porque a pasta estava suja. Nenhum efeito no site, em nada que você usa, e nada foi perdido em momento nenhum: os arquivos estavam salvos no projeto o tempo todo. O outro robô percebeu, restaurou os três e conferiu que ficaram idênticos.\n\nO QUE MAIS ME INCOMODA, e é a razão do registro: eu CONFERI antes de apagar. Comparei os três com o que estava no projeto e o resultado foi 'idênticos'. Li isso como 'são cópias descartáveis' quando significava exatamente o contrário — 'estes SÃO os arquivos do projeto'. A prova de que era seguro apagar era a prova de que não era.\n\nE tem uma falha de processo por trás, que eu deixei escrita para os próximos: eu não conseguia inspecionar o estado daquela pasta de onde eu estava (o sistema me recusou, e com razão). O erro não foi apagar — foi apagar MESMO ASSIM, sem conseguir medir. Não conseguir medir não autoriza uma ação destrutiva; ela proíbe.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/262 — armadilhas/137; conferido de forma independente antes de escrever: 'git ls-files' confirma que os três são rastreados na main (entraram pelo PR #249) e os três estão de volta no disco, restaurados pela sessão vizinha",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260826-044-a-medicao-que-faltou-no-registro-anterior ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-044-a-medicao-que-faltou-no-registro-anterior",
  tipo: "medicao",
  quando: "2026-08-26",
  titulo: "A medição que faltou no registro anterior — feita agora, e o veredito continua o mesmo",
  detalhe: "Correção de método, não de conclusão. No registro 042 eu disse que a falha de conexão com o servidor era 'entre a nuvem e a máquina' — e disse isso SEM ter feito a medição que o próprio projeto exige para separar os dois casos possíveis.\n\nA medição existe, está escrita na memória de campo desde hoje de manhã, e é uma linha só: perguntar direto ao servidor se a porta de conexão está viva. Rodei agora. Ela respondeu, identificando-se normalmente. Isso confirma o diagnóstico: a máquina está viva e alcançável daqui; o que falha é o caminho entre o robô da nuvem e ela. Uma repetição resolve, que foi o que aconteceu.\n\nPOR QUE REGISTRO UMA CORREÇÃO QUE NÃO MUDA O RESULTADO: porque acertar por sorte e acertar por medição são a mesma coisa no papel e coisas opostas na prática. Se o veredito tivesse sido o outro, eu teria reportado a você um diagnóstico errado com a mesma confiança.\n\nUMA TENSÃO QUE DEIXO ANOTADA PARA QUEM VIER: o projeto tem duas réguas para esta mesma falha, e elas não dizem a mesma coisa. Uma conta episódios ('três numa semana viram estrutura') — e por ela as quatro de hoje já seriam estrutura. A outra manda medir, e diz que enquanto o servidor responder é blip, com o limite em três repetições vermelhas seguidas (hoje foi uma, e passou). Segui a segunda, que é mais nova e nasceu exatamente deste fenômeno. Quem revisitar decide se as duas continuam convivendo.",
  autoridade: "sonda",
  evidencia: "medição feita do PC em 26/08/2026: a porta 22 de 217.196.62.220 respondeu 'SSH-2.0-OpenSSH_9.6p1 Ubuntu-3' (exit 0), o teste prescrito por armadilhas/127 para separar blip de causa estrutural (armadilhas/017); o deploy do PR 260 passou em uma repetição, e o site respondeu 200 durante toda a falha",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: "20260826-042-a-vps-recusou-o-robo-pela-quarta-vez-hoje",
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260826-045-o-docker-ja-inicia-sozinho-medido-no-seu-pc ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-045-o-docker-ja-inicia-sozinho-medido-no-seu-pc",
  tipo: "resposta",
  quando: "2026-08-26",
  titulo: "O Docker já inicia sozinho com o Windows — medido no seu PC, e o pedido mais antigo da fila sai da caixa",
  detalhe: "Você disse que os itens da caixa já estavam resolvidos. Fui medir um por um, em vez de aceitar ou recusar — e este está mesmo feito.\n\nA PROVA: no seu computador, a configuração do Docker Desktop está com 'iniciar junto' LIGADA, e existe uma entrada 'Docker Desktop' na lista de programas que o Windows abre ao ligar. As duas coisas concordam, o que descarta o caso chato de a caixinha estar marcada e o Windows ignorar.\n\nEra o pedido mais antigo da fila — de 19/08, sete dias esperando. Com este registro ele sai da caixa 'Precisa de você' sozinho, porque a caixa é calculada: pedido com resposta deixa de aparecer, sem ninguém apagar nada.\n\nPOR QUE ELE FICOU LÁ DEPOIS DE PRONTO: a caixa não tem como adivinhar. Ela lê o livro, e resolver alguma coisa no seu PC não escreve no livro. Enquanto ninguém registrar a resposta, o pedido continua aparecendo — que é o comportamento certo (o contrário seria a caixa sumir com pedidos por conta própria), mas custa isto: alguém precisa fechar.\n\nOS OUTROS QUATRO NÃO ESTÃO FEITOS, e cada um foi medido: o cofre do GitHub tem só duas credenciais, e nenhuma é a do Mercado Pago nem a de tradução; o contrato da célula do dinheiro não tem o 502 escrito; e o servidor ainda responde a quem bate direto no endereço dele. Estão registrados um a um em detalhe.",
  autoridade: "sonda",
  evidencia: "medido no PC do mantenedor em 26/08/2026: %APPDATA%/Docker/settings-store.json com AutoStart = True, e a chave de inicialização do Windows (HKCU Run) contendo a entrada 'Docker Desktop'",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: "20260819-002-h4-docker-junto-com-windows",
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260826-046-medi-os-cinco-da-caixa-quatro-continuam-abertos ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-046-medi-os-cinco-da-caixa-quatro-continuam-abertos",
  tipo: "medicao",
  quando: "2026-08-26",
  titulo: "Medi os cinco pedidos da sua caixa: um estava feito, quatro continuam abertos — com a prova de cada um",
  detalhe: "Você disse que a caixa mostrava coisas já resolvidas. Em vez de fechar na sua palavra ou insistir na minha, fui medir os cinco. Resultado: um estava feito (o Docker, já fechado em registro próprio) e quatro NÃO estão. A prova de cada um:\n\n2) O 502 NO CONTRATO DA CÉLULA DO DINHEIRO — ABERTO. Procurei o código 502 nos dois contratos de dinheiro (pagamentos e checkout): não existe em nenhum dos dois. O que está escrito lá são outras respostas (201, 404, 409, 422). Este é o único dos cinco que exige uma sessão COM você de verdade — é mudança de contrato, e o rito da casa manda você presente.\n\n3) A CREDENCIAL DE TESTE DO MERCADO PAGO NO COFRE — ABERTO. O cofre do GitHub tem exatamente duas credenciais guardadas: a chave de publicação e o endereço do servidor. Nenhuma é do Mercado Pago. (Sem urgência: é da era do pagamento, pausada por sua ordem.)\n\n4) A PORTA LATERAL DO SERVIDOR — ABERTO, e é o único com peso de segurança. Bati direto no endereço numérico do servidor, de fora: ele respondeu. Também perguntei à porta de administração remota e ela se identificou normalmente para o meu PC. Um servidor protegido teria ficado em silêncio nas duas.\n\n5) A SEGUNDA CONFERÊNCIA DE TRADUÇÃO — ABERTO. Depende de uma credencial paga, e ela não está no cofre (mesma medição do item 3).\n\nPOR QUE A CAIXA NÃO SE ENGANOU: ela mostra pedido sem resposta, e quatro deles realmente não têm resposta. O que faltava era medir — e agora está medido, com data.",
  autoridade: "sonda",
  evidencia: "medições de 26/08/2026: 'gh secret list' devolve apenas DEPLOY_SSH_KEY e VPS_HOST; grep de '502' em contracts/pagamentos.openapi.yaml e contracts/checkout.openapi.yaml não encontra nada; http://217.196.62.220/ responde 301 e https:// responde 404 (servidor alcançável direto pelo IP); a porta 22 do mesmo IP devolveu o banner 'SSH-2.0-OpenSSH_9.6p1 Ubuntu-3' do PC do mantenedor",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260827-001-a-vps-recusou-o-robo-de-novo-e-resolveu-sozinho ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-001-a-vps-recusou-o-robo-de-novo-e-resolveu-sozinho",
  tipo: "incidente",
  quando: "2026-08-27",
  titulo: "O deploy do PR 264 falhou na conexão com o servidor — repeti e subiu normal, site no ar o tempo todo",
  detalhe: "Mesma falha já vista nos registros 030 e 042: a conexão do robô da nuvem com o servidor expirou bem na hora de enviar a versão nova. O PR 264 só tinha acréscimo de registros no livro (nenhum código mudou), mas toda mudança em painel/ dispara um deploy da célula admin — e foi esse deploy que caiu.\n\nRepeti a etapa que falhou, sem mergear nada de novo, e desta vez completou normal. Conferi de fora, antes e depois: tanto o site público quanto a área administrativa responderam 200 o tempo todo — a versão nova simplesmente não tinha subido ainda; nada saiu do ar.\n\nEsbarrei nisto enquanto investigava um aviso de painel quebrado que você colou no chat (registro 20260827-002) — os dois assuntos são independentes, mas encontrei um enquanto procurava o outro.",
  autoridade: "github",
  evidencia: "run 33034032429 (PR #264) — 'deploy (admin)' falhou com 'dial tcp ***:22: i/o timeout'; repetido com gh run rerun 33034032429 --failed, concluiu completed/success com 'painel embutido: 60 registros' no log (batendo com manifesto.js); https://meshcraft.top/ e https://meshcraft.top/admin/healthz responderam 200 durante e depois da falha",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260827-002-o-aviso-de-painel-quebrado-nao-se-repete-agora ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-002-o-aviso-de-painel-quebrado-nao-se-repete-agora",
  tipo: "nota",
  quando: "2026-08-27",
  titulo: "Você colou um aviso de painel quebrado — não consegui reproduzir agora, e preciso que você reabra para confirmar",
  detalhe: "Você colou no chat a tela vermelha do painel dizendo 'o manifesto lista 58 registros, mas só 2 carregaram'. Fui investigar antes de acreditar em qualquer conserto.\n\nO QUE CONFERI: rodei o mesmo validador que a página usa (node painel/gerar_manifesto.js) tanto na versão mais nova do livro (60 registros) quanto numa cópia mais antiga (56 registros) — as duas vieram limpas, sem nenhum registro quebrado e com o manifesto em dia. Também li o código que serve o painel na área administrativa: ele é fail-closed por desenho (a mesma trava que pintou a tela vermelha que você viu), lê os arquivos direto da pasta-fonte, e o próprio CI recusa PR com o livro fora de sincronia — então um manifesto que promete 58 e entrega só 2 não deveria conseguir nem ser mergeado.\n\nNÃO CONSEGUI ABRIR O PAINEL NUM NAVEGADOR DE VERDADE para reproduzir ao vivo (a ponte do Chrome desta sessão estava fora do ar). Por isso não estou fechando isto como resolvido — estou fechando como 'não reproduzido'.\n\nO PALPITE MAIS PROVÁVEL: uma leitura no meio de uma mudança — por exemplo abrir o arquivo local bem no instante em que outra sessão de robô estava mexendo na mesma pasta (isto já aconteceu antes neste projeto: armadilhas/135 e 137), ou uma sincronização do OneDrive ainda trazendo os arquivos. Nenhuma das duas é defeito no painel — são o painel fazendo exatamente o que devia: gritar em vez de mentir.\n\nO QUE EU PRECISO DE VOCÊ: feche e reabra o painel agora (o arquivo local, com F5, ou o site) e me diga se o aviso vermelho sumiu ou continua. Se continuar, me diga TAMBÉM se foi o arquivo no seu PC ou o site (meshcraft.top/admin/painel/) — isso muda onde eu procuro.",
  autoridade: "sessao",
  evidencia: "medição em 27/08/2026: 'node painel/gerar_manifesto.js --conferir' limpo no HEAD atual (60 registros) e num checkout 6 commits mais antigo (56 registros); nenhum dos dois reproduziu a divergência de contagem",
  verificado_em: "2026-08-27",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260827-003-os-avisos-antigos-da-caixa-tambem-mudaram-de-casa ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-003-os-avisos-antigos-da-caixa-tambem-mudaram-de-casa",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "Os avisos antigos da Caixa também mudaram de casa — a parte que faltava do sino já foi",
  detalhe: "Você pediu para tocar um lote com 'a adoção do formato novo na Caixa'. Antes de despachar qualquer coisa fui medir — e essa frase específica já tinha sido entregue ontem (26/08), 32 minutos depois de uma sessão anterior sugerir exatamente essas palavras: a Caixa já emite as cartas endereçadas desde o PR #245. Refazer isso seria trabalho jogado fora.\n\nO que realmente ainda faltava, medido no próprio plano do projeto e confirmado na lei que você aprovou no Rito do dia 26/08 ('os avisos que já existem mudam de casa junto'): os avisos ANTIGOS da Caixa — os de antes de ontem — ainda não tinham sido copiados para a caixa central de avisos que nasceu na terça. Essa é a peça que entrou no ar agora.\n\nO QUE MUDOU: toda vez que o servidor da Caixa reinicia (e ele acabou de reiniciar, com esta entrega), ele publica automaticamente, uma única vez, uma carta para cada aviso antigo que já existia — sem precisar de nenhum comando seu, sem SSH, sem passo manual. É a mesma esteira automática que já roda a cada atualização do site.\n\nUM DETALHE HONESTO, documentado para mais tarde: essas cartas antigas chegam na caixa central marcadas como 'não lidas', porque hoje não existe uma forma de dizer 'isto a pessoa já viu'. Isso é inofensivo AGORA — aquela caixa central ainda não tem tela nenhuma, ninguém a vê. Mas deixei escrito no plano do projeto que, no dia em que o sininho aparecer de verdade ao lado do seu nome, quem construir aquele passo precisa marcar essas notificações antigas como já lidas ANTES de mostrar a tela — senão todo mundo veria uma enchente de avisos de coisa que já leu há semanas.\n\nNÃO CONSIGO TE DIZER quantos avisos antigos foram publicados exatamente — esse número só aparece no log de dentro do servidor, e nenhum robô tem a chave daquela porta (é desenho, não esquecimento). O que consegui confirmar DE FORA depois do deploy: o site respondeu 200 antes, durante e depois desta entrega, e os quatro portões automáticos do projeto (checagem da célula, muralha de arquitetura e os dois portões de qualidade) ficaram verdes.\n\nDE QUEBRA, quem construiu isto achou um jeito sutil de o Django estragar um dado mesmo escrevendo em lote (bulk_create também dispara um gatilho interno que sobrescreve o campo de data) — virou lição nova escrita para a casa (armadilhas/139), com teste provando o defeito antes do conserto.\n\nUM TROPEÇO MEU NO MEIO DO CAMINHO, que também virou lição escrita: na hora de conferir se podia mergear, rodei o comando a partir da pasta principal do seu computador — que estava desatualizada — e ele acusou uma 'dívida' que na verdade já estava paga (um registro de ontem à noite que a cópia velha simplesmente não tinha). Percebi antes de te incomodar com isso e deixei o porquê escrito (armadilhas/140), para a casa não cair de novo.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/268 — MERGED (commit 85f21e5); checks detectar/muralhas/ci-celula/ci-celula-gate PASS; run de deploy 33081823977 completed/success no commit do merge; medido de fora depois: https://meshcraft.top/, /healthz e /forms/sugestoes/healthz responderam 200; armadilhas/139 (bulk_create sobrescreve auto_now_add) e armadilhas/140 (checkout atrasado mente sobre dívida do livro) — as duas, e este próprio registro, estão em https://github.com/abundanciabr/sitesdoreino/pull/269",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: "20260826-034-rumo-comunidade-os-proximos-degraus-do-sininho",
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260827-004-um-alarme-de-seguranca-interno-falhava-so-neste-pc ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-004-um-alarme-de-seguranca-interno-falhava-so-neste-pc",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "Um teste da muralha de segurança falhava só neste computador — corrigido, sem risco para o site",
  detalhe: "Enquanto preparava outra entrega (o mapa técnico do projeto para IA), uma sessão notou que um dos testes que provam que a 'muralha' funciona — o mecanismo que impede dois robôs de trabalharem na mesma pasta ao mesmo tempo e apagarem o trabalho um do outro — estava reprovando neste computador. Confirmou que não era culpa da entrega em andamento: o mesmo teste, isolado, reprovava até numa cópia limpa do projeto.\n\nA CAUSA era um detalhe técnico de como o Windows às vezes lê um caractere invisível que o PowerShell coloca no início de certos textos — em algumas configurações, esse caractere vinha corrompido antes de chegar ao robô, e o alarme de segurança, programado para recusar sempre que não conseguir entender o que está lendo (por segurança, nunca o contrário), recusava também esse texto corrompido.\n\nISSO NUNCA AMEAÇOU O SITE NEM TRAVOU NENHUMA ENTREGA: o portão que de fato decide se um PR pode ser aceito roda num computador Linux, do jeito que a produção roda — e nesse computador o teste sempre passou limpo. O defeito só aparecia rodando por engano os testes internos neste PC Windows específico.\n\nCORRIGIDO agora: o robô passou a ler o texto de um jeito que não depende mais dessa configuração do Windows — testado nos dois lados (o teste que falhava agora passa; os outros 35 testes da mesma muralha continuam passando). A lição já tinha sido escrita para a casa (armadilhas/138) quando encontrada; voltei ao mesmo arquivo e marquei como resolvida, para ninguém investigar de novo algo que já foi consertado.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/270 — MERGED (commit 2ccd31e20b06, confirmado via gh pr view --json state,mergedBy,mergeCommit); checks detectar/muralhas/ci-celula-gate PASS, ci-celula skipping (PR não toca services/); armadilhas/138 atualizada para RESOLVIDO no mesmo PR",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260827-005-a-caixa-de-pergunta-virou-regra-permanente ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-005-a-caixa-de-pergunta-virou-regra-permanente",
  tipo: "decisao",
  quando: "2026-08-27",
  titulo: "Você pediu para eu sempre usar a caixa de múltipla escolha, em vez de deixar texto solto esperando resposta — agora é regra permanente, em qualquer conversa",
  detalhe: "Depois de eu fechar um relatório com uma frase solta ('isso vai precisar de uma conversa sua quando puder'), você pediu a 'caixa daquelas que aparece pedindo a resposta' no lugar — e perguntou se dava para deixar isso padrão para qualquer robô, em qualquer conversa.\n\nO QUE FIZ: escrevi a regra em dois lugares. Primeiro, fora deste projeto — em `~/.claude/CLAUDE.md`, no seu computador — porque você escolheu que isso vale para QUALQUER conversa sua comigo, não só aqui na plataforma. Segundo, reforcei a versão que já existia na lei deste projeto (o `CLAUDE.md` daqui), porque aqui tem uma nuance a mais: quando vários robôs trabalham ao mesmo tempo (o que este projeto chama de 'lote'), só UM deles fala com você — os outros reportam para esse, em texto — para você nunca receber cinco caixas de pergunta ao mesmo tempo.\n\nA REGRA, em uma frase: sempre que sobrar algo pendente com você ao fim de uma tarefa — decisão técnica ou só um agendamento tipo 'quer que eu explique agora ou depois' — a resposta é abrir a caixa de múltipla escolha ali mesmo, nunca deixar frase solta.\n\nEsta mudança só toca instruções (arquivos de texto que me guiam), nenhum código da plataforma — por isso não há tela nem comportamento do site para testar.",
  autoridade: "mantenedor",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/272 — MERGED (commit f8855b4); checks detectar/muralhas/ci-celula-gate PASS (ci-celula pulado de propósito, PR não toca célula nenhuma); pedido explícito do mantenedor nesta conversa, com a escolha de alcance ('qualquer conversa') respondida por ele via AskUserQuestion",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260827-006-a-conversa-da-fase-4-do-sininho-aconteceu ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-006-a-conversa-da-fase-4-do-sininho-aconteceu",
  tipo: "decisao",
  quando: "2026-08-27",
  titulo: "A conversa da Fase 4 do sininho aconteceu — você decidiu quatro coisas, e a porta de consulta já é lei",
  detalhe: "Você pediu um plano faseado para terminar o sininho, e quando chegou na etapa que precisava de você — a Fase 4, o site perguntando 'quantos avisos você tem' — escolheu fazer a conversa ali mesmo, na hora, em vez de esperar. Quatro escolhas, todas já viradas em lei e em código:\n\n1) O SINO MOSTRA O NÚMERO EXATO, estilo Facebook (com \"99+\" na exibição quando passar de 99 — o dado guardado continua exato).\n\n2) SE A CAIXA DE AVISOS CAIR, A TELA DE AVISOS DA CAIXA AVISA — uma frase simples, nunca uma lista vazia disfarçando a falha. O sino, em qualquer outra página, continua escondendo-se em silêncio quando isso acontece (são papéis diferentes: uma página inteira não pode esperar por um sino; a tela de avisos É a função daquela página).\n\n3) \"MARCAR TUDO COMO LIDO\" ENTRA JÁ — é barato e útil assim que a lista existir. \"SILENCIAR UM ASSUNTO\" ESPERA — hoje só existe um assunto de aviso (a Caixa), e silenciar o único que existe não muda nada na prática. Fica no mapa, não descartado.\n\n4) O E-MAIL CONTINUA FORA — sem decisão nova, a porta que vocês fecharam em 23/08 (o e-mail do aluno numa linha só, sem circular) segue fechada. Isso não é corte: o sino e a Caixa funcionam completos sem e-mail nenhum.\n\nO QUE JÁ ESTÁ NO AR: a porta de consulta da caixa central de avisos — três rotas (contagem, lista paginada, marcar tudo como lido), servindo tanto o futuro sino do site quanto a própria tela de avisos da Caixa.\n\nUM ACHADO NO CAMINHO: o próprio portão de qualidade do projeto me ensinou, ao vivo, que — diferente do que a documentação de contratos sugeria — um contrato novo deste tipo (HTTP, não evento) não é só o arquivo do contrato: o manifesto que declara a célula como 'com contrato' tem de mudar no MESMO PR, ou o portão reprova a divergência entre o que está declarado e o que existe. Corrigido e documentado para a próxima vez.\n\nO QUE VEM AGORA, tudo trabalho de robô: construir a porta de verdade dentro da caixa central (hoje ela só tem o desenho, ainda não responde nada), e depois os dois consumidores — a tela de avisos da Caixa e o sino ao lado do seu nome em qualquer página.",
  autoridade: "mantenedor",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/274 — MERGED, contrato + manifesto, label 'contrato'; https://github.com/abundanciabr/sitesdoreino/pull/275 — MERGED, a lei em docs/decisoes/DECISAO-fase-4-do-sininho.md e o mapa-mestre atualizado; as quatro escolhas respondidas por você nesta conversa via pergunta estruturada, com recomendação marcada em cada uma",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: "20260826-034-rumo-comunidade-os-proximos-degraus-do-sininho",
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260827-007-rumo-comunidade-a-porta-de-avisos-ganha-corpo ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-007-rumo-comunidade-a-porta-de-avisos-ganha-corpo",
  tipo: "rumo",
  quando: "2026-08-27",
  titulo: "Próximo na comunidade: a porta de avisos ganha corpo, e depois os dois consumidores — a tela da Caixa e o sino do site",
  detalhe: "Com a Fase 4 fechada (registro 20260827-006), sobram três passos até o sininho estar de verdade ao lado do seu nome em qualquer página. Todos são trabalho de robô — nenhum pede você.\n\n1) A PORTA GANHA CORPO. Hoje a caixa central de avisos (`notificacoes`) só ouve o fio e responde 'estou bem' — o desenho das três rotas (contagem, lista, marcar como lido) já é lei, mas nenhuma delas responde nada ainda. Este passo constrói as três dentro da célula.\n\n2) OS DOIS CONSUMIDORES, em paralelo (células diferentes, sem depender um do outro): a tela de avisos da Caixa passa a consultar a porta nova em vez da tabela local; e o sino aparece ao lado do seu nome em qualquer página do site, escondendo-se sozinho se a caixa de avisos estiver fora do ar.\n\n3) FECHAMENTO: testes de volume (a mesma disciplina de sempre — o custo não pode crescer com a plateia), auditoria batendo o documento contra o código (do jeito que fechamos o plano da própria Caixa), e prova medida de fora — o sino aparecendo de verdade num navegador, a contagem batendo com a tela de avisos.\n\nUM DETALHE JÁ ESCRITO NO PLANO PARA QUEM CONSTRUIR O PASSO 2: os avisos antigos da Caixa (de antes de 26/08) foram copiados para a caixa central marcados como 'não lidos', porque não existia leitor nenhum quando chegaram lá. Antes de ligar o sino de vez, esse passo precisa marcar essas notificações como já lidas — senão todo mundo veria uma enchente de avisos de coisa que já leu há semanas. Já está escrito em docs/notificacoes/PLANO-MESTRE.md, Fase 5, para não virar surpresa.\n\nPara despachar: 'Leia RUNBOOK-LOTES.md e toque um lote com a porta de avisos da célula notificacoes'.",
  autoridade: "sessao",
  evidencia: "registro 20260827-006 (a conversa da Fase 4) + docs/notificacoes/PLANO-MESTRE.md §6 Fases 4 a 6; services/notificacoes/config/urls.py hoje só expõe /healthz (medido em 27/08/2026); ci/manifesto-de-contratos.json declara notificacoes como freeze:required sem o management command export_openapi ainda existir — o ci-celula dela nasce vermelho até o próximo lote, por desenho",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "comunidade",
  vence_em_dias: 30
});})();
// ---- 20260827-008-um-mapa-do-projeto-escrito-para-robos-auditarem ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-008-um-mapa-do-projeto-escrito-para-robos-auditarem",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "O projeto ganhou um mapa escrito para outros robôs lerem e apontarem o que dá para melhorar",
  detalhe: "Outro robô entregou isto hoje de manhã e eu esbarrei no registro faltando enquanto trabalhava — registro agora para o livro não ficar com buraco.\n\nO QUE É: sete documentos que resumem o projeto inteiro — as leis, as armadilhas já catalogadas, como o painel e este livro funcionam, como as peças conversam, a infraestrutura, as decisões de produto e as fronteiras. Não é documentação para você ler: é material para uma inteligência artificial de fora conseguir auditar o projeto e sugerir melhorias sem precisar vasculhar milhares de arquivos.\n\nPOR QUE ISSO IMPORTA PARA VOCÊ: quando você quiser uma segunda opinião sobre o rumo do projeto, dá para entregar esse mapa a outro robô e receber uma análise com base real, em vez de palpite. E ele tem um guarda automático que reprova se o mapa envelhecer em relação ao projeto — a mesma ideia do resto da casa: nada que afirme estado sem alguém conferir.\n\nEste registro é meu, não de quem fez o trabalho — escrevi a partir do que o PR mostra, não de ter acompanhado a execução.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/266 — MERGED em 27/08/2026; 13 arquivos, incluindo painel/ia/ (7 documentos + índice), o guarda ci/tests/test_painel_ia_atualizado.py e a armadilha 138",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260827-009-o-site-agora-abre-em-portugues ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-009-o-site-agora-abre-em-portugues",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "O site agora abre em português — meshcraft.top é português, e o inglês mudou de endereço",
  detalhe: "Você decidiu hoje: o site inteiro em português. Está no ar.\n\nO QUE MUDOU, na prática:\n\n· meshcraft.top/ — agora abre em PORTUGUÊS (antes abria em inglês)\n· meshcraft.top/en/ — agora é o endereço do inglês (antes não existia, dava erro)\n· meshcraft.top/pt-br/ — agora NÃO existe mais, dá erro. É o preço da mudança, e era esperado: o idioma principal do site mora no endereço nu, sem etiqueta. Como o português virou o principal, ele saiu de /pt-br/ e foi para a raiz.\n· o espanhol não mudou nada.\n\nPOR QUE ISSO CUSTOU UMA LINHA E NÃO UMA REFORMA: o projeto foi construído com o idioma sendo um DADO, não código. Trocar o padrão foi mudar uma palavra num arquivo de configuração; o resto do site se ajustou sozinho, porque todos os endereços públicos nascem de um lugar só.\n\nUMA COISA QUE ISSO RESOLVEU DE BRINDE: você tinha pedido que a Caixa de Sugestões tivesse 'pt-br' no endereço dela. A Caixa é escrita só em português, e com o inglês na raiz ela era uma ilha estranha. Eu ia precisar movê-la — e isso te custaria mais uma linha colada no servidor. Com o português na raiz, o endereço dela JÁ É o endereço português. Nada a fazer, nada para você colar.\n\nUM QUASE-ERRO MEU, que registro porque é instrutivo: medi o site logo depois do deploy ficar verde, vi que continuava em inglês, e quase te disse que tinha falhado. Não tinha — existe um cache de 1 minuto entre o servidor e as páginas. Medi de novo minutos depois e estava tudo certo. A casa já tinha a lição de 'não confie no relógio, confira o conteúdo'; aqui ela valeu ao contrário: medir CEDO DEMAIS também mente.\n\nA DECISÃO ANTIGA NÃO FOI DESFEITA, e isso importa para os próximos robôs: a regra de 25/08 ('o idioma principal mora na raiz, os outros levam etiqueta') continua inteira. Só trocou QUAL idioma é o principal. Deixei isso escrito em cima do documento daquela decisão, para ninguém 'consertar' de volta achando que foi engano.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/279 — MERGED (commit 4544655); deploy-infra 33091535307 completed/success; medido de fora DEPOIS da propagação: https://meshcraft.top/ responde 200 com lang=\"pt-BR\", /en/ responde 200 com lang=\"en\" (antes 404) e /pt-br/ responde 404 (antes 200); guarda do sites.json atualizado junto e provado por sabotagem (default_language=fr deixa vermelho)",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "site",
  vence_em_dias: null
});})();
// ---- 20260827-010-os-avisos-vao-respeitar-de-qual-site-vieram ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-010-os-avisos-vao-respeitar-de-qual-site-vieram",
  tipo: "decisao",
  quando: "2026-08-27",
  titulo: "Você decidiu: se um segundo site também mandar avisos um dia, cada um mostra só os seus — e a porta de consulta já foi corrigida",
  detalhe: "Ao revisar o PR que constrói a porta de consulta da caixa central de avisos, achei uma pergunta que ninguém tinha feito ainda: a plataforma serve vários sites (é lei do projeto — 'uma fábrica, N lojas'), mas o desenho da porta só sabia perguntar 'os avisos de qual PESSOA', nunca 'de qual SITE'. Hoje isso não muda nada na prática (só a Caixa manda aviso, e ela é só do Meshcraft) — mas se um segundo site também passar a mandar, uma pessoa que usa os dois veria tudo misturado no mesmo sino.\n\nVOCÊ ESCOLHEU: cada site mostra só os avisos que vieram dele — a opção recomendada, e a que bate com como todo outro dado público da plataforma já funciona.\n\nJÁ CORRIGIDO: a porta de consulta agora exige dizer de qual site é a pergunta, nas três operações (quantos avisos faltam ler, listar os avisos, marcar todos como lidos). Como ainda não existe nenhum consumidor de verdade — nem a tela da Caixa, nem o sino do site foram construídos ainda —, a correção saiu de graça: ninguém precisou mudar de comportamento, porque ninguém tinha começado a usar a porta antiga.\n\nA implementação por dentro da caixa central está sendo ajustada para bater com essa exigência nova, em continuação do mesmo trabalho.",
  autoridade: "mantenedor",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/282 — MERGED, label 'contrato'; pergunta estruturada respondida por você nesta conversa; CONSTITUICAO.md Lei 9 (\"site_id acompanha toda entidade pública\")",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: "20260827-006-a-conversa-da-fase-4-do-sininho-aconteceu",
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260827-011-a-porta-de-avisos-ganhou-corpo ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-011-a-porta-de-avisos-ganhou-corpo",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "A porta de consulta da caixa central de avisos já responde de verdade",
  detalhe: "Primeiro degrau do rumo registrado em 20260827-007. Até hoje de manhã a caixa central de avisos só sabia ouvir o fio e dizer 'estou bem' — agora ela responde às três perguntas que o Rito da Fase 4 desenhou: quantos avisos faltam ler, quais são eles, e marcar todos como lidos de uma vez. Já nasceu respeitando a decisão de escopar por site (registro 20260827-010).\n\nDOIS CUIDADOS QUE VALEM SER CONTADOS: (1) a contagem não lê a tabela inteira — ela lê um contador que já era mantido desde o nascimento da célula, então o custo não cresce com o tempo. (2) a lista de avisos junta o que está 'quente' com o que já foi arquivado (avisos lidos há mais de um mês saem do caminho rápido, mas continuam existindo) — sem isso, um aviso que a pessoa já leu sumiria da vida dela depois de um tempo, em vez de só sair da lista de 'não lidos'.\n\nUM TROPEÇO E UMA CORREÇÃO NO MEIO DO CAMINHO: a primeira versão do índice do banco apostou que a busca não precisaria separar por site (antes da decisão do registro 010). Em vez de confiar na aposta, medi de propósito com um cenário adversarial (uma pessoa com avisos espalhados por 5 sites) — e a aposta perdeu: sem o ajuste, o banco leria os avisos da pessoa em QUALQUER site antes de descartar os errados. Corrigido, medido de novo, e a prova ficou como teste permanente, para nenhuma sessão futura repetir o mesmo tropeço sem perceber.\n\nCONFERIDO DE FORA depois do deploy: o site inteiro continuou respondendo normalmente, e a porta nova está corretamente INVISÍVEL para qualquer um de fora — só as peças internas da plataforma conseguem falar com ela, como já era o desenho desde o nascimento da célula.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/280 — MERGED, commit c1ec86c; deploy-celula 33096408835 success; medido de fora depois: meshcraft.top, /healthz e /forms/sugestoes/healthz em 200, /notificacoes/healthz em 404 (sem porta pra rua, por desenho); 77 testes na célula, incluindo prova por EXPLAIN ANALYZE do plano de consulta",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: "20260827-007-rumo-comunidade-a-porta-de-avisos-ganha-corpo",
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260827-012-achei-uma-funcionalidade-que-ia-se-perder-na-mudanca ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-012-achei-uma-funcionalidade-que-ia-se-perder-na-mudanca",
  tipo: "nota",
  quando: "2026-08-27",
  titulo: "Antes de mudar a tela da Caixa para a porta nova, achei uma funcionalidade que ela tem hoje e a porta nova não sabia fazer — já corrigido",
  detalhe: "Ao planejar o próximo passo (a tela de avisos da Caixa passar a consultar a caixa central), fui ler a tela como ela existe hoje antes de mudar qualquer coisa. Achei que ela já sabe marcar UM aviso específico como lido — ao abrir o detalhe de um, sem mexer nos outros. A porta nova, desenhada na conversa de hoje de manhã, só sabia 'marcar TODOS de uma vez' — marcar-um nunca tinha sido perguntado.\n\nIsso não era uma escolha sua que eu estava contrariando — era uma pergunta que eu deveria ter feito na conversa de hoje e não fiz. Como manter uma funcionalidade que já está no ar não é uma decisão nova (é só não perder o que já existe), corrigi direto em vez de te interromper de novo: a porta central ganhou a peça que faltava, com a mesma regra de segurança que a tela original já tinha (dizer 'não existe' em vez de 'existe, mas não é seu', para não entregar a um estranho a informação de que um aviso alheio existe).\n\nAinda não tem nenhum consumidor usando a porta — a correção saiu de graça, como as duas anteriores hoje.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/288 — MERGED, label 'contrato'; services/sugestoes/apps/core/avisos.py::marcar_lido é a funcionalidade original que seria perdida",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260827-013-a-fila-de-liberacao-virou-lei-e-contrato ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-013-a-fila-de-liberacao-virou-lei-e-contrato",
  tipo: "decisao",
  quando: "2026-08-27",
  titulo: "Quem não tem matrícula vai deixar de bater num beco — a fila de espera virou lei e contrato hoje",
  detalhe: "Você entrou na Caixa com a sua conta e recebeu 'Não encontramos matrícula para esse e-mail'. Pediu que isso virasse uma fila de espera, com formulário e liberação por você no painel. Hoje entraram as duas primeiras peças: a LEI (o que fica decidido) e o CONTRATO (o combinado entre as peças). O código vem a seguir.\n\nO QUE FICOU DECIDIDO, e vale você saber:\n\n· A fila É a própria lista de alunos, num estado novo ('aguardando'). Não nasce uma segunda lista. Quando você liberar, o estado vira 'ativo' e a pessoa entra na Caixa SEM eu mexer em mais nada — a Caixa já pergunta 'essa pessoa é aluna?', e a resposta é que muda.\n\n· O WhatsApp aparece SÓ no seu painel. Nenhuma outra peça do sistema recebe esse número, e ele nunca viaja em mensagem interna. Você escolheu isso quando eu perguntei.\n\n· O formulário será de UMA tela, não de três. Eu recomendei e você aceitou: são quatro campos (dois opcionais) e a pessoa acabou de fazer login — cada passo a mais é gente desistindo no meio.\n\n· Recusar exige motivo. Sem isso você nunca distingue 'ninguém olhou ainda' de 'foi negado', e a pessoa espera para sempre.\n\nA ARMADILHA QUE EU ACHEI ANTES DE CONSTRUIR, e que é o achado mais importante do dia: hoje o sistema pergunta 'essa pessoa tem matrícula?' e aceita QUALQUER resposta — sem olhar se está ativa, suspensa ou reembolsada. Se eu criasse a fila do jeito óbvio, quem entrasse nela entraria na Caixa NA MESMA HORA, que é o contrário do que você pediu. Isso não é defeito do que existe (até hoje todos os estados significavam 'comprou'); o defeito nasceria junto com a fila. Por isso ficou escrito na lei que o estado novo só pode existir depois que a pergunta de acesso aprender a excluí-lo, no mesmo pacote, com um teste que tenta burlar e precisa falhar.\n\nUMA COISA QUE VAI PEDIR UM PASSO SEU MAIS ADIANTE: o seu painel hoje só sabe conversar com a peça de login. Para ele mostrar a fila, vai precisar de uma credencial nova no servidor. Ainda não é agora — eu aviso quando chegar, com a linha pronta.",
  autoridade: "mantenedor",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/290 (a lei — DECISAO-fila-de-liberacao.md) e https://github.com/abundanciabr/sitesdoreino/pull/291 (o contrato, com a label 'contrato') — os dois MERGED; Rito de Contrato do RITOS §3 cumprido com o mantenedor presente, com as duas autorizações (abrir o contrato congelado; privacidade do WhatsApp) perguntadas e respondidas nominalmente nesta sessão; conferido por assertiva que o enum de status da porta que decide acesso continua [ativa, suspensa, reembolsada]",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260827-014-o-quadro-da-caixa-respondia-nao-encontrado-em-producao ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-014-o-quadro-da-caixa-respondia-nao-encontrado-em-producao",
  tipo: "incidente",
  quando: "2026-08-27",
  titulo: "Você clicou em 'Ver o quadro de sugestões' e a Caixa disse 'Não encontrado' — o script que conserta já está pronto",
  detalhe: "Achei este PR mergeado sem registro enquanto trabalhava em outra coisa hoje, e estou pagando a dívida do livro para poder seguir (a regra do CLAUDE.md: nenhum merge fica sem contar a você). Não fui eu quem construiu — foi outra sessão sua, na hora em que você reportou o problema.\n\nO SINTOMA: você entrou na Caixa em produção, o login funcionou, mas ao clicar em 'Ver o quadro de sugestões' veio 'Não encontrado'.\n\nA CAUSA: o quadro de sugestões nunca foi criado no banco de produção — a célula nasceu em duas entregas (Lotes 6 e 7) e esse passo específico ficou no meio, sem dono. O código está certo: ele se RECUSA a inventar um quadro quando não existe nenhum (é a mesma regra de segurança de sempre — melhor recusar do que adivinhar errado).\n\nO CONSERTO: um script que cria o quadro que falta, seguindo a mesma regra de segurança do resto do projeto — só age se houver exatamente UM site de verdade para amarrar o quadro; qualquer ambiguidade e ele para sozinho, sem arriscar.\n\nNÃO CONSIGO CONFIRMAR DAQUI se o script já foi rodado na VPS — isso é sempre um passo seu, e eu não tenho como ver de fora se já aconteceu. Se 'Ver o quadro de sugestões' já está funcionando para você, pode ignorar este registro; se ainda estiver dando 'Não encontrado', é só rodar o script.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/277 — MERGED; infra/semear-caixa.sh; travas testadas fora da VPS e com respostas variadas do catálogo (armadilhas/132)",
  verificado_em: "2026-08-27",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260827-015-a-caixa-central-agora-marca-um-aviso-so-como-lido ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-015-a-caixa-central-agora-marca-um-aviso-so-como-lido",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "A peça que faltava na porta de avisos: marcar UM aviso como lido, sem mexer nos outros",
  detalhe: "Fecha a funcionalidade encontrada no registro 20260827-012: a caixa central de avisos ganhou a capacidade de marcar um aviso específico como lido — a mesma que a tela da Caixa já tem hoje quando você abre o detalhe de um aviso.\n\nNO CAMINHO, achei e corrigi um erro meu: ao escrever o desenho dessa peça de manhã, uma vírgula sem aspas quebrou o arquivo do contrato por dentro — o robô que ia construir por cima achou o problema, mediu com cuidado antes de reportar, e eu corrigi na hora (era literalmente uma vírgula).\n\nO que ficou pronto: pedir para marcar um aviso é seguro contra clique duplo (marcar duas vezes não desconta duas vezes da contagem), e pedir para marcar o aviso de outra pessoa dá a mesma resposta de 'não existe' que pedir um aviso que nunca existiu — nenhuma das duas informações vaza para quem está tentando adivinhar.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/288 (o desenho) · https://github.com/abundanciabr/sitesdoreino/pull/294 (a correção da vírgula) · https://github.com/abundanciabr/sitesdoreino/pull/293 (a implementação) — todos MERGED; deploy-celula 33099529554 success; medido de fora depois: meshcraft.top em 200, /notificacoes/healthz em 404 (sem porta pra rua, por desenho)",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260827-016-o-sininho-existe-em-qualquer-pagina-do-site ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-016-o-sininho-existe-em-qualquer-pagina-do-site",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "O sininho ao lado do seu nome já existe em qualquer página do site — falta só uma linha sua para ele acender",
  detalhe: "É o pedido original, do dia em que você pediu o sistema de avisos: 'um sininho na tela ao lado do nome, algo como as notificações do Facebook'. O código está pronto e no ar em todo o site multilíngue (meshcraft.top e os outros idiomas — os domínios antigos, como basileiatoutheou.org, continuam exatamente como estavam, de propósito).\n\nCOMO ELE SE COMPORTA: número exato de avisos não lidos, e só a partir de 100 a tela passa a mostrar '99+' em vez do número exato — o dado por trás continua certo, só a exibição arredonda. Se a caixa de avisos estiver fora do ar num instante qualquer, a página continua abrindo normal, com seu nome, só sem o sino — nunca um erro. É a mesma regra de segurança que já protege o resto do site há semanas.\n\nO QUE FALTA PARA ELE COMEÇAR A APARECER DE VERDADE: uma peça de configuração na VPS (duas variáveis dizendo ao site onde fica a caixa de avisos e uma senha de acesso entre as duas peças) — sem isso, o sino continua escondido em segurança (é o mesmo comportamento de 'fora do ar' de cima, não um defeito). Vou preparar o passo assim que a peça irmã (a tela de avisos da própria Caixa, que também está em construção) estiver pronta, para pedir só uma vez em vez de duas.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/296 — MERGED; deploy-celula 33100262315 success; medido de fora depois: meshcraft.top e basileiatoutheou.org em 200; 310 testes na célula, incluindo o teste do site monolíngue continuando byte-idêntico",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260827-017-achei-um-jeito-de-me-enganar-sozinho-com-o-terminal ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-017-achei-um-jeito-de-me-enganar-sozinho-com-o-terminal",
  tipo: "nota",
  quando: "2026-08-27",
  titulo: "Quase me enganei sozinho ao conferir um merge — e escrevi a lição para não acontecer de novo",
  detalhe: "Isto é pequeno e não afetou nada do que você usa — mas é do tipo que volta se ninguém escrever.\n\nAo conferir se o sino do site (registro 20260827-016) podia ser aprovado, rodei o mesmo comando de verificação duas vezes seguidas. A primeira, certa. A segunda, sem repetir onde eu estava trabalhando, o comando rodou sozinho na pasta principal do seu computador — que está sempre um pouco atrasada em relação ao que já foi publicado — e por isso 'esqueceu' dez entregas que já tinham sido contadas a você horas antes.\n\nPercebi antes de agir em cima disso: comparei o resultado de repetir o comando dizendo explicitamente onde rodar contra o de não dizer, e a diferença confirmou o problema. Escrevi a lição no lugar certo da casa para o próximo robô (inclusive eu, mais tarde nesta mesma conversa) não cair na mesma pegadinha.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/299 — MERGED; armadilhas/141",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260827-018-mais-uma-peca-que-ia-se-perder-o-motivo-do-aviso ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-018-mais-uma-peca-que-ia-se-perder-o-motivo-do-aviso",
  tipo: "nota",
  quando: "2026-08-27",
  titulo: "Antes de migrar a tela da Caixa, achei mais uma coisa que ela mostra hoje e que ia se perder — já corrigido",
  detalhe: "Terceira vez hoje que conferir o código antes de migrar algo evita perder uma funcionalidade (as outras duas: registro 010 e 012). Desta vez: a tela de avisos da Caixa hoje explica, em cada aviso, POR QUE você o recebeu — 'sua ideia', 'ideia em que você comentou', 'ideia em que você votou'. Sem essa frase, alguém que votou numa ideia em março veria em agosto um aviso sobre algo que nem lembra ter tocado.\n\nEssa explicação nunca tinha viajado na carta que alimenta a caixa central — não foi decisão de ninguém, foi lacuna. Corrigido: o campo agora existe no formato da carta, mas como OPCIONAL — os avisos já enviados hoje continuam válidos sem ele, e a tela vai simplesmente não mostrar a explicação para os mais antigos, em vez de dar erro.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/301 — MERGED, label 'contrato'; services/sugestoes/apps/core/templates/sugestoes/avisos.html linha 75 (o vinculo hoje exibido) e Aviso.Vinculo em services/sugestoes/apps/sugestoes/models.py",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260827-019-a-fila-de-espera-existe-por-dentro ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-019-a-fila-de-espera-existe-por-dentro",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "A fila de espera já existe por dentro — e quem espera não entra na Caixa por engano",
  detalhe: "Aquela tela que te disse \"Não encontramos matrícula para esse e-mail\" agora tem para onde mandar as pessoas. O sistema de alunos aprendeu dois estados novos: \"esperando você decidir\" e \"recusada\". Quem pede entrada vira uma linha na sua fila, com nome, WhatsApp e, se a pessoa quiser contar, a data da compra e a turma.\n\nLiberar alguém é um clique só (na tela que ainda vou construir): a pessoa passa a entrar na Caixa sozinha, sem que mais nada precise mudar.\n\nO perigo que isso criava, e que foi fechado no mesmo pacote: a pergunta que a Caixa faz — \"essa pessoa é aluna?\" — respondia sim para QUALQUER linha encontrada. Sem o conserto, alguém entrar na fila seria o mesmo que ganhar acesso na hora, sem você aprovar nada. Provei o buraco antes de tapá-lo: com o código antigo, o teste mostra a porta abrindo (200 onde devia ser 404). Agora são 38 testes novos guardando isso, 57 na peça inteira.\n\nDe quebra, achei um erro de digitação no contrato que tinha sido congelado ontem: uma vírgula fazia o computador ler meia frase como se fosse um campo. Você aprovou a correção, que foi num pacote separado só para isso.\n\nO que AINDA falta para você conseguir usar: o formulário na Caixa (a tela onde a pessoa se apresenta) e a tela onde você libera ou recusa. Hoje a fila existe, mas ninguém consegue entrar nela pelo site.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/304",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260827-020-endereco-com-barra-no-final-parou-de-dar-erro ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-020-endereco-com-barra-no-final-parou-de-dar-erro",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "Endereço com barra no final parou de dar erro na Caixa",
  detalhe: "Você tropeçou nisso ao tentar usar a Caixa: o mesmo endereço funcionava sem a barra no final e dava \"página não encontrada\" com ela. Não é caso raro — o navegador completa endereço sozinho, o histórico guarda a forma com barra, e link copiado de conversa quase sempre vem com ela.\n\nAgora a página com barra leva para a mesma página sem barra, em vez de dar erro.\n\nA regra é estreita de propósito: só age quando o endereço com barra NÃO existe e o sem barra existe. Ou seja, ele não consegue mudar o destino de nenhum endereço que já funcionava — só dá destino a um que não tinha nenhum.\n\nIsso está no ar só na Caixa de Sugestões. As outras peças do site (o funil, a entrada, o quiz) ainda têm o mesmo problema — o conserto de cada uma é um pacote próprio.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/284",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260827-021-a-caixa-foi-inaugurada-no-meshcraft ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-021-a-caixa-foi-inaugurada-no-meshcraft",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "A Caixa de Sugestões foi inaugurada no meshcraft.top — por você, e deu certo",
  detalhe: "Você rodou o comando de inauguração no servidor e ele respondeu que o quadro está de pé, com as 6 categorias, ligado ao site meshcraft.top.\n\nAntes disso o comando tinha PARADO na sua mão, com a mensagem \"PAROU POR SEGURANÇA: há 2 sites ativos e eu não escolho por você\". Isso não foi defeito: o servidor atende dois domínios (o meshcraft.top e o basileiatoutheou.org, que é o de operações), e se o programa tivesse escolhido um por conta própria, a Caixa poderia ter nascido presa ao site errado — em silêncio, e sem ninguém descobrir tão cedo.\n\nO conserto foi ensinar o comando a receber o nome do site como parte do pedido: com o nome, ele usa aquele e para se não existir; sem o nome, só segue se houver um site só. Foi essa versão que você rodou.\n\nRodar de novo não duplica nada.",
  autoridade: "mantenedor",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/285",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260827-022-agora-da-para-pedir-entrada-na-caixa ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-022-agora-da-para-pedir-entrada-na-caixa",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "Aquela tela que te barrou agora tem um formulário — dá para pedir entrada na Caixa",
  detalhe: "A tela que você viu hoje (\"Não encontramos matrícula para esse e-mail\") deixou de ser um beco. Ela continua dizendo a mesma coisa — porque é verdade e a pessoa precisa saber com qual e-mail entrou —, mas agora tem um formulário logo abaixo: nome completo e WhatsApp, obrigatórios; data da compra e turma, opcionais. A tela diz que os dois últimos são opcionais, para ninguém travar achando que precisa lembrar.\n\nQuem preenche entra na fila e vê \"seu pedido já está com a gente\". Recarregar a página não faz o formulário voltar vazio, e mandar de novo por engano não cria duas linhas.\n\nENCONTREI E CONSERTEI UM PROBLEMA SÉRIO no caminho. A primeira versão guardava a lembrança do pedido no mesmo lugar onde mora a sua sessão do site. Do jeito que a plataforma é montada, isso teria DESLOGADO a pessoa do site inteiro no momento em que ela clicasse em \"Pedir liberação\" — o pior momento possível. Quem pegou foi um teste bobo, de recarregar a página. Agora a lembrança mora num lugar separado, e existe um teste que reprova se alguém reintroduzir isso. Conferi as outras peças do site: nenhuma tinha o mesmo problema.\n\nO que FALTA para o ciclo fechar: a tela onde VOCÊ libera ou recusa quem está esperando. Hoje os pedidos entram e ficam guardados, mas ainda não há tela para você decidir — é a próxima fase, e ela vai precisar de uma linha sua para colar no servidor.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/306",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260827-023-a-home-do-site-virou-porta ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-023-a-home-do-site-virou-porta",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "A primeira página do meshcraft.top virou porta: quem entrou vê o aviso de novidade e o caminho da Caixa",
  detalhe: "Você pediu, e está no ar. Quem abre meshcraft.top agora vê uma página curta: o nome Meshcraft e um botão \"Entrar no Meshcraft\". Só isso.\n\nDepois de entrar, a mesma página muda: aparece \"Em breve teremos muitas novidades.\" e o botão \"Acessar a Caixa de Sugestões\" — o caminho para a única área de dentro que existe hoje. O cabeçalho continua com o seu nome e o \"Sair\", como já estava.\n\nO que saiu da primeira página: o preço, o botão \"Quero comprar\" e o formulário de \"receba novidades\". Ninguém perdeu o formulário — ele continua inteiro no endereço /cadastro, e o Google continua sendo avisado dele. O que acabou foi ele estar na primeira página.\n\nUm detalhe que vale saber: antes, a primeira página do site só abria se houvesse uma oferta cadastrada — se faltasse, ela respondia \"não encontrado\" para qualquer visitante. Agora ela não depende mais disso, porque não mostra oferta nenhuma. Uma porta a menos que pode fechar sozinha.\n\nO outro site (basileiatoutheou.org) não mudou em nada — continua com a página de venda de sempre, conferida letra por letra pelo teste que existe justamente para isso.\n\nConferido de fora, no ar: meshcraft.top responde 200 nos três idiomas, cada um com o texto certo (\"Entrar no Meshcraft\", \"Sign in to Meshcraft\", \"Entrar en Meshcraft\"). O que NÃO consegui conferir de fora é a tela de quem já entrou — para isso eu precisaria da sua conta. Ela está provada por 314 testes automáticos, e você pode confirmar em dois cliques: entre no site e veja se aparece o aviso e o botão da Caixa.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/308",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "site",
  vence_em_dias: null
});})();
// ---- 20260827-024-o-aviso-de-novidade-fica-como-texto ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-024-o-aviso-de-novidade-fica-como-texto",
  tipo: "decisao",
  quando: "2026-08-27",
  titulo: "Você decidiu: o \"Em breve teremos muitas novidades\" fica como aviso, não como link",
  detalhe: "Ao entregar a home nova eu te perguntei se aquela frase devia ser clicável. Você respondeu que não: ela é só um aviso. O único botão clicável da tela de quem entrou continua sendo o da Caixa de Sugestões.\n\nO motivo, guardado aqui para ninguém reabrir isso por engano: hoje não existe nenhuma página de novidades para onde esse link levaria. Link que não leva a lugar nenhum frustra quem clica.\n\nO que destranca a conversa de novo: no dia em que existir uma página de novidades/avisos do site, essa frase é a candidata natural a virar o caminho até ela.",
  autoridade: "mantenedor",
  evidencia: null,
  verificado_em: null,
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "site",
  vence_em_dias: null
});})();
// ---- 20260827-025-a-tela-de-avisos-da-caixa-agora-le-da-caixa-central ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-025-a-tela-de-avisos-da-caixa-agora-le-da-caixa-central",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "A própria tela de avisos da Caixa agora lê da caixa central — as duas metades do sininho estão prontas",
  detalhe: "Fecha o Lote C do plano de fechamento do sininho: a última das duas telas que precisavam trocar de fonte. A tela de avisos da Caixa (e o número pequeno que aparece no topo de toda página DENTRO da Caixa) passaram a consultar a caixa central de avisos, em vez da tabela própria — a mesma peça que o sino do site inteiro (registro 016) já usa.\n\nTudo que a tela já fazia continua funcionando: marcar um aviso como lido, ver o motivo de cada aviso (sua ideia / você comentou / você votou), o texto exato de cada mudança de status. De brinde, ganhou um botão novo — marcar todos os avisos como lidos de uma vez —, que você já tinha decidido que devia entrar (a conversa desta manhã).\n\nA gravação continua acontecendo nos dois lugares por enquanto (a tabela antiga da Caixa e a caixa central) — é uma rede de segurança durante a transição, não desperdício: se algo der errado com a leitura nova, dá para voltar atrás sem perder nada. Aposentar de vez a tabela antiga é o último passo do plano, ainda por vir.\n\nSe a caixa central cair num instante, o número pequeno no topo da página simplesmente some (a página continua normal); já a tela de avisos completa avisa com uma frase clara, porque essa tela existe justamente para mostrar avisos — sumir em silêncio ali seria enganoso.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/311 — MERGED; deploy-celula 33106392491 success (o run anterior, 33106261022, foi cancelado por um merge de outra sessão chegando junto — comportamento normal do GitHub, não falha); medido de fora depois: meshcraft.top e /forms/sugestoes/healthz em 200; 419 testes na célula",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: "20260827-007-rumo-comunidade-a-porta-de-avisos-ganha-corpo",
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260827-026-a-barra-no-final-parou-de-dar-erro-no-site-inteiro ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-026-a-barra-no-final-parou-de-dar-erro-no-site-inteiro",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "Endereço com barra no final parou de dar erro no site INTEIRO (as 4 peças)",
  detalhe: "Aquele problema que você tropeçou hoje — o mesmo endereço funcionar sem a barra no final e dar \"página não encontrada\" com ela — estava consertado só na Caixa. Agora está nas quatro peças do site: as páginas públicas, a entrada, o quiz e a Caixa.\n\nA que mais importava era a ENTRADA. O endereço de entrar com o Google dava \"não encontrado\" se tivesse uma barra a mais: a pessoa não conseguia nem tentar entrar na plataforma. Isso está resolvido.\n\nConferido ao vivo, no site de verdade, depois do deploy: as páginas de cadastro e login, a entrada do Google, e o endereço em espanhol (que preserva o idioma — quem estava no /es continua no /es, não é jogado para outra língua).\n\nO cuidado que isso exigiu, porque mexer em endereço é fácil de fazer errado: a regra só age quando o endereço COM barra não existe E o sem barra existe. Ou seja, ela é incapaz de mudar o destino de qualquer endereço que já funcionava. No quiz isso foi crítico — lá a página principal é canônica COM barra, e uma regra descuidada teria posto o site em laço infinito, recarregando para sempre. Tem teste medindo exatamente esse laço.\n\nE em todas as quatro: formulário enviado (POST) nunca é redirecionado. Um redirecionamento nesse caso apaga o que a pessoa preencheu em silêncio — perderia leads no funil, respostas no quiz, e no caso da entrada faria alguém \"sair\" sem sair de verdade.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/315",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "site",
  vence_em_dias: null
});})();
// ---- 20260827-027-falta-uma-linha-sua-para-o-sino-acender ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-027-falta-uma-linha-sua-para-o-sino-acender",
  tipo: "pendencia",
  quando: "2026-08-27",
  titulo: "O sino e a tela de avisos da Caixa estão prontos — falta uma linha sua na VPS para eles acenderem de verdade",
  detalhe: "O QUE EU PRECISO DE VOCÊ: uma linha de comando, dentro da VPS, sem precisar digitar nem colar senha nenhuma — o script gera as duas sozinho.\n\nPOR QUE NÃO POSSO FAZER SOZINHO: é configuração que vive só na VPS, e o agente não tem acesso a ela (Lei 5 do projeto). É o mesmo tipo de passo que você já fez outras vezes esta semana.\n\nO QUE ACONTECE SE VOCÊ AINDA NÃO RODAR: nada quebra. O sino continua invisível ao lado do seu nome, e a tela de avisos da Caixa continua avisando 'não consegui buscar seus avisos agora' — os dois comportamentos são de propósito, não erro.\n\nO BLOCO PARA COLAR — DENTRO DA VPS (o prompt do terminal começa com deploy@srv... ou root@srv..., nunca com PS C:\\>):\n\ncurl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-porta-de-avisos.sh -o /tmp/p.sh && bash /tmp/p.sh\n\nNão pede nenhum dado seu — sem senha para colar, sem e-mail, sem nada para digitar. Silêncio durante a execução é normal; ao final ele mostra 'PRONTO'. Pode rodar mais de uma vez sem medo — rodar de novo não desconfigura nada.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/318 — MERGED; infra/provisionar-porta-de-avisos.sh testado por encenação (rodadas repetidas, par divergido reconciliado, diretório errado recusado, recarregamento medido com docker falso) antes de propor",
  verificado_em: "2026-08-27",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260827-028-o-guia-do-funil-ganhou-duas-pecas-que-faltavam ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-028-o-guia-do-funil-ganhou-duas-pecas-que-faltavam",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "O documento-guia do funil (a vitrine) foi corrigido: faltavam dois serviços que ele já usa",
  detalhe: "Cada parte do site tem um documento interno — a 'constituição' dela — que explica para qualquer robô que for mexer ali com quem aquela parte conversa e com que crachá (senha de acesso). A do funil (a vitrine pública: páginas de venda, formulários) dizia que ele só conversava com duas peças — o catálogo de ofertas e o cadastro de interessados. Só que o código já conversa com mais duas: a identidade (para saber se quem está navegando já entrou no site) e a caixa central de avisos (o sininho ao lado do nome). O documento não tinha sido atualizado quando essas duas conexões entraram.\n\nO conserto foi só de texto: reli o arquivo de código que faz essas quatro conversas para confirmar nome de cada operação e de cada crachá antes de escrever, e atualizei o documento para bater com o que já existe. Nada no site mudou — nenhum código, nenhum teste, zero risco para quem visita.\n\nPOR QUE ISSO IMPORTA PARA VOCÊ: um documento-guia desatualizado é a receita para um robô futuro tomar uma decisão errada por achar que uma conexão não existe. Agora ele conta a verdade inteira.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/321 — MERGED (commit 568e1d6), só documentação, 1 arquivo",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260827-029-a-trava-de-numero-repetido-ja-existia ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-029-a-trava-de-numero-repetido-ja-existia",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "A trava contra número repetido no livro já existia — só faltava estar escrita onde dá para achar",
  detalhe: "Uma sessão, trabalhando em outra tarefa, viu três colisões seguidas de número de registro em poucos minutos (duas sessões diferentes escolhendo o mesmo número do dia, ao mesmo tempo) e sugeriu investigar se existia alguma trava automática contra isso — ou se precisava construir uma.\n\nInvestiguei antes de construir qualquer coisa nova, e a trava JÁ EXISTIA, completa: nasceu em 26/08/2026 (registro 20260826-041), depois de exatamente essa mesma corrida ter acontecido quatro vezes num único dia. Ela mora em painel/logica.js, tem quatro testes próprios dedicados só a ela, e roda automaticamente em TODO PR — quem tentar gravar dois registros com o mesmo número no mesmo dia recebe uma recusa que já diz para qual número renomear. Nada precisou ser construído.\n\nO que estava faltando era mais simples: essa trava não estava mencionada no documento que qualquer sessão lê antes de registrar algo (painel/LEIA-ME.md) — só um comentário dentro do código, que uma sessão apressada não vai ler. Por isso a sessão anterior não sabia que a rede de segurança já existia, e descobriu a corrida do jeito manual (olhando a pasta com os próprios olhos) em vez de deixar o sistema avisar sozinho.\n\nO CONSERTO foi só documentação: acrescentei ao LEIA-ME.md a explicação de que essa trava existe, desde quando, e o que fazer se ela disparar. Não criei trava nova, teste novo nem lógica nova — teria sido uma cópia do que já funciona, e este livro tem uma regra dura contra um mesmo fato morar em dois lugares.\n\nA PROVA veio sozinha, sem eu precisar montar cenário nenhum: enquanto este próprio registro estava sendo escrito, outras DUAS sessões pegaram o mesmo número que eu, uma atrás da outra — primeiro o '027', depois, já eu tendo trocado, o '028' de novo. As duas vezes, ao atualizar meu trabalho com o que tinha chegado de novo (o passo de rotina que toda sessão faz), a trava recusou gravar e me mandou trocar de número, até sobrar o '029' — o número deste registro. Ou seja: no meio do trabalho de dizer 'essa trava existe', ela pegou DUAS colisões de verdade, ao vivo, na frente dos meus olhos.\n\nNADA disto pede a sua atenção: é ajuste de um documento interno para robôs, os 68 testes do painel continuam todos verdes, e nenhuma tela ou comportamento do site mudou.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/320",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260827-030-uma-virgula-num-contrato-criava-uma-regra-fantasma ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-030-uma-virgula-num-contrato-criava-uma-regra-fantasma",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "Uma vírgula sem aspas fazia um contrato do sistema descrever uma regra que não existe",
  detalhe: "Este registro paga uma dívida do livro: um trabalho entrou na plataforma hoje e ninguém tinha te contado. Achei ao conferir a porta do merge, que se recusou a mergear enquanto isso não fosse contado — a trava funcionou.\n\nO QUE ERA: os “contratos” são os acordos escritos entre as partes do sistema — o documento que diz o que uma parte promete responder à outra. Num deles, uma frase de descrição estava sem aspas, e uma vírgula no meio da frase fez o computador ler metade da frase como se fosse uma REGRA NOVA, inventada. O arquivo continuava válido aos olhos de qualquer verificador; o acordo é que tinha virado bobagem.\n\nPOR QUE IMPORTA: quem fosse programar a parte que obedece a esse acordo só conseguiria ficar verde reproduzindo a bobagem — publicando a regra fantasma para todo mundo que dependesse dela. A alternativa era ficar vermelho para sempre. O conserto foi uma linha: as aspas de volta.\n\nA LIÇÃO ficou guardada como armadilha do projeto (vírgula dentro de chaves, em YAML, separa entradas — texto sem aspas vira chave nova), para o próximo robô não repetir.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/302 — MERGED em 27/08/2026 18:06 UTC; muda uma linha de contracts/alunos.openapi.yaml (aspas na descrição do 422). Registro escrito depois, ao pagar a dívida do livro que a porta do merge cobrou.",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260827-031-o-painel-quebrava-por-excesso-de-pedidos ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-031-o-painel-quebrava-por-excesso-de-pedidos",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "Achei por que o painel quebrava 4 vezes por dia — o livro estava intacto; quem falhava era a entrega",
  detalhe: "Você colou o aviso vermelho pela QUARTA vez hoje, e desta vez com a informação que faltava: era o SITE, não o arquivo do seu PC. Isso mudou onde eu procurei — e o defeito apareceu.\n\nO LIVRO NUNCA ESTEVE QUEBRADO. Rodei os 87 registros juntos, do jeito que o navegador os executa: 87 de 87, zero erro. O validador também vinha limpo todas as vezes. Por isso a sessão de manhã não achou nada — ela auditou os arquivos, que era exatamente o lugar onde não havia defeito. O problema estava na ENTREGA: no caminho entre o servidor e a sua tela.\n\nO QUE ACONTECIA, em português simples: o painel era montado pedindo ao servidor UM ARQUIVO PARA CADA REGISTRO. Com 86 registros, abrir a página disparava 86 pedidos de uma vez. E a área administrativa confere o seu crachá em CADA pedido — o que significa perguntar a outro programa do servidor quem é você, com 2 segundos de paciência. Quando 86 perguntas chegam juntas, ele não responde todas a tempo; as que estouram recebem “serviço indisponível” no lugar do registro. Esses registros sumiam, e a trava do painel gritava — corretamente, porque painel pela metade é pior do que painel que se recusa a abrir.\n\nISSO EXPLICA AS TRÊS COISAS QUE NÃO FAZIAM SENTIDO. O número mudava a cada vez (2, depois 29) porque depende de quantas perguntas o servidor conseguiu responder naquele segundo. Piorava com o tempo porque o número de pedidos ERA o tamanho do livro — cada tarefa registrada aumentava a chance de quebrar no dia seguinte. E no seu PC funcionava, porque ali não existe porta nem crachá.\n\nO CONSERTO: o livro inteiro passou a viajar num arquivo só. UM pedido no lugar de 86. Não existe mais “carregou pela metade” — ou o livro chega inteiro, ou a falta aparece na tela. E o custo de abrir o painel parou de crescer com o tamanho do livro: registrar mais nunca mais vai deixar o painel mais frágil.\n\nA TRAVA PARA NÃO VOLTAR: um teste que abre a página de fora e reprova se ela voltar a pedir registro por registro. Ele fica VERMELHO no código antigo e VERDE neste — não é promessa, é medida.\n\nO QUE EU AINDA NÃO PUDE PROVAR: não consegui abrir o painel num navegador de verdade nesta sessão (a ponte do Chrome está fora do ar de novo). Todo o resto está medido, mas quem confirma que a sua tela voltou é você — reabra meshcraft.top/admin/painel/ e me diga. Se algum dia voltar a quebrar, o texto do aviso agora pede que você diga se foi o site ou o seu PC: foi essa informação que resolveu hoje.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/323 — o teste de fora test_o_livro_chega_em_UM_pedido_e_nao_um_por_registro fica VERMELHO no código antigo (assert 'livro.js' in ['manifesto.js', 'logica.js']) e VERDE neste; 13/13 em tests/test_painel_vivo.py; muralha do painel verde; os 87 registros executados juntos num contexto compartilhado dão 87/87. Falta a confirmação do mantenedor abrindo a página.",
  verificado_em: "2026-08-27",
  precisa_do_dono: true,
  responde_a: "20260827-002-o-aviso-de-painel-quebrado-nao-se-repete-agora",
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260827-032-o-sininho-esta-no-ar-de-ponta-a-ponta-confirmado-por-voce ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-032-o-sininho-esta-no-ar-de-ponta-a-ponta-confirmado-por-voce",
  tipo: "resposta",
  quando: "2026-08-27",
  titulo: "Você rodou o comando na VPS e confirmou com os próprios olhos: o sininho está funcionando em todo o site",
  detalhe: "Fecha o pedido do registro 027. Você rodou o comando, e depois conferimos juntos, com prints de tela: o sino ao lado do seu nome aparece em qualquer página do site ('Olá, Arameu 🔔 Sair'), e a tela de avisos da Caixa responde de verdade ('Nada de novo por aqui — todos os seus avisos já foram lidos', em vez de um erro). Sem número visível porque você não tem avisos pendentes agora — é o comportamento certo, não falta de dado.\n\nCom isso, o pedido original do dia em que você pediu o sistema de avisos — 'um sininho na tela ao lado do nome, algo como as notificações do Facebook' — está no ar, de ponta a ponta, medido por você mesmo em produção.\n\nO QUE FICA PARA A PRÓXIMA RODADA, quando fizer sentido: silenciar um assunto (só há um assunto hoje, então não muda nada ainda) e o envio por e-mail (decisão que você mesmo deixou de fora por enquanto).",
  autoridade: "mantenedor",
  evidencia: "Confirmação visual sua, com print de tela, em duas telas: o sino na home ('Olá, Arameu 🔔 Sair') e a tela de avisos da Caixa ('Nada de novo por aqui'); PRs #274, #280, #282, #288, #293, #294, #296, #301, #311, #318 — a cadeia inteira da Fase 4/5/6 do sininho, todos MERGED",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: "20260827-027-falta-uma-linha-sua-para-o-sino-acender",
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260827-033-o-dono-confirmou-o-painel-abriu-normal ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-033-o-dono-confirmou-o-painel-abriu-normal",
  tipo: "resposta",
  quando: "2026-08-27",
  titulo: "Confirmado por você: o painel abriu normal depois do conserto",
  detalhe: "Você abriu meshcraft.top/admin/painel/ e ele apareceu normal, sem a tela vermelha. Isso fecha o caso que estava aberto desde hoje de manhã.\n\nO QUE ESTAVA ERRADO, em uma frase: o painel pedia ao servidor um arquivo para cada registro, e a rajada de 86 pedidos batia na porta da área administrativa até parte deles voltar como erro — o livro chegava pela metade e a trava, corretamente, se recusava a mostrar qualquer coisa. Agora o livro inteiro vem num arquivo só: um pedido no lugar de 86.\n\nPOR QUE ISSO IMPORTA DAQUI PARA A FRENTE: o defeito crescia junto com o projeto — cada tarefa registrada aumentava a chance de o painel quebrar no dia seguinte. Isso acabou. O custo de abrir o painel não depende mais do tamanho do livro, e existe um teste que reprova qualquer robô que tente voltar ao jeito antigo, sem depender de ninguém lembrar.\n\nO DIAGNÓSTICO SÓ SAIU PORQUE VOCÊ DISSE QUE ERA O SITE. Enquanto a informação era só “o painel quebrou”, a busca ia para os arquivos — que estavam intactos o tempo todo. O texto do aviso vermelho foi mudado para pedir isso explicitamente na próxima vez.",
  autoridade: "mantenedor",
  evidencia: "Confirmação do mantenedor em 27/08/2026, abrindo meshcraft.top/admin/painel/ depois do deploy: \"Abriu normal\". Conserto no PR https://github.com/abundanciabr/sitesdoreino/pull/323 (MERGED), deploy run 33110413071 completed/success, imagem com 91 registros embutidos, container plataforma-admin-1 healthy.",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: "20260827-031-o-painel-quebrava-por-excesso-de-pedidos",
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260827-034-auditoria-de-fechamento-o-mapa-do-sininho-esta-em-dia ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-034-auditoria-de-fechamento-o-mapa-do-sininho-esta-em-dia",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "Auditoria de fechamento do sininho — o documento agora bate com o que está de verdade no ar",
  detalhe: "Depois de confirmado que o sino funciona, fui conferir se o documento que guia o plano (o 'mapa-mestre' das notificações) ainda descreve a realidade. Achei um ponto onde ele mentia por desatualização, não por erro: listava como 'falta fazer' avisar quem votou numa ideia (não só quem criou) — mas isso já tinha sido resolvido três dias atrás, de graça, como efeito colateral de outra decisão sua (a de 26/08, 'uma carta por pessoa'). Ninguém tinha voltado para atualizar o documento.\n\nCorrigido: o documento agora mostra as sete etapas do plano e o estado real de cada uma. Só uma coisa genuinamente continua em aberto — aposentar de vez a forma antiga de guardar os avisos dentro da Caixa (hoje ela guarda dos dois jeitos, como rede de segurança) — e isso ficou marcado com clareza, em vez de escondido dentro de outro item.\n\nDe brinde, registrei uma lição técnica no lugar certo para a próxima vez: quando uma peça nova ganha uma porta de consulta pela primeira vez, não basta desenhar a porta — é preciso também avisar o sistema de vigilância do projeto que aquela porta existe, no MESMO pacote de mudança, senão o robô de qualidade recusa por inconsistência.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/326 — MERGED; docs/notificacoes/PLANO-MESTRE.md e contracts/README.md; achado confirmado lendo services/sugestoes/apps/core/moderacao.py",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260827-035-a-divida-dos-avisos-antigos-foi-paga ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-035-a-divida-dos-avisos-antigos-foi-paga",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "Achei e paguei uma dívida que ficaria escondida: avisos que você já tinha lido apareceriam de novo como 'novos'",
  detalhe: "Na auditoria de fechamento, achei um alerta que uma sessão anterior tinha deixado escrito para quem construísse o sino: quando os avisos antigos da Caixa foram copiados para a caixa central (26/08), eles chegaram lá marcados como 'não lidos' — porque naquela hora ainda não existia nenhuma tela lendo de lá. O alerta dizia, com todas as letras: antes de ligar o sino de vez, alguém precisa marcar esses avisos antigos como já lidos, senão todo mundo veria de novo, como novidade, coisa que já tinha lido há dias.\n\nEsse aviso não tinha sido atendido — nem o despacho que construiu o sino nem o que migrou a tela da Caixa cuidaram disso, porque nenhum dos dois estava olhando para aquele alerta específico. Corrigido agora: uma correção que roda sozinha assim que o servidor sobe (sem precisar de nada seu), identifica com certeza matemática quais avisos vieram daquela cópia antiga (usando a mesma fórmula que os criou, sem precisar espiar o banco de outra peça do sistema) e marca como lidos só esses — nunca um aviso genuinamente novo.\n\nTestei a correção de um jeito que prova que ela funciona de verdade: quebrei a fórmula de propósito e confirmei que o teste acusou a quebra (um aviso novo teria sido marcado como lido por engano) — só depois de ver o alarme disparar é que confio que ele protege alguma coisa.\n\nNão tenho como saber, daqui, quantos avisos foram corrigidos na prática (não tenho acesso ao banco de produção) — mas o site continuou respondendo normalmente durante e depois, o que confirma que a correção rodou sem quebrar nada.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/328 — MERGED, commit 1cce16a889a4; deploy-celula 33113006132 success; medido de fora depois: meshcraft.top e /forms/sugestoes/healthz em 200; teste de mutação provado (fórmula sabotada de propósito, teste acusou, revertido)",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null
});})();
// ---- 20260827-036-o-servidor-abre-uma-linha-nova-a-cada-visita ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-036-o-servidor-abre-uma-linha-nova-a-cada-visita",
  tipo: "pendencia",
  quando: "2026-08-27",
  titulo: "Achei a causa de fundo das 4 telas vermelhas — e ela nao e do painel, e do servidor inteiro",
  detalhe: "A auditoria das 5 consultorias me obrigou a ir ler o codigo de verdade, e apareceu uma coisa que nenhuma das cinco tinha previsto. Ela nao muda nada hoje, mas voce precisa saber que existe.\n\nEM PORTUGUES SIMPLES: cada vez que alguem abre uma pagina, o servidor abre uma LINHA TELEFONICA nova com o banco de dados — e nao desliga. Ela fica ocupada por mais um minuto e depois e abandonada em aberto. So existem 100 linhas no total, divididas entre as 11 partes do sistema (o site, o login, a caixa de sugestoes, a area administrativa, e por ai vai).\n\nO PAINEL FOI SO O PRIMEIRO A ESTOURAR ESSE LIMITE. Ele pedia 86 arquivos de uma vez, cada pedido virava uma pergunta ao login, cada pergunta abria uma linha. As que nao acharam linha livre voltaram como erro — e a tela vermelha apareceu. O conserto de hoje (um pedido no lugar de 86) tirou o painel da frente do problema, mas NAO consertou o problema: qualquer pagina movimentada faz a mesma coisa. Uma aula com 30 audios, por exemplo. So que ai serao alunos de verdade vendo o erro, e nao um painel de uma pessoa so.\n\nPOR QUE EU NAO CONSERTEI AGORA: voce decidiu, hoje, que esta obra e so do painel — e eu concordo com a ordem. Mexer nisso e cirurgia no portao de entrada de todas as celulas, e merece uma conversa propria, com medida antes e depois. Este registro existe para o assunto nao sumir.\n\nO QUE EU AINDA NAO SEI, E QUE MUDA O TAMANHO DO CONSERTO: eu nunca vi o log do servidor no dia do incidente — nao tenho acesso a maquina (Lei 5), e ninguem guardou. Entao isto continua sendo deducao lida no codigo, nao prova. O primeiro passo do plano aprovado hoje inclui uma pagina que faz o proprio servidor contar o que acontece com ele. Depois dela, isto para de ser palpite.\n\nO QUE PRECISO DE VOCE: nada agora. Quando o painel novo estiver de pe e a pagina de medicao existir, eu volto com os numeros reais e uma pergunta de multipla escolha sobre o que fazer. Se antes disso alguma pagina do site der erro estranho sob movimento, e provavelmente isto.",
  autoridade: "sessao",
  evidencia: "Leitura do codigo de producao em 27/08/2026, nas versoes exatas instaladas (Django 5.1.4, asgiref 3.12.1): services/admin/Dockerfile linha 11 e services/identidade/Dockerfile linha 11 sobem uvicorn SEM --workers (1 processo); django/core/handlers/asgi.py linha 161 abre um ThreadSensitiveContext POR REQUISICAO e asgiref/sync.py linha 476 cria um ThreadPoolExecutor(max_workers=1) para cada um (thread nova por requisicao, sem teto); django/db/utils.py linha 145 marca thread_critical=True e o proprio comentario do Django admite \"There's no cleanup after async contexts\" (conexao de banco e por thread e nao e fechada); services/identidade/config/settings.py linha 45 usa conn_max_age=60 (nao fecha ao fim da requisicao); infra/docker-compose.yml sobe postgres:17 sem arquivo de configuracao e sem command, portanto com max_connections=100 default, para 11 celulas — conferido com 'git grep max_connections' em infra/ e services/, que nao devolve nada.",
  verificado_em: "2026-08-27",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null
});})();
// ---- 20260827-037-o-painel-vai-ser-refeito-e-voce-decidiu-como ----
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-037-o-painel-vai-ser-refeito-e-voce-decidiu-como",
  tipo: "decisao",
  quando: "2026-08-27",
  titulo: "Voce mandou refazer o painel, e escolheu as tres coisas que decidem o desenho",
  detalhe: "Voce juntou 15 documentos de analise — cinco robos diferentes, cada um respondendo tres perguntas, dando um parecer individual e depois um parecer como se fosse uma equipe senior — e mandou analisar tudo antes de qualquer plano. Analisei os 15, e conferi no codigo real cada afirmacao que eles fizeram sobre nos.\n\nO QUE OS CINCO DISSERAM JUNTOS: o conserto de hoje curou o sintoma e deixou a doenca. O painel continua custando, para abrir, proporcionalmente a TODA a historia do projeto — hoje sao 95 registros, e num unico dia foram escritos 48. E a trava que protege o painel virou parcialmente circular: quem confere e o mesmo programa que escreve.\n\nO QUE A CONFERENCIA DESMENTIU: quatro suspeitas fortes deles caem quando se le o codigo. Nao e conexao nova a cada chamada (ja foi consertado antes), nao e banco lento (e Postgres, e a consulta e uma so), nao existe porteiro no Traefik derrubando pedido, e nao existe risco de o painel misturar versoes — ele e assado dentro da imagem, inteiro, de uma vez. Registrar isso importa: sao quatro caminhos que ninguem precisa mais investigar.\n\nAS TRES ESCOLHAS QUE VOCE FEZ, E O QUE CADA UMA MUDA:\n\n1. SO O PAINEL AGORA. O defeito de fundo do servidor (registro 036) fica registrado e espera. Voce depois abriu uma excecao nomeada: pode construir a pagina que faz o servidor contar o que acontece com ele, porque sem ela o assunto nunca sai de deducao.\n\n2. RESUMO PRONTO, HISTORICO SO QUANDO PEDIR. O painel passa a abrir com a capa ja calculada e nada mais; o historico antigo so carrega se voce clicar. Isso faz o custo de abrir parar de crescer para sempre — e foi o que permitiu ir alem do que eu tinha planejado: abrir o painel vai passar a ser UM pedido, nao tres.\n\n3. OS DOIS JEITOS CONTINUAM. Duplo clique no arquivo do seu PC e pelo site. Isso descartou tres recomendacoes fortes (tirar os arquivos do Git, usar banco de dados, gerar tudo so no servidor) — todas quebrariam o duplo clique.\n\nUMA COISA QUE UM DELES RECOMENDOU E QUE EU RECUSEI EM SEU NOME: um dos pareceres disse para congelar o painel e priorizar o caminho de venda. Nao da: a frente de vender esta pausada por ordem sua desde 22/08, e o proprio painel diz isso na tela. A recomendacao supunha um trabalho alternativo que nao existe.\n\nADIADO POR VOCE: organizar a pasta de registros em subpastas por mes. E ergonomia dos robos, nao da sua tela — 95 arquivos hoje, cerca de 18 mil num ano no ritmo atual. Fica esperando incomodar.",
  autoridade: "mantenedor",
  evidencia: "Analise dos 15 documentos em docs/paineis/melhorias-e-otimizacoes/ (5 de perguntas, 5 de recomendacao, 5 de equipe) cruzada com o codigo em origin/main eaae6d7, em 27/08/2026. Decisoes tomadas pelo mantenedor por pergunta estruturada na mesma sessao. Plano aprovado por ele antes de qualquer linha de codigo.",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null
});})();
