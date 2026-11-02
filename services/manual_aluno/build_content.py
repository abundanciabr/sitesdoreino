"""Prepare the approved manual text; no runtime dependency on Markdown."""
import json
import re
import sys
from pathlib import Path
import markdown


def html(text):
    return markdown.markdown(text.strip(), extensions=['tables'])


def build(source):
    text = Path(source).read_text(encoding='utf-8-sig')
    text = text[text.index('**MANUAL DO ALUNO DA MESHCRAFT**'):text.index('**Pendências para sua revisão**')]
    # Editorial observations remain identifiable, without claiming a lesson is available.
    text = re.sub(r'\*\*\[CONFERIR:.*?\]\*\*', '', text, flags=re.S)
    text = text.replace('*Cada pergunta abaixo corresponde a uma seção recolhível.*', '')
    blocks = re.split(r'\*\*Bloco [123] — .*?\*\*', text)[1:]
    first = blocks[0]
    welcome = first[:first.index('**Abertura conforme')]
    states = first[first.index('**Os cinco estados'):].strip(' \n-')
    states = states.replace('**Os cinco estados da sua atividade**', '')
    steps = re.split(r'\*\*Passo (\d) — (.*?)\*\*', blocks[1])[1:]
    result = {'welcome': html(welcome), 'states': html(states), 'steps': [], 'faq': []}
    for i in range(0, len(steps), 3):
        number, title, body = steps[i:i+3]
        step = {'number': int(number), 'title': title, 'variants': {}}
        body = body.strip(' \n-')
        if int(number) <= 3:
            step['body'] = html(body)
        else:
            pieces = re.split(r'\*\*(Clientes|UGC|Visual do jogo|Aprender modelagem) — (.*?)\*\*', body)
            step['lead'] = html(pieces[0])
            for j in range(1, len(pieces), 3):
                key = {'Clientes': 'freelancer', 'UGC': 'ugc', 'Visual do jogo': 'jogo', 'Aprender modelagem': 'aprender'}[pieces[j]]
                part = pieces[j+2].strip(' \n-')
                # The dynamic progress card supplies these actual values.
                part = re.sub(r'> \*\*Seu grau atual:.*?(?=Os próximos graus)', '', part, flags=re.S)
                part = part.replace('Seu acompanhamento continua mostrando:', 'Confira seu grau, sua meta pessoal, seu progresso reconhecido e o próximo marco no quadro do início deste manual.')
                step['variants'][key] = {'title': pieces[j+1], 'body': html(part)}
        result['steps'].append(step)
    faq = re.split(r'\*\*(.*?\?)\*\*', blocks[2])
    for i in range(1, len(faq), 2):
        result['faq'].append({'title': faq[i], 'body': html(faq[i+1].strip(' \n-'))})
    return result


if __name__ == '__main__':
    output = Path(__file__).with_name('content.json')
    output.write_text(json.dumps(build(sys.argv[1]), ensure_ascii=False, indent=2), encoding='utf-8')
