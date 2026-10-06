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


_PROJETOS = [('prop-espada',
  'Espada estilizada',
  'espadas_objetos',
  'Modele uma espada de fantasia para um jogo, com lâmina, guarda e cabo de silhuetas distintas. Prepare '
  'materiais e uma apresentação estática.',
  ['Espadas estilizadas low poly', 'Estudo de metal e detalhes do cabo'],
  ['Fonte Blender', 'Modelo exportado', 'Texturas e prévia estática'],
  'Silhueta clara; topologia econômica; UV organizada; fonte editável.'),
 ('escudo-runico',
  'Escudo rúnico',
  'espadas_objetos',
  'Crie um escudo estilizado com emblema central e variação de materiais, mantendo leitura clara em tamanho '
  'pequeno.',
  ['Escudos medievais e símbolos geométricos', 'Referências de madeira e metal'],
  ['Fonte Blender', 'Modelo exportado', 'Prévia frontal e lateral'],
  'Emblema legível; espessura coerente; organização dos materiais.'),
 ('bau-aventura',
  'Baú de aventura',
  'espadas_objetos',
  'Construa um baú de tesouro fechado, com ferragens e detalhes que indiquem uso em um jogo de aventura.',
  ['Baús de madeira estilizados', 'Referências de fechaduras e ferragens'],
  ['Fonte Blender', 'Modelo exportado', 'Texturas e prévia'],
  'Escala consistente; formas bem definidas; materiais distinguíveis.'),
 ('mascote-3d',
  'Mascote 3D da comunidade',
  'pets',
  'Modele um mascote animal simpático para a comunidade, com silhueta legível e expressão acolhedora.',
  ['Animais estilizados de formas simples', 'Paleta da escola'],
  ['Arquivo fonte 3D', 'Render frontal e lateral', 'Prévia estática'],
  'Silhueta clara; malha limpa; materiais consistentes; arquivos editáveis.'),
 ('pet-fantasia',
  'Pet de fantasia',
  'pets',
  'Crie um companheiro fantástico pequeno para jogo casual; expresse personalidade no rosto e em uma pose '
  'estática.',
  ['Pets de jogos casuais', 'Moodboard de criaturas fantásticas'],
  ['Modelo 3D', 'Texturas', 'Prévias estáticas'],
  'Personalidade reconhecível; proporções coerentes; texturas sem falhas.'),
 ('cabelo-curto',
  'Cabelo curto estilizado',
  'cabelos',
  'Modele um cabelo curto em mechas amplas para um avatar, com volume legível de frente, lado e costas.',
  ['Penteados curtos estilizados', 'Referência de proporções da cabeça'],
  ['Fonte Blender', 'Modelo exportado', 'Prévias em três vistas'],
  'Mechas organizadas; silhueta consistente; encaixe demonstrado.'),
 ('cabelo-longo',
  'Cabelo longo em camadas',
  'cabelos',
  'Crie um penteado longo em camadas com mechas econômicas e desenho coerente em todas as vistas.',
  ['Penteados longos em camadas', 'Estudos de silhueta de cabelo'],
  ['Fonte Blender', 'Modelo exportado', 'Prévias em três vistas'],
  'Volume equilibrado; camadas legíveis; malha sem interseções indevidas.'),
 ('bone-estilizado',
  'Boné estilizado',
  'chapeus',
  'Modele um boné com aba, costuras simplificadas e um emblema original. Apresente o encaixe em uma cabeça '
  'de referência.',
  ['Bonés de aba curva', 'Estudo de emblemas geométricos'],
  ['Fonte Blender', 'Modelo exportado', 'Texturas e prévia'],
  'Aba e copa proporcionais; emblema legível; encaixe demonstrado.'),
 ('chapeu-fantasia',
  'Chapéu de fantasia',
  'chapeus',
  'Construa um chapéu de mago com aba e copa expressivas, incluindo um detalhe ornamental original.',
  ['Chapéus de fantasia', 'Estudos de tecido estilizado'],
  ['Fonte Blender', 'Modelo exportado', 'Prévias frontal e lateral'],
  'Silhueta original; ornamentação clara; materiais coerentes.'),
 ('personagem-conceito',
  'Conceito de personagem',
  'personagens',
  'Desenvolva um explorador original para um mundo de fantasia leve, em vistas estáticas consistentes.',
  ['Roupas de viagem', 'Estudos de silhueta'],
  ['Folha de silhuetas', 'Arte final', 'Paleta de cores'],
  'Design original; detalhes apoiam a história; vistas consistentes.'),
 ('personagem-robo',
  'Personagem robô explorador',
  'personagens',
  'Modele um robô explorador de formas simples com torso, membros e rosto expressivos. Entregue uma pose '
  'estática de apresentação.',
  ['Robôs estilizados', 'Estudos de proporção de personagens'],
  ['Fonte Blender', 'Modelo exportado', 'Prévias frontal e lateral'],
  'Proporções coerentes; peças organizadas; expressão e silhueta legíveis.')]


def semear_projetos(*, site_id):
    projetos = []
    for slug, titulo, categoria, briefing, referencias, entregaveis, criterios in _PROJETOS:
        projeto, _ = ProjetoSandbox.objects.get_or_create(
            site_id=site_id, slug=slug,
            defaults=dict(titulo=titulo, categoria=categoria, briefing=briefing, referencias=referencias,
                          entregaveis=entregaveis, criterios=criterios),
        )
        projetos.append(projeto)
    return projetos


@transaction.atomic
def aceitar(*, site_id, pessoa_id, projeto_id):
    projeto = ProjetoSandbox.objects.select_for_update().filter(pk=projeto_id, site_id=site_id, ativo=True, categoria__in=ProjetoSandbox.Categoria.values).first()
    if projeto is None:
        raise ErroSandbox("Projeto indisponível neste site.")
    if projeto.prazo_dias is None or projeto.ajustes_previstos is None or projeto.recompensa is None:
        raise ErroSandbox("A escola ainda precisa configurar prazo, ajustes e recompensa.")
    if ParticipacaoSandbox.objects.filter(site_id=site_id, pessoa_id=pessoa_id,
                                          status__in=["em_producao", "entregue", "em_ajuste"]).exists():
        raise ErroSandbox("Esta pessoa já tem um projeto em andamento.")
    agora = timezone.now()
    termos = dict(projeto_id=str(projeto.pk), titulo=projeto.titulo, categoria=projeto.categoria, briefing=projeto.briefing,
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
