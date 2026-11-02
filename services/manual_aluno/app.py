"""Course-specific student manual. No writes, enrollment bypass or shared cache."""
import json
from html import escape
from pathlib import Path
from urllib.parse import parse_qs, quote

ROOT = Path(__file__).parent
PATH = '/manual-do-aluno-primeiros-dolares'
CONTENT = json.loads((ROOT / 'content.json').read_text(encoding='utf-8'))
CSS = (ROOT / 'style.css').read_text(encoding='utf-8')
NAMES = {'freelancer': 'Clientes', 'ugc': 'Itens UGC', 'jogo': 'Visual do jogo', 'aprender': 'Aprender modelagem'}
OPENINGS = {
    'freelancer': 'Você escolheu criar peças 3D para clientes. Seu caminho começa com uma primeira criação, passa pela prática orientada e segue para entregas e recebimentos reconhecidos.',
    'ugc': 'Você escolheu criar seus próprios itens UGC — itens criados por usuários para o Roblox. Vamos acompanhar sua primeira criação, da ideia à apresentação final.',
    'jogo': 'Você escolheu criar a parte visual do seu jogo. Vamos acompanhar a criação de um objeto e as mudanças que ajudam a aproximá-lo do cenário que você imagina.',
    'aprender': 'Você escolheu aprender modelagem 3D. Vamos começar com uma criação simples e acompanhar o que você aprende ao construir, modificar e apresentar seu trabalho.',
}
STATES = ('Falta realizar', 'Aguardando análise', 'Precisa de ajuste', 'Análise não pôde ser concluída', 'Realização reconhecida')
LESSONS = {
    1: ['Os 3 pilares dos Primeiros dólares'],
    2: ['Conhecendo a interface', 'Salvando Projetos e Navegação', 'Seleção e Ferramentas de Seleção', 'Transformações'],
    3: ['Salvando Projetos e Navegação', 'Visões Predefinidas'],
    4: ['Introdução: Modelagem na prática', 'Introdução Texturas'],
    5: ['Transformações'],
    6: ['Portfólio', 'Como se organizar no trabalho'],
}


class Unavailable(Exception):
    pass


def allowed(identity, enrollments, course):
    """Enrollment service has already selected current access; match site AND product."""
    return bool(identity.get('autenticado') is True and identity.get('id') and identity.get('email')
                and course.get('site_id') and course.get('produto_id')
                and any(m.get('site_id') == course['site_id'] and m.get('product_id') == course['produto_id']
                        for m in enrollments))


def current_state(data):
    nxt = data.get('proxima')
    if not nxt:
        return STATES[4]
    order = nxt['ordem']
    pending = data.get('pending', {}).get(str(order))
    if pending:
        return STATES[3] if pending.get('estado') in ('falha', 'erro') else STATES[1]
    result = nxt.get('avaliacao_resultado')
    if result == 'falha':
        return STATES[3]
    if result == 'incompleta':
        return STATES[2]
    if data.get('caminho') == 'freelancer' and order == 5:
        for item in data.get('sandbox_avaliacoes', []):
            if not item.get('atual') or item.get('historico') or item.get('anterior_reinicio'):
                continue
            if item.get('estado') in ('falha', 'erro', 'invalida') or item.get('resultado') in ('falha', 'nao_examinado'):
                return STATES[3]
            if item.get('estado') != 'concluida':
                return STATES[1]
            return STATES[1] if item.get('resultado') == 'atende' else STATES[2]
    if data.get('caminho') == 'freelancer' and order >= 7:
        receipts = data.get('receipt_states', [])
        if receipts:
            if receipts[0] == 'falha':
                return STATES[3]
            if receipts[0] in ('pendente', 'analisando'):
                return STATES[1]
    return STATES[0]


def shell(title, body, support=False):
    scripts = ('<link rel="stylesheet" href="/cursos/static/cursos/suporte.css?v=20261014-publico24h2">'
               '<script defer src="/cursos/static/cursos/suporte.js?v=20261014-publico24h2" data-curso="primeiros-dolares"></script>') if support else ''
    return ('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex,nofollow,noarchive">'
            f'<title>{escape(title)} | Meshcraft</title><style>{CSS}</style></head>'
            '<body><a class="skip" href="#conteudo">Ir para o conteúdo</a>'
            '<header class="brand"><span class="symbol" aria-hidden="true">M</span><span>MESHCRAFT <small>ESCOLA DE CRIADORES</small></span></header>'
            f'<main id="conteudo">{body}</main><footer>Meshcraft · Aprender, criar e continuar.</footer>{scripts}</body></html>')


def render(data, preview=None):
    actual = data.get('caminho')
    selected = preview if preview in NAMES else actual if actual in NAMES else 'freelancer'
    nxt, current = data.get('proxima'), data['atual']
    state = current_state(data)
    step = min(current['ordem'], 6)
    if not nxt:
        step = 6
    fields = [('Seu objetivo', NAMES.get(actual, 'Escolha seu caminho em Meu motivo')),
              ('Faixa conquistada', current['nome']),
              ('Próxima conquista', nxt['nome'] if nxt else 'Percurso concluído'),
              ('Atividade atual', nxt['conquista'] if nxt else 'Continue estudando e praticando conforme seu objetivo.'),
              ('Situação', state)]
    summary = ''.join(f'<div><dt>{escape(k)}</dt><dd>{escape(str(v))}</dd></div>' for k, v in fields)
    degrees = ''
    if actual == 'freelancer' and current['ordem'] >= 7:
        goal = data.get('meta') if data.get('meta_escolhida') else 'Ainda não registrada'
        degrees = f'<div class="degrees"><h3>Seus graus e sua meta</h3><p>Grau atual: {escape(current["nome"])}.</p><p>Meta pessoal: {escape(str(goal))}. Progresso reconhecido: {escape(str(data.get("recognized_total", "R$ 0,00")))} · {data.get("percentual", 0)}%.</p><p>Próximo marco: {escape(nxt["conquista"]) if nxt else "Todos os graus deste percurso foram reconhecidos."}</p><a href="/trilha/recebimentos/">Registrar ou acompanhar recebimentos</a></div>'
    intro = OPENINGS.get(actual, 'O que você quer fazer com modelagem 3D? Escolha entre Clientes, Itens UGC, Visual do jogo e Aprender modelagem em Meu motivo. Se você já escreveu um motivo, ele continua sendo parte da sua história.')
    first = f'<section id="agora"><p class="eyebrow">BLOCO 1 · SEU PRÓXIMO PASSO</p><h2>Um passo de cada vez.</h2>{CONTENT["welcome"]}<p>{escape(intro)}</p><dl class="summary">{summary}</dl><a class="button" href="/trilha/">Abrir minha atividade na Trilha <span aria-hidden="true">↗</span></a><p class="caption">Confira na Trilha a atividade correspondente à sua próxima conquista. A faixa e o bônus chegam com a realização reconhecida, uma única vez.</p>{degrees}<details class="states"><summary>Entenda os cinco estados da sua atividade</summary>{CONTENT["states"]}</details></section>'
    choices = ''.join(f'<a class="path {"selected" if k == selected else ""}" href="{PATH}?caminho={k}#percurso" {"aria-current=\"true\"" if k == selected else ""}>{v}</a>' for k, v in NAMES.items())
    cards = []
    published = data.get('lesson_states', {})
    for s in CONTENT['steps']:
        n = s['number']
        variant = s['variants'].get(selected)
        content = s.get('body', '') if not variant else s.get('lead', '') + '<h4>' + escape(variant['title']) + '</h4>' + variant['body']
        lessons = ''.join(f'<li>{escape(name)} <span class="availability">{escape(published.get(name, "Consulte a disponibilidade na sala do curso"))}</span></li>' for name in LESSONS[n])
        note = f'<aside class="lesson-note"><h4>Aulas de apoio do curso</h4><ul>{lessons}</ul><p>São referências de estudo. Uma aula em preparo ainda não está disponível; siga as orientações da atividade. Assistir a uma aula extra não é um novo requisito de faixa.</p><details class="editorial"><summary>Espaço para o admin incluir os links das aulas</summary><p>Admin: se necessário, incluir aqui os links das aulas de apoio deste passo, após conferir sua disponibilidade para os alunos.</p></details></aside>'
        is_current = n == step and selected == actual and nxt
        marker = '<span class="tag">Seu passo atual</span>' if is_current else ''
        cards.append(f'<details class="step" id="passo-{n}" {"open" if is_current else ""}><summary><span class="step-number">0{n}</span><span><span class="step-title">{escape(s["title"])}</span>{marker}</span><span class="plus" aria-hidden="true">+</span></summary><div class="step-body">{content}{note}</div></details>')
    warning = '<p class="preview-note">Você está consultando outro caminho. Seu objetivo e seu progresso continuam os mesmos; a escolha é alterada somente em Meu motivo, na Trilha.</p>' if selected != actual else ''
    second = f'<section id="percurso"><p class="eyebrow">BLOCO 2 · SEU PERCURSO EM SEIS PASSOS</p><h2>Da primeira ideia<br>à sua conquista.</h2><p>Você começa na branca e avança pela amarela, azul, vermelha, verde, marrom e preta. Os três primeiros passos são comuns aos quatro caminhos.</p><p>XP registra sua progressão na plataforma e não representa dinheiro recebido.</p><div class="paths" aria-label="Consultar orientações dos quatro caminhos">{choices}</div>{warning}{"".join(cards)}</section>'
    faq = ''.join('<details class="faq"><summary>' + escape(item['title']) + '</summary><div>' + item['body'] + '</div></details>' for item in CONTENT['faq'])
    help_note = '<div class="help-note"><h3>Suporte da Meshcraft</h3><p>Use o botão <strong>Suporte</strong>, no canto da tela. Escreva sua dúvida, diga a atividade e inclua a mensagem apresentada. Para discordar de uma avaliação, explique qual parte não corresponde ao que entregou.</p><p>Na Trilha, <strong>Meu motivo</strong> guarda sua escolha; a atividade mostra os campos e a forma de envio. O inventário aceita arquivos de até 20 MB: BLEND, GLB, GLTF, OBJ, STL, FBX, ZIP, PNG, JPG, JPEG e WEBP. Siga também os limites específicos apresentados na atividade. Aceitar um formato no envio não garante que todo o seu conteúdo possa ser examinado.</p><p>O resultado e os ajustes são acompanhados na própria atividade. Para clientes, meta e recebimentos ficam em <a href="/trilha/recebimentos/">Recebimentos</a>.</p></div>'
    third = f'<section id="ajuda"><p class="eyebrow">BLOCO 3 · AJUDA PARA ESTUDAR E CONTINUAR</p><h2>Você pode voltar<br>sempre que precisar.</h2>{help_note}{faq}</section>'
    hero = '<div class="hero"><p class="eyebrow">PRIMEIROS DÓLARES COM ROBLOX</p><h1>Seu manual.<br><em>Sua próxima criação.</em></h1><p>Entenda seu caminho, encontre a atividade de agora e acompanhe o que você já conquistou.</p><div class="contents"><a href="#agora">01 Seu próximo passo</a><a href="#percurso">02 Os seis passos</a><a href="#ajuda">03 Ajuda para continuar</a></div></div>'
    return shell('Manual do Aluno — Primeiros Dólares', hero + first + second + third, support=True)


class Application:
    def __init__(self, provider):
        self.provider = provider

    def __call__(self, environ, start_response):
        status, extra = 200, []
        path = environ.get('PATH_INFO', '')
        if path == '/healthz':
            body = 'ok'
        elif path.rstrip('/') != PATH:
            status, body = 404, shell('Página não encontrada', '<h1>Página não encontrada.</h1>')
        elif environ.get('REQUEST_METHOD') not in ('GET', 'HEAD'):
            status, body = 405, shell('Método não permitido', '<h1>Método não permitido.</h1>')
            extra.append(('Allow', 'GET, HEAD'))
        else:
            try:
                identity, enrollments, course = self.provider.access(environ.get('HTTP_COOKIE', ''))
                if identity.get('autenticado') is not True:
                    status = 401
                    body = shell('Entre para abrir seu manual', '<p class="eyebrow">MANUAL DO ALUNO</p><h1>Entre para continuar.</h1><p>Este manual é exclusivo de quem tem acesso vigente ao curso Primeiros Dólares com Roblox.</p><a class="button" href="/entrar?next=' + quote(PATH, safe='') + '">Entrar na minha conta</a>')
                elif not allowed(identity, enrollments, course):
                    status = 403
                    body = shell('Acesso ao manual', '<p class="eyebrow">MANUAL DO ALUNO</p><h1>Este manual acompanha o seu curso.</h1><p>Não encontramos acesso vigente ao Primeiros Dólares com Roblox nesta conta. Estar conectado ou ter outro curso não libera este manual.</p><p>Confira se entrou na conta usada na matrícula. Se acredita que deveria ter acesso, use o Suporte.</p>', support=True)
                else:
                    data = self.provider.progress(identity['id'], course['site_id'])
                    body = render(data, parse_qs(environ.get('QUERY_STRING', '')).get('caminho', [None])[0])
            except Exception:
                # Never log cookies, enrollment details or exceptions containing private responses.
                status, body = 503, shell('Não foi possível conferir agora', '<h1>Não foi possível conferir seu acesso ou progresso agora.</h1><p>Tente novamente em instantes. Nenhuma conquista ou entrega foi alterada.</p>')
        content = body.encode('utf-8')
        reasons = {200: 'OK', 401: 'Unauthorized', 403: 'Forbidden', 404: 'Not Found', 405: 'Method Not Allowed', 503: 'Service Unavailable'}
        headers = [('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', str(len(content))),
                   ('Cache-Control', 'private, no-store, max-age=0'), ('Vary', 'Cookie'),
                   ('X-Robots-Tag', 'noindex, nofollow, noarchive'), ('X-Content-Type-Options', 'nosniff'),
                   ('Referrer-Policy', 'same-origin'), ('X-Frame-Options', 'DENY')]
        start_response(f'{status} {reasons[status]}', headers + extra)
        return [b'' if environ.get('REQUEST_METHOD') == 'HEAD' else content]
