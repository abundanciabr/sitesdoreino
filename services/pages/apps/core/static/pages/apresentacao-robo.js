(() => {
  "use strict";
  const form = document.getElementById("apresentacao");
  if (!form) return;
  const $ = (selector, root = document) => root.querySelector(selector);
  const initialNode = $("#conteudo-inicial");
  let saved = {};
  try { saved = JSON.parse(initialNode?.textContent || "{}") || {}; } catch (_) { saved = {}; }
  const pageFields = [
    ["titulo", "Título", "Abertura", "text", 200],
    ["subtitulo", "Subtítulo", "Abertura", "textarea"],
    ["apresentacao", "Quem sou e o que faço", "Apresentação", "textarea", 3000],
    ["oferta", "O que posso entregar", "Oferta", "textarea", 3000],
    ["diferenciais", "Diferenciais, um por linha", "Diferenciais", "textarea"],
    ["condicoes", "Condições, uma por linha", "Condições", "textarea"],
    ["continuidade", "Como seguimos depois", "Continuidade", "textarea"],
    ["duvidas", "Dúvidas frequentes, uma por linha", "Dúvidas", "textarea"],
    ["cta", "Convite para contato", "Convite para contato", "text"]
  ];
  const kitFields = [
    ["apresentacao_principal", "Bio longa", "Apresentação principal", "textarea"],
    ["bio_curta", "Bio curta", "Bio curta", "textarea", 280],
    ["abordagem", "Mensagem para o destinatário", "Primeira abordagem", "textarea"],
    ["proposta", "Texto da proposta", "Proposta", "textarea"]
  ];
  const positionFields = [["comprador", "Comprador"], ["necessidade", "Necessidade"], ["oferta", "Oferta prioritária"], ["prova", "O que demonstra meu trabalho"]];
  const fieldGuides = {
    pagina_titulo: {
      description: "É a primeira frase que o visitante lê. Apresente o tipo de criação que ele pode encomendar e ajude-o a imaginar essa peça no projeto dele.",
      steps: ["Comece pelo serviço ou pela peça que você quer destacar, como acessórios, espadas ou objetos de cenário.", "Acrescente um estilo ou uso que faça sentido para seu comprador. Prefira uma frase curta e específica, apoiada no que seus trabalhos mostram."],
      examples: ["Espadas de fantasia para dar forma à aventura do seu jogo.", "Acessórios florais para sua próxima coleção de avatares.", "Objetos coloridos para compor sua vila no Roblox."],
      unknown: "Use uma frase simples como ‘Modelagem de objetos de cenário para Roblox’. Você pode pedir ao robô uma nova abertura e ajustar depois."
    },
    pagina_subtitulo: {
      description: "É a frase que acompanha o título. Ela explica com mais clareza o serviço, para quem ele serve e o que você cria.",
      steps: ["Leia o título e identifique qual informação ainda falta para o comprador entender a oferta.", "Complete com a peça, o estilo ou a entrega. Evite repetir o título inteiro ou acrescentar arquivos e serviços que você não oferece."],
      examples: ["Modelo espadas estilizadas com texturas para equipes que desenvolvem jogos de aventura.", "Crio chapéus e outros acessórios com tema floral para coleções de avatares.", "Transformo suas referências em objetos 3D para a decoração do seu cenário."],
      unknown: "Responda em uma frase: ‘O que eu crio e para quem?’. Os detalhes de prazo e preço podem ficar nas condições."
    },
    pagina_apresentacao: {
      description: "É sua apresentação ao possível cliente. Escreva em primeira pessoa e conecte o que você faz aos trabalhos que ele pode ver na página.",
      steps: ["Diga qual criação você oferece e que tipo de projeto gosta de atender.", "Aponte uma peça sua que demonstre esse trabalho. Se foi um estudo autoral ou uma colaboração, explique sua participação de forma simples."],
      examples: ["Crio objetos estilizados para cenários Roblox. A lanterna que apresento abaixo mostra as formas e as cores que desenvolvi para uma vila de fantasia.", "Modelo acessórios para avatares. Meu chapéu floral é um projeto autoral que mostra o tipo de composição que posso criar para uma coleção."],
      unknown: "Você pode se apresentar pelo serviço e por um trabalho autoral, mesmo sem encomendas anteriores. Não precisa inventar clientes ou resultados."
    },
    pagina_oferta: {
      description: "É o texto que explica o que o visitante pode contratar. Reúna a criação oferecida e os materiais que fazem parte da entrega.",
      steps: ["Use as informações de ‘Minha oferta’ para descrever uma encomenda concreta: peça, quantidade e estilo.", "Diga o que o cliente recebe e o que precisa ser definido na conversa. Inclua importação, montagem ou publicação somente quando fizerem parte do seu serviço."],
      examples: ["Você pode encomendar uma espada estilizada. A entrega inclui o modelo 3D e suas texturas, com formatos e prazo definidos na proposta.", "Crio um chapéu floral a partir das suas referências. Combinamos a composição, os arquivos e os ajustes antes de começar."],
      unknown: "Comece por uma peça que você oferece. Quando algum detalhe depender do pedido, escreva que será combinado na proposta."
    },
    pagina_diferenciais: {
      description: "São motivos concretos para escolher seu trabalho. Explique uma característica que você consegue demonstrar e como ela ajuda o comprador.",
      steps: ["Observe suas peças e seu modo de trabalhar: formas, cores, organização da entrega ou etapas de conversa que você realmente oferece.", "Escreva um diferencial por linha, ligando a característica à utilidade para o cliente. Troque elogios gerais por algo que ele consiga entender e conferir."],
      examples: ["Cores e formas combinadas com suas referências para compor a direção visual do cenário.", "Prévia na etapa combinada para você comentar a aparência antes da entrega final.", "Arquivos identificados por peça para facilitar a organização do projeto."],
      unknown: "Escolha uma característica visível de um trabalho seu e descreva-a. Os exemplos de processo só devem ser usados se fizerem parte da sua oferta."
    },
    pagina_condicoes: {
      description: "É o resumo dos combinados que o visitante precisa conhecer para contratar: prazo, ajustes, pagamento e entrega, conforme você definiu na oferta.",
      steps: ["Confira os campos de prazo, revisões, suporte e condições comerciais em ‘Minha oferta’.", "Organize um combinado por linha. Use palavras simples e indique o que será definido após analisar o pedido, sem criar prazos ou benefícios novos."],
      examples: ["Prazo informado após receber as referências e definir a peça.", "Quantidade de revisões combinada na proposta.", "Formatos e etapas de pagamento definidos antes do início."],
      unknown: "Escreva ‘Prazo, arquivos e ajustes definidos na proposta antes do início’. Depois, acrescente as condições que você decidir oferecer."
    },
    pagina_continuidade: {
      description: "Mostra uma possibilidade de nova encomenda depois da primeira entrega. Ajuda o cliente a pensar em outras peças relacionadas ao projeto.",
      steps: ["Pense em uma continuação útil: outros acessórios da coleção, novas armas ou objetos para outra área do cenário.", "Apresente a ideia como um novo trabalho que pode ser combinado, com seu próprio escopo e orçamento."],
      examples: ["Depois da primeira espada, podemos conversar sobre outras armas no mesmo estilo.", "Podemos definir novos acessórios para ampliar a coleção floral.", "Uma próxima encomenda pode incluir objetos para outras áreas da vila."],
      unknown: "Pode deixar vazio se ainda não houver uma continuação que faça sentido para sua oferta."
    },
    pagina_duvidas: {
      description: "São perguntas e respostas que ajudam o visitante a entender a contratação. Escreva cada pergunta com sua resposta na mesma linha.",
      steps: ["Pense no que alguém perguntaria antes de encomendar: referências, arquivos, prazo ou ajustes.", "Responda com suas condições reais. Para separar as perguntas na página, coloque uma pergunta e sua resposta por linha."],
      examples: ["O que preciso enviar? Envie referências da peça e conte onde ela será usada.", "Qual é o prazo? Informo depois de analisar a complexidade do pedido.", "Quais arquivos recebo? Combinamos os formatos na proposta conforme o uso no projeto."],
      unknown: "Comece com a pergunta sobre como enviar um pedido. Você pode acrescentar outras depois das primeiras conversas com clientes."
    },
    pagina_cta: {
      description: "É o convite que aparece no botão de contato. Diga qual ação o interessado pode fazer para começar uma conversa com você.",
      steps: ["Escolha uma ação curta, como enviar referências ou conversar sobre a peça.", "Confira o ‘Link público de contato’ em ‘Minha oferta’: é esse endereço que o botão abre. O texto deste campo é o convite, sem precisar repetir o endereço."],
      examples: ["Envie as referências da sua peça", "Vamos conversar sobre seu projeto", "Peça um orçamento para sua criação"],
      unknown: "Use ‘Entrar em contato’ e escolha seu canal no campo de link público."
    },
    kit_apresentacao_principal: {
      description: "É uma apresentação mais completa para copiar e usar em uma conversa, perfil ou proposta. Ela deve fazer sentido mesmo fora da sua página.",
      steps: ["Escreva em primeira pessoa qual serviço oferece, quem atende e que tipo de peça cria.", "Acrescente um trabalho que demonstre seu estilo e um convite para conversar. Revise o texto para o destinatário e o idioma escolhidos."],
      examples: ["Modelo objetos estilizados para cenários Roblox. Minha lanterna de fantasia mostra as formas e cores que crio para esse tipo de ambiente. Se você precisa de uma peça para sua vila, podemos conversar a partir das referências.", "Crio acessórios florais para avatares. Você pode ver meu chapéu autoral no portfólio e me contar qual peça imagina para a próxima coleção."],
      unknown: "Use o serviço e um trabalho seu como ponto de partida. A apresentação pode ser útil sem listar experiências ou clientes que você ainda não tem."
    },
    kit_bio_curta: {
      description: "É uma descrição rápida para perfis e mensagens curtas. O campo permite até 280 caracteres; acompanhe o contador abaixo do texto.",
      steps: ["Resuma o tipo de criação que oferece e o público ou projeto que atende.", "Se houver espaço, acrescente uma característica do seu trabalho ou um convite para ver o portfólio. Corte repetições até ficar dentro do limite."],
      examples: ["Modelo objetos estilizados para cenários Roblox. Veja minhas peças e envie as referências do seu projeto.", "Crio acessórios florais para avatares Roblox. Portfólio e contato para encomendas na minha página.", "Modelagem de espadas de fantasia para jogos de aventura. Vamos conversar sobre sua próxima peça."],
      unknown: "Comece com ‘Modelagem 3D de [tipo de peça] para [tipo de projeto]’ e substitua os trechos pelas suas informações."
    },
    kit_abordagem: {
      description: "É a primeira mensagem para um possível cliente. Conecte uma necessidade dele ao seu serviço e ofereça um trabalho relevante para ele conhecer.",
      steps: ["Use o nome, o projeto e o contexto que você informou em ‘Para quem vou enviar o kit’. Cite apenas o que realmente sabe.", "Apresente seu serviço em poucas frases, indique uma peça sua e termine com uma pergunta simples. Depois de revisar, copie e envie pelo canal que você escolheu."],
      examples: ["Exemplo fictício: Olá, Ana! Vi seu anúncio procurando uma lanterna para a vila. Modelo objetos estilizados e posso mostrar uma lanterna autoral. Você já tem referências para essa peça?", "Olá! Crio acessórios florais para avatares. Posso mostrar meu chapéu autoral para você conhecer meu estilo. Sua equipe está planejando novas peças para a coleção?"],
      unknown: "Sem informações sobre um destinatário, apresente o serviço e pergunte quais peças ele procura. Você pode personalizar o texto quando conhecer o projeto."
    },
    kit_proposta: {
      description: "É o texto que organiza uma encomenda para o cliente conferir: o pedido entendido, a entrega, os combinados e o próximo passo para começar.",
      steps: ["Confira o pedido recebido e descreva a peça, a quantidade e os arquivos incluídos. Ajuste qualquer sugestão que não corresponda à conversa.", "Acrescente preço, moeda, prazo, revisões e condições já definidos. Identifique os pontos a combinar e termine pedindo a confirmação ou as informações que faltam."],
      examples: ["Modelo para adaptar: Pedido: [peça e quantidade]. Entrega: [modelo, texturas e formatos]. Prazo: [prazo combinado]. Valor: [valor e moeda]. Ajustes: [rodadas combinadas]. Próximo passo: confirmar as referências e o escopo.", "Para a lanterna que você descreveu, proponho criar o modelo 3D e suas texturas. Confirmamos dimensões, formatos e referências para definir o prazo e o orçamento antes de começar."],
      unknown: "Sem pedido recebido, use o texto como rascunho. Complete os pontos em aberto com o cliente antes de apresentá-lo como uma proposta fechada."
    },
    orientacao: {
      description: "É um pedido curto para orientar a escrita do robô. Você pode indicar o foco, o tom ou algo que deseja destacar, usando até 400 caracteres.",
      steps: ["Diga qual aspecto dos seus dados ou trabalhos merece destaque: estilo, tipo de peça ou público.", "Acrescente uma preferência de escrita, como frases curtas ou tom direto. Ao gerar uma seção, a orientação ajuda a reescrever aquela parte; confira a sugestão antes de salvar."],
      examples: ["Destaque meus objetos coloridos para cenários de aventura. Use frases curtas.", "Dê foco aos acessórios florais e ao chapéu autoral que selecionei.", "Escreva uma abordagem direta para o pedido de lanterna informado no kit."],
      unknown: "Pode deixar vazio. O robô usa o quiz, a oferta e os trabalhos informados para criar as sugestões.",
      hint: "Ex.: Destaque meus objetos coloridos e use frases curtas"
    },
    pagina_trabalho_destaque: {
      description: "É a imagem que abre sua apresentação. Escolha um trabalho seu que mostre claramente o serviço que deseja vender.",
      steps: ["Compare as peças com sua oferta principal e escolha a que mais ajuda o cliente a visualizar uma encomenda parecida.", "Ao escolher uma peça aqui, ela também é marcada na seleção de trabalhos. Confira o destaque na prévia; você pode manter a escolha automática entre os trabalhos selecionados."],
      examples: ["Oferta de espadas: destacar a imagem da sua espada de fantasia.", "Oferta de acessórios florais: destacar o chapéu da coleção.", "Oferta de objetos de cenário: destacar uma peça com formas e cores bem visíveis."],
      unknown: "Mantenha ‘Escolher automaticamente’. Se ainda não houver peças, adicione imagens em ‘Meus trabalhos’."
    },
    trabalho_selecao: {
      label: "Selecionar este trabalho",
      description: "Marque a peça que deseja incluir na apresentação. Os trabalhos escolhidos também ajudam o robô a relacionar os textos às suas criações.",
      steps: ["Escolha peças relacionadas ao serviço e ao comprador que você quer destacar. Um estudo autoral também pode demonstrar seu trabalho.", "Confira o título e a legenda de cada peça marcada. Salve a seleção; se sua página já estiver publicada, os trabalhos selecionados aparecem nela."],
      examples: ["Selecionar uma espada para apresentar modelagem de armas de fantasia.", "Selecionar um chapéu para mostrar a composição de um acessório floral.", "Selecionar uma lanterna para uma oferta de objetos de cenário."],
      unknown: "Comece pelo trabalho mais próximo da sua oferta. Você pode ajustar a seleção enquanto observa a prévia."
    },
    trabalho_titulo: {
      description: "É o nome da peça que o visitante verá na página. Ajude-o a identificar a criação sem depender do nome do arquivo.",
      steps: ["Diga que peça é essa: espada, chapéu, lanterna ou outro objeto.", "Acrescente o tema ou uma característica que diferencia a peça. Use um título curto que corresponda à imagem."],
      examples: ["Espada de cristal para aventura", "Chapéu com flores de primavera", "Lanterna para vila de fantasia"],
      unknown: "Use o tipo de peça seguido do tema, como ‘Espada de fantasia’."
    },
    trabalho_texto: {
      description: "É a legenda que explica o que essa peça mostra sobre seu trabalho e como uma criação parecida pode servir ao projeto do comprador.",
      steps: ["Descreva a peça e o que você fez: modelagem, texturas ou outra contribuição real.", "Conecte uma característica visível ao uso possível. Quando for um estudo, apresente-o como projeto autoral; quando houver colaboração, informe sua parte."],
      examples: ["Espada autoral que modelei e texturizei. As formas e as cores mostram uma direção visual para armas de um jogo de fantasia.", "Chapéu floral que modelei para explorar acessórios de avatar. A imagem mostra a composição das flores e da aba.", "Nesta cena em colaboração, modelei a lanterna. Ela demonstra o tipo de objeto que posso criar para uma praça."],
      unknown: "Escreva ‘Modelei esta [peça] para explorar [tema ou estilo]’ e complete com o que a imagem realmente mostra."
    },
    trabalho_provas: {
      label: "Links de prova e detalhes",
      description: "São imagens ou vídeos adicionais que ajudam o visitante a conferir detalhes da mesma peça. Adicione uma prova, escolha o tipo, cole o link e explique o que ela mostra.",
      steps: ["Escolha um material seu que complemente a imagem principal: outro ângulo, detalhe, malha, teste no Studio ou vídeo.", "Clique em ‘Adicionar prova’ para preencher os três campos. Você pode acrescentar outros materiais ou remover uma linha; salve a apresentação para guardar os links."],
      examples: ["Um detalhe aproximado das flores do chapéu.", "Uma imagem da malha da espada que você modelou.", "Um vídeo que mostra a lanterna por vários ângulos."],
      unknown: "É opcional. Se ainda não tem material adicional, mantenha a imagem principal e acrescente as provas quando estiverem disponíveis."
    },
    prova_tipo: {
      label: "Tipo de prova",
      description: "Indica o tipo do material adicional. Render final é uma imagem da peça pronta; detalhe mostra uma parte; wireframe mostra as linhas da malha; Teste Studio mostra a peça no Roblox Studio; vídeo mostra uma gravação.",
      steps: ["Veja o material que você vai compartilhar e escolha a opção que melhor descreve o que aparece nele.", "Use a descrição para explicar o que o visitante consegue observar. Um teste no Studio deve corresponder ao que você realmente testou e registrou."],
      examples: ["Detalhe: imagem aproximada das flores do chapéu.", "Wireframe: imagem com as linhas da malha da espada.", "Vídeo: gravação da peça girando para mostrar seus lados."],
      unknown: "Se é uma imagem da peça pronta, escolha ‘Render final’. Se mostra apenas uma parte, escolha ‘Detalhe’."
    },
    prova_link: {
      description: "É o endereço público da imagem ou do vídeo que será aberto pelo visitante. Use o link completo do material que deseja mostrar.",
      steps: ["Abra a imagem ou o vídeo e copie seu endereço ou link de compartilhamento público, começando com https://.", "Confira se uma pessoa sem login consegue abrir o material. O conteúdo do link deve mostrar a mesma peça ou o detalhe descrito nesta prova."],
      examples: ["Endereço público de uma imagem com outro ângulo da sua peça.", "Link de compartilhamento de um vídeo seu mostrando o objeto.", "Endereço de uma imagem sua da peça no Roblox Studio."],
      unknown: "Deixe o link vazio enquanto prepara o material. Uma linha sem link não acrescenta uma prova à apresentação.",
      hint: "https://..."
    },
    prova_descricao: {
      label: "Descrição da prova",
      description: "É a explicação curta do material adicional. Conte o que o cliente deve observar ao abrir a imagem ou o vídeo.",
      steps: ["Identifique a peça e o detalhe que aparece, como acabamento, formas, malha ou posição no cenário.", "Descreva somente o que o material permite conferir. Se citar um teste, diga o que foi observado nele."],
      examples: ["Vista aproximada das flores que modelei para o chapéu.", "Linhas da malha da espada vistas por dois ângulos.", "Registro da lanterna posicionada no cenário no Roblox Studio."],
      unknown: "Use uma frase simples, como ‘Vista lateral da peça’. Pode deixar vazio e voltar para explicar melhor depois."
    },
    oferta_encomenda: {
      description: "É o serviço que uma pessoa pode contratar de você. Diga qual criação você faz e qual é o tamanho dessa encomenda: uma peça, um conjunto ou uma cena.",
      steps: ["Comece com o que você cria: acessório de avatar, objeto de cenário, arma, cabelo ou outra peça que você oferece.", "Acrescente o estilo ou tema e a quantidade. Se oferece vários serviços, destaque aqui uma encomenda fácil de entender; os detalhes dos arquivos vêm em ‘O que você entrega’."],
      examples: ["Modelagem de um chapéu floral para avatar Roblox.", "Criação de uma espada estilizada para um jogo de aventura.", "Modelagem de um objeto temático para uma experiência Roblox de marca."],
      unknown: "Se estiver em dúvida sobre como escrever, descreva a peça com suas palavras. Você pode ajustar esse texto depois de gerar a apresentação.",
      hint: "Ex.: Modelagem de uma espada estilizada para Roblox"
    },
    oferta_comprador: {
      description: "É o tipo de pessoa ou equipe que pode precisar do seu serviço. Isso ajuda o robô a escrever uma oferta que faça sentido para aquele comprador.",
      steps: ["Pense em quem encomenda a peça e decide contratar: um criador de itens de avatar, uma equipe de jogo ou um estúdio que atende marcas.", "Escolha o público mais relacionado à encomenda que você quer destacar. Você pode definir um tipo de comprador mesmo sem conhecer uma pessoa específica."],
      examples: ["Criadores de coleções de acessórios para avatares Roblox.", "Equipes que desenvolvem jogos de aventura.", "Estúdios que criam experiências Roblox para marcas."],
      unknown: "Use como ponto de partida o público sugerido pelo quiz. Na seção do kit, você poderá informar o nome de um cliente específico.",
      hint: "Ex.: Equipes que criam jogos de aventura"
    },
    oferta_uso: {
      description: "Conte onde a peça vai aparecer e qual função terá no projeto do comprador. Isso ajuda a explicar por que alguém precisaria da sua criação.",
      steps: ["Imagine a peça dentro do projeto: equipada por um avatar, colocada em um cenário ou usada na decoração de um evento virtual.", "Descreva esse uso em uma frase. Se ainda depende do pedido do cliente, apresente um uso possível que seja compatível com o seu serviço."],
      examples: ["Acessório para compor uma coleção de avatares com tema floral.", "Espada para equipar os personagens de um jogo de aventura.", "Objeto decorativo para a área de encontro de um evento virtual de marca."],
      unknown: "Você pode escrever ‘Uso definido conforme o projeto do cliente’ e detalhar isso na conversa sobre a encomenda.",
      hint: "Ex.: Equipar personagens de um jogo de aventura"
    },
    oferta_entregaveis: {
      description: "Liste o que o cliente recebe quando a encomenda termina. ‘Entregáveis’ significa o conjunto de arquivos e materiais incluídos no serviço.",
      steps: ["Separe os itens da entrega: modelo 3D, texturas, imagem de apresentação, arquivo editável ou variações, conforme o que você oferece.", "Indique a quantidade e os itens incluídos. Informe separadamente se também fará a importação ou a montagem no Roblox Studio, quando esse trabalho fizer parte do seu serviço."],
      examples: ["Um modelo 3D de espada e suas texturas.", "Um modelo de chapéu e duas imagens para apresentar a peça.", "Três objetos de cenário, cada um com seu arquivo de modelo e textura."],
      unknown: "Se o pedido ainda não está definido, use ‘Arquivos e materiais a definir conforme o escopo’. Escopo é a descrição do trabalho combinado com o cliente.",
      hint: "Ex.: Um modelo de espada, texturas e uma imagem da peça"
    },
    oferta_formatos: {
      description: "São os tipos dos arquivos entregues, normalmente reconhecidos pelo final do nome: .fbx, .obj, .blend ou .png, por exemplo.",
      steps: ["Confira quais arquivos você consegue exportar e quais o cliente precisa abrir. O .blend é o projeto do Blender; formatos como FBX e OBJ levam o modelo para outros programas; PNG pode ser usado para imagens de textura.", "Informe apenas os formatos incluídos na entrega. Entregar um arquivo de modelo, importar no Studio e publicar um item são serviços que você pode combinar separadamente."],
      examples: ["Modelo em FBX e texturas em PNG.", "Modelo em OBJ; arquivo editável .blend incluído.", "Formatos a combinar conforme o projeto do cliente."],
      unknown: "Se você ainda não sabe qual formato o comprador precisa, pode deixar a combinar e perguntar qual programa ele vai usar.",
      hint: "Ex.: FBX e PNG",
      source: {label: "Consultar a documentação de importação do Roblox Studio", url: "https://create.roblox.com/docs/studio/importer"}
    },
    oferta_prazo: {
      description: "É o tempo previsto para fazer a entrega e o momento em que essa contagem começa. O comprador precisa entender as duas coisas.",
      steps: ["Pense no tempo necessário para criar, conferir os arquivos e fazer os ajustes combinados. Considere também o tempo que você tem disponível.", "Diga se conta dias úteis ou corridos e quando começa: após receber as referências, aprovar o escopo ou outro ponto que você combinar. Os números dos exemplos são apenas ilustrativos."],
      examples: ["7 dias úteis após receber as referências e definir o escopo.", "Prazo informado depois de analisar o pedido.", "Entrega em etapas, com datas combinadas antes do início."],
      unknown: "Se precisa ver a complexidade da peça antes, escreva ‘Prazo a combinar após análise do pedido’. Você pode preencher sem escolher uma data agora.",
      hint: "Ex.: Prazo a combinar após análise do pedido"
    },
    oferta_revisoes: {
      description: "São as oportunidades para o cliente pedir ajustes durante a criação. Uma rodada de revisão reúne os ajustes enviados pelo cliente naquele momento.",
      steps: ["Defina quantas rodadas pretende incluir e em qual etapa o cliente verá o trabalho para comentar.", "Explique quais mudanças cabem nessa revisão. Ajustar uma cor ou uma proporção é diferente de trocar o pedido por outra peça; você pode combinar como tratar mudanças no escopo."],
      examples: ["Uma rodada de ajustes de cor e proporção após a primeira prévia.", "Duas rodadas de revisão dentro do escopo combinado.", "Revisões definidas na proposta de cada encomenda."],
      unknown: "Se ainda não decidiu, escreva ‘Quantidade e tipo de ajustes a combinar’. Escolha depois o que consegue incluir no seu serviço.",
      hint: "Ex.: Uma rodada de ajustes dentro do escopo"
    },
    oferta_suporte: {
      description: "É a ajuda oferecida depois de entregar os arquivos. Pode incluir esclarecer como abrir um arquivo ou corrigir um problema da entrega, conforme o combinado.",
      steps: ["Diga qual ajuda você oferece, por qual canal e por quanto tempo. Revisões acontecem durante a criação; suporte é o atendimento após a entrega.", "Informe se a ajuda inclui algum trabalho no Roblox Studio. Defina o que entra no atendimento para o cliente entender o que pode pedir."],
      examples: ["Ajuda pelo canal de contato para abrir os arquivos entregues.", "Ajustes de problemas nos arquivos entregues durante 7 dias.", "Suporte após a entrega definido na proposta."],
      unknown: "Se ainda não definiu esse atendimento, deixe em branco ou escreva ‘Suporte a combinar’. Os exemplos não acrescentam atendimento automaticamente à sua oferta.",
      hint: "Ex.: Suporte a combinar na proposta"
    },
    oferta_preco: {
      description: "É o valor ou a maneira de orçar o serviço. O cliente precisa saber se o valor corresponde a uma peça, a um conjunto ou ao projeto completo.",
      steps: ["Escolha a forma de apresentar: valor fechado para uma entrega definida, valor inicial com condições ou orçamento após analisar o pedido.", "Se escrever um número, diga a que ele se refere. A moeda tem um campo próprio. Os valores abaixo mostram apenas o formato de escrita; não são uma recomendação de quanto cobrar."],
      examples: ["250 por uma peça com o escopo descrito — valor fictício para exemplo.", "Orçamento após receber referências e definir o escopo.", "Valor combinado por conjunto de objetos."],
      unknown: "Você pode escrever ‘Sob orçamento’ ou deixar em branco. Para pensar no seu valor, liste o trabalho envolvido, os arquivos e os ajustes que pretende incluir.",
      hint: "Ex.: Sob orçamento"
    },
    oferta_moeda: {
      description: "Identifica em qual moeda um valor foi informado. BRL representa reais brasileiros; USD representa dólares americanos.",
      steps: ["Escolha a moeda em que pretende informar o preço ao comprador e escreva o nome ou a sigla.", "Use a mesma moeda ao combinar a proposta. Este campo identifica o valor; ele não converte preços nem define o meio de pagamento."],
      examples: ["BRL (reais brasileiros).", "USD (dólares americanos)."],
      unknown: "Se ainda vai combinar a moeda com o cliente, deixe em branco ou escreva ‘A combinar’.",
      hint: "Ex.: BRL ou USD"
    },
    oferta_condicoes: {
      description: "São os combinados que explicam como a contratação e a entrega acontecem: início do trabalho, pagamento, aprovação e mudanças no pedido.",
      steps: ["Escreva em frases simples o que o cliente precisa enviar para começar e como vocês confirmarão a encomenda.", "Acrescente as condições que você já definiu: etapas de pagamento, aprovação de prévias, envio dos arquivos e como serão combinados pedidos adicionais. Se tratar de uso dos arquivos ou exclusividade, diga apenas o que vocês realmente combinaram."],
      examples: ["O trabalho começa após definirmos a peça e recebermos as referências.", "Etapas de pagamento e entrega combinadas na proposta.", "Mudanças que acrescentem novas peças serão orçadas separadamente."],
      unknown: "Você pode escrever ‘Condições definidas na proposta antes do início’. Adapte os exemplos aos seus próprios combinados.",
      hint: "Ex.: Condições combinadas na proposta antes do início"
    },
    oferta_continuidade: {
      description: "É uma possibilidade de novo trabalho depois da primeira entrega. Ajuda o comprador a enxergar como você pode contribuir com outras partes do projeto.",
      steps: ["Pense no que faria sentido depois da peça inicial: outros itens da coleção, objetos do mesmo cenário ou uma nova variação.", "Apresente isso como uma nova encomenda que pode ser conversada. Descreva uma continuação relacionada ao serviço que você quer oferecer."],
      examples: ["Depois do chapéu, podemos definir outros acessórios para a mesma coleção.", "Novos objetos para ampliar a vila na mesma direção visual.", "Outras peças temáticas para as próximas áreas da experiência de marca."],
      unknown: "Pode deixar em branco se ainda não vê uma continuação útil. A oferta da primeira peça pode ser apresentada normalmente.",
      hint: "Ex.: Novos objetos para o mesmo cenário"
    },
    oferta_contato: {
      description: "É o endereço que o visitante poderá abrir para falar com você. Esse link fica público e será usado nos botões de contato da sua página.",
      steps: ["Abra o perfil, página de contato ou formulário que você quer usar e copie o endereço completo, começando com https://.", "Teste o link em uma janela sem login para ver se outra pessoa consegue chegar ao canal certo. Escolha um canal que você acompanha e deseja compartilhar com possíveis clientes."],
      examples: ["Link completo do seu perfil profissional com uma forma de contato.", "Link completo de uma página ou formulário para receber pedidos.", "Link público do canal que você usa para atender encomendas."],
      unknown: "Se ainda não escolheu um canal, pode deixar em branco e voltar depois. Um nome de usuário sozinho não é um endereço que o botão consegue abrir.",
      hint: "https://..."
    },
    oferta_exibir_preco: {
      description: "Escolha se o preço informado acima deve aparecer para qualquer visitante da sua página pública.",
      steps: ["Marque quando quiser mostrar um valor que o comprador consiga relacionar a uma entrega definida. O site usa os campos ‘Preço’ e ‘Moeda’ para exibi-lo.", "Deixe desmarcado quando preferir combinar o valor por orçamento. O preço informado ainda pode ser usado no texto privado da proposta do kit."],
      examples: ["Marcado: mostrar o valor de uma peça com entrega definida.", "Desmarcado: conversar sobre a encomenda e enviar o valor na proposta."],
      unknown: "Pode manter desmarcado enquanto decide como apresentar seus valores. Marcar essa opção sem preencher o preço não cria um valor automaticamente."
    },
    prospeccao_nome: {
      description: "É o nome da pessoa para quem você quer preparar a mensagem. O robô pode usá-lo na saudação para deixar o kit mais pessoal.",
      steps: ["Use o nome que a pessoa utiliza na conversa ou no perfil profissional. Pode ser o primeiro nome ou o nome público pelo qual ela se apresenta.", "Se o contato é com uma equipe e você ainda não sabe quem responde, deixe o nome vazio e informe a equipe em ‘Projeto ou empresa’."],
      examples: ["Ana.", "Lucas.", "Nome público usado pelo criador no perfil."],
      unknown: "Este campo é opcional. Sem um nome, a mensagem pode começar com uma saudação geral. Esses dados servem ao kit privado.",
      hint: "Ex.: Ana — se você já conhece o nome"
    },
    prospeccao_projeto: {
      description: "É o nome do jogo, coleção, estúdio ou empresa com que essa pessoa trabalha. Ajuda a relacionar a mensagem ao projeto dela.",
      steps: ["Informe o nome que aparece no perfil, anúncio ou conversa. Se o nome ainda não foi informado, uma descrição simples do projeto também ajuda.", "Você pode citar uma equipe, uma coleção de acessórios ou uma experiência de marca, conforme o caso."],
      examples: ["Vila Aurora — jogo de aventura (nome fictício).", "Coleção de acessórios com tema floral.", "Estúdio que produz um evento virtual de marca."],
      unknown: "Se ainda não conhece um projeto específico, deixe em branco. Você pode gerar um kit geral e personalizá-lo quando encontrar um possível cliente.",
      hint: "Ex.: Nome do jogo, coleção ou estúdio"
    },
    prospeccao_detalhe: {
      description: "Conte o que você já sabe sobre esse possível cliente: tema do projeto, estilo visual, momento da produção ou algo que ele publicou.",
      steps: ["Escreva de onde veio a informação: um anúncio de encomenda, uma publicação, o perfil ou uma conversa que vocês tiveram.", "Inclua um detalhe que conecte seu trabalho ao projeto. Se algo é apenas uma impressão sua, explique isso com palavras como ‘parece’ ou ‘talvez’."],
      examples: ["A equipe publicou que procura objetos para uma vila medieval.", "O perfil mostra uma coleção de acessórios inspirados em flores.", "Na conversa, a pessoa disse que está preparando uma área de encontro para um evento."],
      unknown: "Pode deixar em branco quando ainda não tiver informações. A mensagem será geral, sem fingir que você conhece o projeto.",
      hint: "Ex.: A equipe publicou que procura objetos para uma vila"
    },
    prospeccao_necessidade: {
      description: "É o que esse cliente precisa criar, completar ou resolver agora. Quanto mais claro o pedido, mais útil fica a abordagem e a proposta.",
      steps: ["Procure uma necessidade ligada ao seu serviço: uma peça que falta no cenário, um acessório para a coleção ou um objeto temático para um evento.", "Se a pessoa já contou o que precisa, resuma esse pedido. Se você está sugerindo uma possibilidade, escreva como hipótese para o robô manter esse tom."],
      examples: ["Precisa de uma lanterna para a praça da vila.", "Busca um chapéu floral para a nova coleção de avatares.", "Talvez precise de objetos temáticos para a área de encontro do evento."],
      unknown: "Se ainda não sabe, deixe em branco. A primeira mensagem pode perguntar quais peças a pessoa está procurando.",
      hint: "Ex.: Precisa de uma lanterna para a praça da vila"
    },
    prospeccao_demonstracao: {
      description: "Escolha um trabalho seu que ajude esse cliente a visualizar o tipo de criação que você oferece. É o exemplo que pode acompanhar a conversa.",
      steps: ["Escolha a peça mais próxima do tema, estilo ou uso do pedido e diga o que ela demonstra.", "Você pode usar o título de um trabalho da seção ‘Imagens e trabalhos’ ou um link acessível. Diga qual parte foi feita por você quando o trabalho teve colaboração."],
      examples: ["Minha espada de fantasia: mostra as formas e as cores que criei para esse tipo de peça.", "Meu chapéu floral: modelagem do acessório que aparece no portfólio.", "Meu objeto temático: exemplo de uma peça criada para compor uma cena."],
      unknown: "Se ainda não escolheu, deixe em branco. O robô pode relacionar a mensagem aos trabalhos que você selecionar para a geração.",
      hint: "Ex.: Minha espada de fantasia, na seção de trabalhos"
    },
    prospeccao_pedido: {
      description: "Cole aqui a mensagem ou o anúncio em que o cliente explica o que procura. Isso ajuda o robô a preparar uma proposta relacionada ao pedido.",
      steps: ["Copie a parte que descreve a peça, referências, quantidade, formatos, data desejada e outras informações úteis à encomenda.", "Pode colar o texto inteiro do pedido ou resumir os pontos principais. Dúvidas ainda abertas podem ser indicadas para a proposta pedir esse esclarecimento."],
      examples: ["‘Preciso de uma espada estilizada para meu jogo de aventura. Posso enviar as referências. Vocês entregam em FBX?’", "‘Estou procurando três objetos para uma vila. Quero saber o prazo e o que vem na entrega.’"],
      unknown: "Se você ainda vai fazer o primeiro contato e não recebeu um pedido, deixe este campo vazio. O kit pode ser gerado normalmente.",
      hint: "Cole o pedido ou descreva os pontos que o cliente informou"
    },
    prospeccao_idioma: {
      description: "Escolha o idioma dos quatro textos do kit: apresentação principal, bio curta, primeira abordagem e proposta.",
      steps: ["Use Português para conversas em português e English para preparar os textos em inglês.", "Depois de mudar o idioma, clique em ‘Gerar kit’ para criar uma nova versão. A troca da opção sozinha não traduz os textos existentes. A página pública continua em português."],
      examples: ["Português: kit para conversar com um cliente em português.", "English: kit em inglês para uma equipe que usa esse idioma."],
      unknown: "Se ainda não sabe quem vai receber o kit, pode manter Português e gerar uma versão em inglês depois."
    },
    posicionamento_comprador: {
      description: "Resuma quem você quer alcançar com esta apresentação. É o comprador principal que você escolheu em ‘Para quem’ na sua oferta.",
      steps: ["Escreva um tipo de pessoa ou equipe em poucas palavras. Se atende públicos diferentes, escolha o que deseja destacar nesta apresentação.", "Pergunte a si mesmo: quem precisa da criação que eu quero oferecer e pode encomendar esse trabalho?"],
      examples: ["Equipes de jogos de aventura.", "Criadores de coleções de acessórios de avatar.", "Estúdios de experiências Roblox para marcas."],
      unknown: "Você pode aproveitar o público da sua oferta. Ao gerar página e kit, o robô também sugere este resumo.",
      hint: "Ex.: Equipes de jogos de aventura"
    },
    posicionamento_necessidade: {
      description: "Resuma o que esse comprador quer conseguir com a sua criação. Pense no projeto dele e na peça que falta para avançar.",
      steps: ["Ligue o público à finalidade da peça: completar um cenário, criar uma coleção ou compor uma experiência temática.", "Escreva uma necessidade principal em uma frase curta. Aqui você pode falar do tipo de projeto; o pedido de uma pessoa específica fica nos dados do kit."],
      examples: ["Equipar os personagens com uma espada que combine com o jogo.", "Adicionar um acessório floral à coleção de avatares.", "Compor a área de encontro de um evento com objetos temáticos."],
      unknown: "Use a aplicação descrita em ‘Como o cliente vai usar’. O robô pode ajudar a resumir isso quando você gerar a apresentação.",
      hint: "Ex.: Equipar personagens com uma espada que combine com o jogo"
    },
    posicionamento_oferta: {
      description: "Escolha a encomenda que você quer colocar em destaque. A oferta completa reúne os detalhes; aqui você resume o serviço principal.",
      steps: ["Use uma criação que esteja dentro do serviço que você oferece e que atenda à necessidade descrita acima.", "Escreva uma frase curta com a peça e o trabalho incluído. Se oferece várias criações, escolha uma para ser a entrada desta apresentação."],
      examples: ["Modelagem de uma espada estilizada com texturas.", "Modelagem de um chapéu floral para avatar.", "Criação de um objeto temático para a experiência da marca."],
      unknown: "Comece pela encomenda que escreveu em ‘O que podem encomendar’. Você pode escolher outro destaque depois.",
      hint: "Ex.: Modelagem de uma espada estilizada com texturas"
    },
    posicionamento_prova: {
      description: "Diga qual trabalho seu sustenta essa oferta e o que o comprador pode observar nele. Um projeto autoral ou estudo concluído também pode demonstrar sua criação.",
      steps: ["Escolha um trabalho que você possa mostrar e cite uma característica concreta: formas, acabamento visual, texturas ou sua participação na criação.", "Você pode indicar a imagem da peça, detalhes, a visualização da malha ou um teste no Studio quando tiver esse material. Ao citar colaboração, explique o que foi feito por você."],
      examples: ["Minha espada de fantasia mostra a modelagem e as texturas que criei.", "Meu chapéu floral demonstra o visual de um acessório autoral.", "Meu totem temático mostra como desenvolvi formas e cores para uma cena."],
      unknown: "Se ainda não escolheu uma prova, deixe em branco e selecione seus trabalhos mais abaixo. Um teste técnico pode ser citado quando você tiver esse teste para mostrar.",
      hint: "Ex.: Minha espada mostra a modelagem e as texturas que criei"
    }
  };
  function addFieldGuide(wrap, input, guide) {
    if (!guide || !wrap) return;
    const description = document.createElement("p"); description.className = "ap-help-description";
    description.id = `ajuda-${input.id || input.name}`; description.textContent = guide.description;
    input.setAttribute("aria-describedby", description.id);
    const anchor = input.closest("label") || input;
    anchor.after(description);
    if (guide.hint && input.tagName !== "SELECT" && input.type !== "checkbox") input.placeholder = guide.hint;
    const details = document.createElement("details"); details.className = "ap-field-guide";
    const summary = document.createElement("summary"); summary.textContent = "Como preencher e exemplos";
    const label = guide.label || wrap.querySelector("label")?.textContent.trim() || input.name;
    summary.setAttribute("aria-label", `Como preencher e exemplos: ${label}`);
    const instructions = document.createElement("ol");
    guide.steps.forEach(step => { const item = document.createElement("li"); item.textContent = step; instructions.append(item); });
    const heading = document.createElement("h3"); heading.textContent = "Exemplos para adaptar ao seu trabalho";
    const examples = document.createElement("ul"); examples.className = "ap-guide-examples";
    guide.examples.forEach(example => { const item = document.createElement("li"); item.textContent = example; examples.append(item); });
    const unknown = document.createElement("p"); unknown.className = "ap-guide-unknown";
    const unknownTitle = document.createElement("strong"); unknownTitle.textContent = "Se ainda não souber: ";
    unknown.append(unknownTitle, document.createTextNode(guide.unknown));
    details.append(summary, instructions, heading, examples, unknown);
    if (guide.source) {
      const source = document.createElement("a"); source.href = guide.source.url; source.textContent = guide.source.label;
      source.target = "_blank"; source.rel = "noopener noreferrer"; details.append(source);
    }
    wrap.append(details);
  }
  const allFields = [...pageFields.map(([key]) => `pagina.${key}`), ...kitFields.map(([key]) => `kit.${key}`)];
  const initial = {
    versao: 1,
    posicionamento: {comprador: "", necessidade: "", oferta: "", prova: ""},
    pagina: {titulo: "", subtitulo: "", apresentacao: "", oferta: "", continuidade: "", diferenciais: "", condicoes: "", duvidas: "", cta: "", trabalho_destaque: "", legendas: []},
    kit: {apresentacao_principal: "", bio_curta: "", abordagem: "", proposta: ""}
  };
  const content = {
    ...initial, ...saved,
    posicionamento: {...initial.posicionamento, ...(saved.posicionamento || {})},
    pagina: {...initial.pagina, ...(saved.pagina || {})},
    kit: {...initial.kit, ...(saved.kit || {})}
  };
  if (!content.pagina.apresentacao) content.pagina.apresentacao = form.dataset.apresentacaoLegada || "";
  if (!content.pagina.oferta) content.pagina.oferta = form.dataset.servicoLegado || "";
  if (!content.posicionamento.comprador) content.posicionamento.comprador = form.elements.namedItem("oferta_comprador")?.value || "";
  if (!content.posicionamento.oferta) content.posicionamento.oferta = form.elements.namedItem("oferta_encomenda")?.value || "";
  const savedLegends = Array.isArray(content.pagina.legendas) ? content.pagina.legendas : [];
  const fieldElements = new Map();
  const positionPanel = document.createElement("section"); positionPanel.className = "ap-panel";
  const positionHeading = document.createElement("h2"); positionHeading.textContent = "Síntese do meu posicionamento";
  const positionHelp = document.createElement("p"); positionHelp.textContent = "Posicionamento é uma forma simples de explicar por que seu trabalho interessa a um comprador: quem você atende, o que ele precisa, qual serviço você oferece e qual peça demonstra isso. O robô sugere esse resumo ao gerar página e kit; você pode ajustar as quatro respostas.";
  const positionExample = document.createElement("details"); positionExample.className = "ap-walkthrough";
  const positionSummary = document.createElement("summary"); positionSummary.textContent = "Veja um exemplo das quatro respostas juntas";
  const positionExampleText = document.createElement("p"); positionExampleText.textContent = "Exemplo ilustrativo: atendo equipes de jogos de aventura (comprador) que precisam equipar seus personagens (necessidade). Ofereço a modelagem de uma espada estilizada com texturas (oferta prioritária), e minha espada autoral mostra o tipo de formas e cores que crio (prova). Use trabalhos e serviços seus ao preencher.";
  positionExample.append(positionSummary, positionExampleText);
  const positionGrid = document.createElement("div"); positionGrid.className = "ap-fields";
  positionPanel.append(positionHeading, positionHelp, positionExample, positionGrid);
  $(".ap-tabs").before(positionPanel);
  for (const [key, label] of positionFields) {
    const wrap = document.createElement("div"); wrap.className = "ap-field";
    const caption = document.createElement("label"); caption.htmlFor = `posicionamento_${key}`; caption.textContent = label;
    const input = document.createElement("input"); input.id = caption.htmlFor; input.name = input.id; input.value = String(content.posicionamento[key] || "");
    wrap.append(caption, input); addFieldGuide(wrap, input, fieldGuides[input.name]); positionGrid.append(wrap); fieldElements.set(`posicionamento.${key}`, input);
  }
  Object.entries(fieldGuides).forEach(([name, guide]) => {
    if (name.startsWith("posicionamento_")) return;
    const input = form.elements.namedItem(name);
    if (input) addFieldGuide(input.closest(".ap-field,.ap-orient"), input, guide);
  });
  function makeField(group, spec, mount) {
    const [key, label, title, kind, max] = spec;
    const path = `${group}.${key}`;
    const panel = document.createElement("section"); panel.className = "ap-panel";
    const row = document.createElement("div"); row.className = "ap-row";
    const heading = document.createElement("h2"); heading.textContent = title;
    const button = document.createElement("button"); button.type = "button"; button.className = "ap-generate"; button.dataset.gerar = path; button.textContent = "Gerar esta seção";
    row.append(heading, button);
    if (group === "kit") {
      const copy = document.createElement("button"); copy.type = "button"; copy.className = "ap-generate"; copy.dataset.copy = path; copy.textContent = "Copiar"; row.append(copy);
    }
    panel.append(row);
    const status = document.createElement("p"); status.className = "ap-status"; status.dataset.status = path; status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite"); panel.append(status);
    const wrapper = document.createElement("div"); wrapper.className = "ap-field";
    const caption = document.createElement("label"); caption.htmlFor = `${group}_${key}`; caption.textContent = label;
    const input = document.createElement(kind === "textarea" ? "textarea" : "input");
    input.id = `${group}_${key}`; input.name = input.id;
    if (kind !== "textarea") input.type = "text";
    if (max) input.maxLength = max;
    input.value = String(content[group][key] || "");
    wrapper.append(caption, input);
    addFieldGuide(wrapper, input, fieldGuides[input.name]);
    if (path === "kit.bio_curta") {
      const counter = document.createElement("small"); counter.id = "bio-contador"; counter.className = "ap-counter"; counter.setAttribute("aria-live", "polite"); wrapper.append(counter);
    }
    panel.append(wrapper); mount.append(panel); fieldElements.set(path, input);
  }
  pageFields.forEach(spec => makeField("pagina", spec, $("#campos-pagina")));
  kitFields.forEach(spec => makeField("kit", spec, $("#campos-kit")));
  const works = [...form.querySelectorAll(".ap-work")];
  for (const work of works) {
    const id = work.dataset.workId;
    const savedLegend = savedLegends.find(item => String(item.peca_id) === id);
    const title = $(`[name="legenda_titulo_${id}"]`, work);
    const description = $(`[name="legenda_texto_${id}"]`, work);
    title.value = savedLegend?.titulo || work.dataset.workTitle || "";
    description.value = savedLegend?.texto || work.dataset.workText || "";
    const selection = $('[name="trabalhos_ids"]', work);
    selection.id = `trabalho-selecao-${id}`;
    addFieldGuide(selection.closest("div"), selection, fieldGuides.trabalho_selecao);
    addFieldGuide(title.closest(".ap-field"), title, fieldGuides.trabalho_titulo);
    addFieldGuide(description.closest(".ap-field"), description, fieldGuides.trabalho_texto);
  }
  const proofTypes = [["render", "Render final"], ["detalhe", "Detalhe"], ["wireframe", "Wireframe"], ["studio", "Teste Studio"], ["video", "Vídeo"]];
  for (const work of works) {
    const id = work.dataset.workId;
    const raw = $(`[name="provas_${id}"]`, work);
    const editor = $(`[data-proofs-for="${id}"]`, work);
    if (!raw || !editor) continue;
    addFieldGuide(raw.closest(".ap-field"), raw, fieldGuides.trabalho_provas);
    editor.setAttribute("aria-describedby", raw.getAttribute("aria-describedby"));
    raw.hidden = true; raw.style.display = "none";
    const list = document.createElement("div"); editor.append(list);
    const add = document.createElement("button"); add.type = "button"; add.className = "ap-generate"; add.textContent = "Adicionar prova"; editor.append(add);
    const serialize = () => {
      raw.value = [...list.children].map(row => {
        const type = $("select", row).value;
        const url = $("[data-proof-link]", row).value.trim();
        const description = $("[data-proof-description]", row).value.trim();
        return url ? `${type} | ${url} | ${description}` : "";
      }).filter(Boolean).join("\n");
    };
    let proofSequence = 0;
    function addRow(type = "render", url = "", description = "") {
      if (list.children.length >= 8) return;
      const proofId = `prova-${id}-${++proofSequence}`;
      const row = document.createElement("div"); row.className = "ap-fields";
      const typeWrap = document.createElement("div"); typeWrap.className = "ap-field";
      const typeLabel = document.createElement("label"); typeLabel.textContent = "Tipo de prova";
      const select = document.createElement("select");
      select.id = `${proofId}-tipo`;
      proofTypes.forEach(([value, label]) => { const option = document.createElement("option"); option.value = value; option.textContent = label; select.append(option); });
      select.value = type; typeLabel.append(select); typeWrap.append(typeLabel);
      const urlWrap = document.createElement("div"); urlWrap.className = "ap-field";
      const urlLabel = document.createElement("label"); urlLabel.textContent = "Link público";
      const link = document.createElement("input"); link.type = "text"; link.inputMode = "url"; link.dataset.proofLink = ""; link.placeholder = "https://..."; link.value = url; urlLabel.append(link); urlWrap.append(urlLabel);
      link.id = `${proofId}-link`;
      const descWrap = document.createElement("div"); descWrap.className = "ap-field wide";
      const descLabel = document.createElement("label"); descLabel.textContent = "Descrição";
      const desc = document.createElement("input"); desc.type = "text"; desc.dataset.proofDescription = ""; desc.value = description; descLabel.append(desc); descWrap.append(descLabel);
      desc.id = `${proofId}-descricao`;
      addFieldGuide(typeWrap, select, fieldGuides.prova_tipo);
      addFieldGuide(urlWrap, link, fieldGuides.prova_link);
      addFieldGuide(descWrap, desc, fieldGuides.prova_descricao);
      const remove = document.createElement("button"); remove.type = "button"; remove.className = "ap-generate"; remove.textContent = "Remover prova";
      remove.addEventListener("click", () => { row.remove(); add.disabled = false; serialize(); sync(); });
      row.append(typeWrap, urlWrap, descWrap, remove); list.append(row);
      row.addEventListener("input", serialize); row.addEventListener("change", serialize);
      serialize();
    }
    const existing = raw.value.split(/\r?\n/).map(line => line.split("|", 3).map(part => part.trim())).filter(parts => parts.length >= 2 && parts[1]);
    existing.forEach(parts => addRow(parts[0], parts[1], parts[2] || ""));
    add.addEventListener("click", () => { addRow(); add.disabled = list.children.length >= 8; });
    if (existing.length >= 8) add.disabled = true;
  }
  const heroInput = $("#pagina_trabalho_destaque");
  heroInput.value = String(content.pagina.trabalho_destaque || "");
  heroInput.addEventListener("change", () => {
    const work = works.find(item => item.dataset.workId === heroInput.value);
    if (work) $("[name=trabalhos_ids]", work).checked = true;
    sync();
  });
  const workPanel = works[0]?.closest(".ap-panel");
  if (workPanel) {
    const heading = $("h2", workPanel);
    const row = document.createElement("div"); row.className = "ap-row";
    heading.replaceWith(row); row.append(heading);
    const button = document.createElement("button"); button.type = "button"; button.className = "ap-generate"; button.dataset.gerar = "pagina.legendas"; button.textContent = "Gerar legendas"; row.append(button);
    const status = document.createElement("p"); status.className = "ap-status"; status.dataset.status = "pagina.legendas"; status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite"); row.after(status);
  }
  const hidden = $("#conteudo-json");
  const get = path => {
    const [group, key] = path.split(".");
    return String(content[group]?.[key] || "");
  };
  const setText = (id, value, fallback = "Escreva aqui para ver a prévia.") => {
    const element = document.getElementById(id);
    if (!element) return;
    element.textContent = value || fallback;
    element.classList.toggle("ap-empty", !value);
  };
  function sync() {
    allFields.forEach(path => {
      const [group, key] = path.split(".");
      content[group][key] = fieldElements.get(path).value;
    });
    positionFields.forEach(([key]) => { content.posicionamento[key] = fieldElements.get(`posicionamento.${key}`).value; });
    content.pagina.trabalho_destaque = heroInput.value;
    content.pagina.legendas = works.map(work => ({
      peca_id: work.dataset.workId,
      titulo: $(`[name="legenda_titulo_${work.dataset.workId}"]`, work).value,
      texto: $(`[name="legenda_texto_${work.dataset.workId}"]`, work).value
    })).filter(item => item.titulo || item.texto);
    hidden.value = JSON.stringify(content);
    const bio = $("#bio-contador"); if (bio) bio.textContent = `${get("kit.bio_curta").length}/280`;
    render();
  }
  function render() {
    for (const key of ["titulo", "subtitulo", "apresentacao", "oferta", "diferenciais", "condicoes", "continuidade", "duvidas"])
      setText(`preview-${key}`, get(`pagina.${key}`));
    const contact = $("#preview-cta");
    contact.textContent = get("pagina.cta") || "Entrar em contato";
    const contactValue = form.elements.namedItem("oferta_contato")?.value || "";
    let safeContact = "";
    try { const url = new URL(contactValue); if (["https:", "http:"].includes(url.protocol)) safeContact = url.href; } catch (_) { /* sem link */ }
    contact.href = safeContact || "#";
    contact.setAttribute("aria-disabled", safeContact ? "false" : "true");
    let details = $("#preview-detalhes");
    if (!details) {
      details = document.createElement("div"); details.id = "preview-detalhes";
      $("#preview-trabalhos").before(details);
    }
    details.replaceChildren();
    const facts = [
      ["Entrega", "entregaveis"], ["Formatos", "formatos"], ["Prazo", "prazo"],
      ["Revisões", "revisoes"], ["Suporte", "suporte"]
    ];
    if (form.elements.namedItem("oferta_exibir_preco")?.checked) facts.push(["Preço", "preco"]);
    for (const [label, name] of facts) {
      const value = form.elements.namedItem(`oferta_${name}`)?.value?.trim();
      if (!value) continue;
      const paragraph = document.createElement("p");
      const strong = document.createElement("strong"); strong.textContent = `${label}: `;
      paragraph.append(strong, document.createTextNode(value)); details.append(paragraph);
    }
    const selected = works.filter(work => $("[name=trabalhos_ids]", work).checked);
    const heroWork = selected.find(work => work.dataset.workId === heroInput.value) || selected[0];
    const hero = $("#preview-hero"); hero.hidden = !heroWork;
    if (heroWork) { hero.src = heroWork.dataset.workImage; hero.alt = $("label", heroWork).textContent.trim(); }
    else hero.removeAttribute("src");
    const grid = $("#preview-trabalhos"); grid.replaceChildren();
    for (const work of selected) {
      const id = work.dataset.workId;
      const card = document.createElement("div"); card.className = "ap-preview-card";
      const img = document.createElement("img"); img.src = work.dataset.workImage; img.alt = ""; img.loading = "lazy";
      const title = document.createElement("strong"); title.textContent = $(`[name="legenda_titulo_${id}"]`, work).value || $("label", work).textContent.trim();
      const description = document.createElement("span"); description.textContent = $(`[name="legenda_texto_${id}"]`, work).value || $("small", work).textContent.trim();
      card.append(img, title, description); grid.append(card);
    }
    const kitPreviews = {apresentacao_principal: "apresentacao-principal", bio_curta: "bio-curta", abordagem: "abordagem", proposta: "proposta"};
    Object.entries(kitPreviews).forEach(([key, id]) => setText(`preview-${id}`, get(`kit.${key}`)));
  }
  form.addEventListener("input", sync);
  form.addEventListener("change", sync);
  form.addEventListener("submit", event => {
    if (pending > 0) {
      event.preventDefault();
      $("#status-salvar").textContent = "Aguarde a sugestão terminar para salvar.";
      return;
    }
    sync(); $("#status-salvar").textContent = "Salvando...";
  });
  const tabs = [...form.querySelectorAll(".ap-tab")];
  function openTab(which) {
    tabs.forEach(tab => { const active = tab.id === `tab-${which}`; tab.setAttribute("aria-selected", String(active)); tab.tabIndex = active ? 0 : -1; });
    $("#painel-pagina").hidden = which !== "pagina";
    $("#painel-kit").hidden = which !== "kit";
    $("#preview-pagina").hidden = which !== "pagina";
    $("#preview-kit").hidden = which !== "kit";
  }
  tabs.forEach(tab => tab.addEventListener("click", () => openTab(tab.id.slice(4))));
  async function copyText(value) {
    if (navigator.clipboard?.writeText) {
      try { await navigator.clipboard.writeText(value); return true; } catch (_) { /* usar alternativa */ }
    }
    const scratch = document.createElement("textarea");
    scratch.value = value; scratch.style.position = "fixed"; scratch.style.left = "-9999px";
    document.body.append(scratch); scratch.select();
    let copied = false;
    try { copied = document.execCommand("copy"); } catch (_) { /* navegador sem cópia */ }
    scratch.remove(); return copied;
  }
  form.querySelectorAll("[data-copy]").forEach(button => button.addEventListener("click", async () => {
    const path = button.dataset.copy;
    const status = form.querySelector(`[data-status="${path}"]`);
    const value = fieldElements.get(path)?.value || "";
    if (!value.trim()) { status.textContent = "Escreva ou gere o texto antes de copiar."; return; }
    status.textContent = await copyText(value) ? "Texto copiado." : "Não foi possível copiar. Selecione o texto acima para copiar.";
  }));
  function fieldsFor(requested) {
    return requested === "completo" ? [...allFields, ...positionFields.map(([key]) => `posicionamento.${key}`), "pagina.trabalho_destaque", "pagina.legendas"] : requested.split(",");
  }
  function snapshot(paths) {
    const values = {};
    paths.forEach(path => { values[path] = path === "pagina.legendas" ? JSON.stringify(content.pagina.legendas) : get(path); });
    return values;
  }
  function applyResult(result, paths, before) {
    const data = result?.conteudo;
    if (!data || typeof data !== "object") throw new Error(result?.erro || "A geração não trouxe textos. Seu rascunho foi mantido.");
    let applied = 0;
    for (const path of paths) {
      const [group, key] = path.split(".");
      const value = data[group]?.[key];
      if (value === undefined || value === null) continue;
      const current = path === "pagina.legendas" ? JSON.stringify(content.pagina.legendas) : get(path);
      if (current !== before[path]) continue;
      if (path === "pagina.legendas" && Array.isArray(value)) {
        for (const work of works) {
          const item = value.find(legend => String(legend.peca_id) === work.dataset.workId);
          if (!item) continue;
          const id = work.dataset.workId;
          $(`[name="legenda_titulo_${id}"]`, work).value = String(item.titulo || "");
          $(`[name="legenda_texto_${id}"]`, work).value = String(item.texto || "");
        }
        applied++;
      } else if (path === "pagina.trabalho_destaque" && typeof value === "string") {
        heroInput.value = value; applied++;
      } else if (typeof value === "string" && fieldElements.has(path)) {
        fieldElements.get(path).value = value; applied++;
      }
    }
    sync();
    if (!applied) throw new Error("Os textos foram alterados enquanto o robô gerava. Suas edições foram mantidas.");
    return applied;
  }
  let pending = 0;
  const saveButton = $("#salvar-apresentacao");
  async function generateOne(path, status, scope = null) {
    sync();
    const paths = scope || fieldsFor(path);
    const before = snapshot(paths);
    const body = new FormData(form);
    body.set("campo", path);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 145000);
    let response;
    try {
      response = await fetch(form.dataset.gerador, {method: "POST", credentials: "same-origin", headers: {"X-CSRFToken": body.get("csrfmiddlewaretoken")}, body, signal: controller.signal});
    } catch (_) {
      throw new Error("A sugestão demorou demais ou a conexão falhou. Seu rascunho foi mantido.");
    } finally { clearTimeout(timeout); }
    let result;
    try { result = await response.json(); } catch (_) { throw new Error("Não foi possível gerar agora. Seu rascunho foi mantido."); }
    if (!response.ok) throw new Error(result?.erro || "Não foi possível gerar agora. Seu rascunho foi mantido.");
    applyResult(result, paths, before);
    status.textContent = result.visao ? "Sugestão pronta com as imagens dos trabalhos. Você pode editar e salvar." : "Sugestão pronta a partir dos seus textos e dados. Você pode editar e salvar.";
  }
  form.querySelectorAll("[data-gerar]").forEach(button => button.addEventListener("click", async () => {
    const requested = button.dataset.gerar;
    const status = form.querySelector(`[data-status="${requested}"]`);
    const original = button.textContent;
    button.disabled = true; button.textContent = "Gerando...";
    pending++; saveButton.disabled = true;
    status.textContent = "Preparando sugestão...";
    try {
      if (requested.startsWith("kit.") && requested.includes(",")) {
        await generateOne("completo", status, kitFields.map(([key]) => `kit.${key}`));
      } else {
        await generateOne(requested, status);
      }
    } catch (error) { status.textContent = error.message || "Não foi possível gerar agora. Seu rascunho foi mantido."; }
    finally { pending--; saveButton.disabled = pending > 0; button.disabled = false; button.textContent = original; }
  }));
  openTab("pagina"); sync();
})();
