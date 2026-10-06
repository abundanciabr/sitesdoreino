"""Gestos da escola no sandbox, sem dinheiro real ou fila remunerada."""

from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from .sandbox_models import (
    AjusteSandbox, ArquivoSandbox, EntregaSandbox, MensagemSandbox,
    MovimentoMeshcoin, ParticipacaoSandbox, ProjetoSandbox,
)


class ErroSandbox(ValueError):
    """Gesto inválido no estado atual ou fora do site."""


_PROJETOS = [
    ("mascote-3d", "Mascote 3D da comunidade", "Modele um mascote simpático para a comunidade de criadores, com silhueta legível e expressão acolhedora.", ["Referência: animais estilizados de formas simples", "Paleta da identidade visual da escola"], ["Arquivo fonte 3D", "Render frontal e lateral", "Prévia giratória"], "Silhueta clara; malha limpa; materiais consistentes; arquivos editáveis."),
    ("pet-fantasia", "Pet de fantasia", "Crie um companheiro fantástico pequeno para um jogo casual; mostre personalidade no rosto e na pose.", ["Pets de jogos casuais", "Moodboard de criaturas fantásticas"], ["Modelo 3D", "Texturas", "Três poses renderizadas"], "Personalidade reconhecível; proporções coerentes; texturas sem falhas."),
    ("interface-inventario", "Interface de inventário", "Desenhe uma tela de inventário para jogo de aventura, navegável em desktop e celular.", ["Inventários de RPG", "Guia de acessibilidade de contraste"], ["Layout desktop", "Layout móvel", "Protótipo clicável"], "Hierarquia clara; estados de seleção; texto legível; navegação demonstrável."),
    ("animacao-corrida", "Ciclo de corrida", "Anime um personagem estilizado em um ciclo de corrida contínuo e expressivo.", ["Vídeo de referência de corrida", "Folha de poses-chave"], ["Arquivo fonte", "Vídeo do ciclo", "Folha de poses"], "Loop sem salto; peso convincente; timing consistente."),
    ("ambiente-floresta", "Ambiente de floresta", "Monte uma clareira de floresta para cena de jogo, com caminho visual e profundidade.", ["Fotos de florestas brasileiras", "Referência de iluminação ao entardecer"], ["Cena editável", "Render geral", "Render de detalhe"], "Composição orienta o olhar; escala consistente; iluminação legível."),
    ("prop-espada", "Espada estilizada", "Produza uma espada de fantasia pronta para uso em jogo, incluindo versão de apresentação.", ["Espadas estilizadas low poly", "Referência de materiais metálicos"], ["Modelo 3D", "UV e texturas", "Render de apresentação"], "Topologia econômica; UV sem sobreposições indevidas; leitura da arma."),
    ("cartaz-evento", "Cartaz de evento criativo", "Crie um cartaz digital para uma mostra de trabalhos dos alunos, com data e chamada fictícias.", ["Cartazes culturais contemporâneos", "Identidade visual da escola"], ["Cartaz editável", "Versão quadrada", "Imagem exportada"], "Informação legível; hierarquia visual; adaptação fiel entre formatos."),
    ("personagem-conceito", "Conceito de personagem", "Desenvolva um explorador original para um mundo de fantasia leve.", ["Referências de roupas de viagem", "Estudos de silhueta"], ["Folha de silhuetas", "Arte final", "Paleta de cores"], "Design original; detalhes apoiam a história; vistas consistentes."),
    ("efeito-magico", "Efeito mágico animado", "Crie um efeito visual curto de feitiço que começa, brilha e se dissipa.", ["Efeitos de partículas estilizadas", "Referência de timing de animação"], ["Arquivo fonte", "Vídeo com fundo neutro", "Sequência de quadros"], "Início e fim claros; ritmo legível; cor e movimento consistentes."),
    ("cenario-quarto", "Quarto de personagem", "Construa o quarto de um personagem estudante de artes e conte sua história pelos objetos.", ["Interiores compactos", "Referências de objetos de ateliê"], ["Cena 3D editável", "Render geral", "Dois detalhes"], "Ambiente conta uma história; escala e luz coerentes; objetos identificáveis."),
    ("icone-habilidade", "Ícones de habilidades", "Desenhe um conjunto de seis ícones para habilidades elementais de um jogo.", ["Sistemas de ícones para jogos", "Referência de símbolos elementais"], ["Seis ícones vetoriais", "Grade de construção", "Prévia em tamanho pequeno"], "Família visual coesa; cada habilidade distinguível; leitura em tamanho pequeno."),
]


def semear_projetos(*, site_id):
    projetos = []
    for slug, titulo, briefing, referencias, entregaveis, criterios in _PROJETOS:
        projeto, _ = ProjetoSandbox.objects.get_or_create(
            site_id=site_id, slug=slug,
            defaults=dict(titulo=titulo, briefing=briefing, referencias=referencias,
                          entregaveis=entregaveis, criterios=criterios),
        )
        projetos.append(projeto)
    return projetos


@transaction.atomic
def aceitar(*, site_id, pessoa_id, projeto_id):
    projeto = ProjetoSandbox.objects.select_for_update().filter(pk=projeto_id, site_id=site_id, ativo=True).first()
    if projeto is None:
        raise ErroSandbox("Projeto indisponível neste site.")
    if projeto.prazo_dias is None or projeto.ajustes_previstos is None or projeto.recompensa is None:
        raise ErroSandbox("A escola ainda precisa configurar prazo, ajustes e recompensa.")
    if ParticipacaoSandbox.objects.filter(site_id=site_id, pessoa_id=pessoa_id,
                                          status__in=["em_producao", "entregue", "em_ajuste"]).exists():
        raise ErroSandbox("Esta pessoa já tem um projeto em andamento.")
    agora = timezone.now()
    termos = dict(projeto_id=str(projeto.pk), titulo=projeto.titulo, briefing=projeto.briefing,
                  referencias=projeto.referencias, entregaveis=projeto.entregaveis,
                  criterios=projeto.criterios, prazo_dias=projeto.prazo_dias,
                  ajustes_previstos=projeto.ajustes_previstos, recompensa=str(projeto.recompensa))
    try:
        return ParticipacaoSandbox.objects.create(
            site_id=site_id, pessoa_id=pessoa_id, projeto=projeto, termos=termos,
            aceite_em=agora, prazo_ate=agora + timedelta(days=projeto.prazo_dias),
        )
    except IntegrityError as exc:
        raise ErroSandbox("Esta pessoa já tem um projeto em andamento.") from exc


def registrar_atrasos(*, site_id):
    return ParticipacaoSandbox.objects.filter(site_id=site_id, atraso_em__isnull=True,
        prazo_ate__lt=timezone.now(), status__in=["em_producao", "em_ajuste"]).update(atraso_em=timezone.now())


@transaction.atomic
def mensagem(*, site_id, participacao_id, ator_id, papel, texto):
    if papel not in MensagemSandbox.Papel.values or not texto.strip():
        raise ErroSandbox("Mensagem inválida.")
    participacao = ParticipacaoSandbox.objects.select_for_update().filter(pk=participacao_id, site_id=site_id).first()
    if participacao is None:
        raise ErroSandbox("Participação não encontrada neste site.")
    if papel == "aluno" and ator_id != participacao.pessoa_id:
        raise ErroSandbox("Mensagem de aluno sem autoria correspondente.")
    return MensagemSandbox.objects.create(participacao=participacao, ator_id=ator_id, papel=papel, texto=texto.strip())


@transaction.atomic
def entregar(*, site_id, participacao_id, pessoa_id, comentario="", arquivos=None):
    p = ParticipacaoSandbox.objects.select_for_update().filter(pk=participacao_id, site_id=site_id, pessoa_id=pessoa_id).first()
    if p is None or p.status not in ["em_producao", "em_ajuste"]:
        raise ErroSandbox("Entrega indisponível para esta pessoa.")
    arquivos = list(arquivos or [])
    if not arquivos:
        raise ErroSandbox("Inclua ao menos um arquivo na entrega.")
    rascunhos = []
    novos = []
    for item in arquivos:
        if isinstance(item, dict):
            exigidos = ("nome", "chave", "sha256", "tamanho", "mime")
            if any(item.get(campo) in (None, "") for campo in exigidos):
                raise ErroSandbox("Metadados do arquivo incompletos.")
            novos.append(item)
        else:
            arquivo = ArquivoSandbox.objects.select_for_update().filter(pk=item, participacao=p, entrega__isnull=True).first()
            if arquivo is None:
                raise ErroSandbox("Arquivo rascunho inválido.")
            rascunhos.append(arquivo)
    # A participação bloqueada serializa versões; a última versão vale como contador.
    ultima = EntregaSandbox.objects.filter(participacao=p).order_by("-versao").first()
    versao = ultima.versao + 1 if ultima else 1
    entrega = EntregaSandbox.objects.create(participacao=p, versao=versao, comentario=comentario)
    for arquivo in rascunhos:
        arquivo.entrega = entrega
        arquivo.save(update_fields=["entrega"])
    for item in novos:
        ArquivoSandbox.objects.create(participacao=p, entrega=entrega, **item)
    if p.atraso_em is None and timezone.now() > p.prazo_ate:
        p.atraso_em = timezone.now()
    p.status = ParticipacaoSandbox.Status.ENTREGUE
    p.save(update_fields=["status", "atraso_em"])
    return entrega


@transaction.atomic
def pedir_ajuste(*, site_id, participacao_id, autor_id, texto):
    p = ParticipacaoSandbox.objects.select_for_update().filter(pk=participacao_id, site_id=site_id).first()
    if p is None or p.status != "entregue" or not texto.strip():
        raise ErroSandbox("Ajuste indisponível.")
    limite = p.termos.get("ajustes_previstos")
    if limite is not None and AjusteSandbox.objects.filter(participacao=p).count() >= limite:
        raise ErroSandbox("Limite de ajustes atingido.")
    entrega = p.entregas.order_by("-versao").first()
    ajuste = AjusteSandbox.objects.create(participacao=p, entrega=entrega, texto=texto.strip(), autor_id=autor_id)
    p.status = ParticipacaoSandbox.Status.EM_AJUSTE
    p.save(update_fields=["status"])
    return ajuste


@transaction.atomic
def aprovar(*, site_id, participacao_id, aprovador_id):
    p = ParticipacaoSandbox.objects.select_for_update().filter(pk=participacao_id, site_id=site_id).first()
    if p is None:
        raise ErroSandbox("Participação não encontrada neste site.")
    if p.status == "aprovado":
        return p
    if p.status != "entregue":
        raise ErroSandbox("A entrega ainda não está pronta para aprovação.")
    entrega = p.entregas.order_by("-versao").first()
    if entrega is None or not entrega.arquivos.exists():
        raise ErroSandbox("Entrega sem arquivos.")
    agora = timezone.now()
    valor = Decimal(p.termos["recompensa"])
    MovimentoMeshcoin.objects.create(participacao=p, pessoa_id=p.pessoa_id, site_id=site_id,
                                     valor=valor, aprovador_id=aprovador_id)
    entrega.aprovada_em = agora
    entrega.save(update_fields=["aprovada_em"])
    p.status = ParticipacaoSandbox.Status.APROVADO
    p.aprovado_em = agora
    p.aprovado_por = aprovador_id
    p.save(update_fields=["status", "aprovado_em", "aprovado_por"])
    return p


def saldo(*, site_id, pessoa_id):
    return MovimentoMeshcoin.objects.filter(site_id=site_id, pessoa_id=pessoa_id).aggregate(total=Sum("valor"))["total"] or Decimal("0.00")


def historico(*, site_id, pessoa_id):
    return MovimentoMeshcoin.objects.filter(site_id=site_id, pessoa_id=pessoa_id).select_related("participacao__projeto").order_by("-criado_em")
