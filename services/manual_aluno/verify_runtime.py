"""Read-only integration checks with real enrollment records; no session creation."""
from runtime import Production, serving
from app import allowed, render

p = Production()
with serving('cursos'):
    from modules.cursos.apps.cursos.models import Curso
    from modules.cursos.apps.core.sessao import site_atual
    course = Curso.objects.filter(site_id=site_atual(), slug='primeiros-dolares').values('site_id', 'produto_id').get()
assert course['produto_id'] == '42e9c1f6-4b83-48fb-b512-eba18abe13ec'

with serving('alunos'):
    from modules.alunos.apps.matriculas.models import Matricula
    from modules.alunos.apps.matriculas.services import matriculas_que_valem
    valid = Matricula.objects.filter(site_id=course['site_id'], product_id=course['produto_id'],
                                    status__in=Matricula.STATUS_QUE_VALEM).first()
    assert valid is not None, 'No current course enrollment to verify'
    identity = {'autenticado': True, 'id': 'not-a-new-session', 'email': valid.email}
    rows = list(matriculas_que_valem(valid.email).values('site_id', 'product_id'))
    assert allowed(identity, rows, course)
    other = Matricula.objects.filter(site_id=course['site_id'], status__in=Matricula.STATUS_QUE_VALEM).exclude(product_id=course['produto_id']).exclude(email__in=Matricula.objects.filter(site_id=course['site_id'], product_id=course['produto_id'], status__in=Matricula.STATUS_QUE_VALEM).values('email')).first()
    if other:
        assert not allowed({'autenticado': True, 'id': 'not-a-new-session', 'email': other.email},
                           list(matriculas_que_valem(other.email).values('site_id', 'product_id')), course)
    print('enrollment checks: matching product accepted; unrelated product denied=' + str(bool(other)))

with serving('gamificacao'):
    from modules.gamificacao.apps.gamificacao.models import JornadaPessoal
    journey = JornadaPessoal.objects.filter(site_id=course['site_id']).first()
    if journey:
        person = str(journey.pessoa_id)
        before = (journey.revisao, journey.atualizada_em)
        data = p.progress(person, course['site_id'])
        assert data['atual']['ordem'] >= 1
        assert 'Um passo de cada vez.' in render(data)
        journey.refresh_from_db()
        assert before == (journey.revisao, journey.atualizada_em)
        print('individual progress: read and rendered without changing journey')
    else:
        raise AssertionError('No journey available for read-only integration check')
