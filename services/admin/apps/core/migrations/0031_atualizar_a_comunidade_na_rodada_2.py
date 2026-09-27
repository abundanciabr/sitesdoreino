"""A pagina da Comunidade Meshcraft ganha as secoes da rodada 2 do dossie.

TAR-856, 27/09/2026: depois de pousarem o rastro da moderacao (TAR-847, PR
#2219), o quadro de contribuicoes (TAR-849, PR #2216) e o rastro de cada
reconhecimento (TAR-850, PR #2230), `documentos/comunidade.md` ganha duas
secoes novas: como funcionam as contribuicoes e o que a escola registra sobre
moderacao e reconhecimentos.

Esta migracao NUNCA sobrescreve uma edicao do mantenedor. `CORPO_DA_RODADA_1`
e uma copia CONGELADA do texto que a migracao `0030` semeou em 27/09/2026,
antes desta atualizacao (nao uma leitura do arquivo de hoje, que ja mudou):
comparar contra o texto de hoje sempre bateria, e a migracao perderia a unica
defesa que tem contra apagar uma edicao dele pela tela `/admin/documentos/`.
So quando o corpo no banco ainda for exatamente esse e que a migracao troca
o texto pelo da rodada 2 (lido de `documentos/comunidade.md` na imagem, pela
mesma porta de `semear_documento`), e so depois de guardar o texto antigo
numa `VersaoDoDocumento`: a atualizacao cria uma versao nova, nunca apaga a
anterior.

Documento ja divergente (mantenedor editou) ou pasta ausente na imagem:
a migracao nao faz nada, e o deploy segue verde.
"""

from django.db import migrations

from apps.core.documentos import de_texto, diretorio

NOME = "comunidade"

CORPO_DA_RODADA_1 = '# A Comunidade Meshcraft\n\nA Comunidade é o lugar onde quem estuda na Meshcraft pratica junto: cada pessoa\nentra num grupo pequeno, faz o desafio do seu estágio, recebe um retorno escrito\ncom critérios, melhora a peça e ajuda quem está um passo atrás. Esta página diz\no que a Comunidade é, o que você pode fazer agora e o que acontece quando a sua\nparticipação termina. Sem letra miúda.\n\n## Para quem é\n\nA Comunidade é para adultos com matrícula ativa na escola. Não existe cadastro\nseparado nem cobrança própria: **o acesso é o da sua matrícula vigente**. Quem\njá entra na sala de aula entra na Comunidade pela mesma porta.\n\nSe você ainda não é aluno, o caminho começa em\n[Como funciona a entrada na escola](/docs/como-funciona-a-entrada).\n\n## O que você ganha participando\n\n- **Um grupo com nome e responsável.** Poucas pessoas, no mesmo estágio, com uma\n  professora ou um monitor da escola respondendo por elas.\n- **Um desafio por vez, com critérios visíveis.** Você sabe antes de começar o\n  que a escola vai olhar na sua peça.\n- **Retorno escrito em até 24 horas.** Três coisas que funcionaram, uma\n  mudança para tentar e uma decisão clara: a porta seguinte abriu, abriu com um\n  ajuste, ou a peça volta com data para o novo envio.\n- **Histórico preservado.** Cada envio recebe um número. O envio 2 não apaga o\n  envio 1: os dois ficam lado a lado com o retorno de cada um.\n- **Reconhecimento com evidência.** Concluir o primeiro ciclo e ter a primeira\n  ajuda aceita por um colega são reconhecimentos concedidos uma vez, com o\n  critério escrito antes de você conquistar.\n- **Gente que depende de você.** As dúvidas do seu grupo sem resposta aparecem\n  para você como algo que só um colega pode destravar.\n\n## O que fazer agora\n\n1. **Entre no fórum da escola** em [/forum/](/forum/). Quem tem matrícula ativa\n   vê ali a área da Comunidade e, quando já estiver num grupo, a área do grupo.\n2. **Ainda sem grupo?** A escola coloca cada pessoa num grupo do seu estágio.\n   Enquanto isso não acontece, a área da Comunidade diz como pedir a entrada e\n   quem responde por ela.\n3. **Apresente-se no grupo.** Uma mensagem curta: em que aula você está e o que\n   quer fazer com modelagem 3D. É a primeira coisa que o responsável do grupo\n   espera ver.\n4. **Faça o desafio do estágio.** Ele é a aula em destaque no mapa do seu curso.\n   Entre pelo catálogo em [/cursos](/cursos), abra o seu curso e, antes de\n   enviar, confira a lista "aceito quando" da própria aula.\n5. **Envie a primeira versão** pelo botão de envio da aula, com o link da peça.\n   O retorno chega na página de laudo do envio e o fórum é o lugar de conversar\n   sobre ele.\n6. **Melhore e reenvie.** Se a peça voltar, a data do novo envio vem escrita no\n   laudo. O reenvio ganha o número seguinte e a versão anterior continua\n   visível.\n\n## Como pedir ajuda\n\nPedido de ajuda bom é aquele que um colega consegue atender. Abra um tópico na\nárea do seu grupo dizendo:\n\n- **o que você está tentando entregar** e o link da peça ou da tela;\n- **onde travou**, com a mensagem de erro ou a imagem do problema;\n- **o que já tentou.**\n\nQuem pode responder é qualquer pessoa do grupo, além do responsável. Quando uma\nresposta resolver, **você marca a resposta aceita**: isso encerra a dúvida para\nquem vier depois e conta como ajuda aceita para quem respondeu.\n\nNão existe mensagem privada entre alunos. Toda conversa acontece no grupo, onde\na escola enxerga e pode intervir.\n\n## Quem avalia e quem reconhece\n\n- **O desafio é avaliado pela professora do curso**, pelo laudo com critérios.\n  Colegas ajudam no grupo e têm a ajuda reconhecida, mas não assinam laudo.\n- **Ajuda aceita é decidida por quem pediu**: só a pessoa que abriu a dúvida\n  marca a resposta que resolveu.\n- **Reconhecimentos são concedidos uma vez.** Repetir a mesma ação não gera um\n  segundo reconhecimento. Curtida, quantidade de mensagens e tempo de casa não\n  provam competência e não concedem nada.\n- **Status não dá autoridade.** Moderar, avaliar e criar grupo são funções da\n  equipe da escola, separadas de qualquer reconhecimento.\n\nO que você já conquistou aparece em [/conquistas/marcos](/conquistas/marcos).\n\n## Regras da casa\n\n- Comunidade de adultos, com respeito nas críticas: aponte o problema e proponha\n  a mudança.\n- Links externos só de lugares permitidos pela escola. O fórum recusa os demais.\n- A evidência que você envia para provar um marco é sua e fica em camada\n  privada: colegas não a veem.\n- Seu estúdio só fica público se você pedir.\n- A moderação é humana. Conteúdo que vai para uma página pública passa pela\n  escola antes.\n\n## O que acontece quando a matrícula termina\n\nTermina a matrícula, termina a participação ativa. Sem prazo escondido e sem\ncondição nova: é a mesma regra que já vale para a sala de aula.\n\n| O que | Enquanto a matrícula está ativa | Depois que ela termina |\n|---|---|---|\n| Grupo e conversas do grupo | Você lê e escreve | O acesso se encerra |\n| Novos desafios e novos laudos | Disponíveis no seu estágio | Não há novos |\n| Reconhecimentos que você já recebeu | Visíveis no seu histórico | Continuam seus, como históricos |\n| Envios e laudos anteriores | Visíveis lado a lado | Continuam registrados |\n\nQuem volta a ter matrícula ativa volta a participar. O histórico e os\nreconhecimentos anteriores permanecem. Um grupo novo depende de vaga aberta no\nestágio em que você estiver.\n\n## Onde ver o estado da sua participação\n\nEsta página não traz números nem listas de pessoas. O que é seu está nas telas\ndo site: o seu curso, aberto pelo catálogo em [/cursos](/cursos), mostra a aula\nem destaque e cada envio; o fórum em [/forum/](/forum/) mostra o seu grupo e as dúvidas que esperam\npor alguém; a trilha em [/conquistas/marcos](/conquistas/marcos) mostra o que já\nfoi concedido e o que falta provar.'


def atualizar_para_a_rodada_2(apps, schema_editor):
    Documento = apps.get_model("core", "Documento")
    documento = Documento.objects.filter(nome=NOME).first()
    if documento is None:
        return  # sem semeadura anterior (0030 nao rodou): nada a atualizar
    if documento.corpo != CORPO_DA_RODADA_1:
        return  # o mantenedor ja editou pela tela; a migracao NUNCA sobrescreve

    pasta = diretorio()
    if pasta is None:
        return  # sem a pasta nesta imagem, a subida segue sem tocar o banco
    caminho = pasta / f"{NOME}.md"
    if not caminho.is_file():
        return
    campos = de_texto(NOME, caminho.read_text(encoding="utf-8"))

    VersaoDoDocumento = apps.get_model("core", "VersaoDoDocumento")
    VersaoDoDocumento.objects.create(
        documento=documento,
        titulo=documento.titulo,
        publico=documento.publico,
        ordem=documento.ordem,
        corpo=documento.corpo,
        salvo_por="",
        gesto="preservou o texto da rodada 1 antes da atualizacao da rodada 2",
    )
    documento.titulo = campos.titulo
    documento.publico = campos.publico
    documento.ordem = campos.ordem
    documento.corpo = campos.corpo
    documento.save()


def nao_desfaz(apps, schema_editor):
    """Descer nao apaga nada: o historico e o texto atual continuam."""


class Migration(migrations.Migration):
    dependencies = [("core", "0030_semear_a_comunidade")]
    operations = [migrations.RunPython(atualizar_para_a_rodada_2, nao_desfaz)]
