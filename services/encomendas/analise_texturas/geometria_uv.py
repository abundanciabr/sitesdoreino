"""Interseção de triângulos UV: bordas compartilhadas não são sobreposição."""
import hashlib
import json
EPS = 1e-10


def area(poly):
    return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly, poly[1:]+poly[:1])))/2


def intersecao(a, b):
    cross = lambda p,q,r: (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    orientation = 1 if cross(*b) >= 0 else -1
    poly = list(a)
    for start,end in zip(b, b[1:]+b[:1]):
        out = []
        for p,q in zip(poly, poly[1:]+poly[:1]):
            dp,dq = orientation*cross(start,end,p),orientation*cross(start,end,q)
            if dp >= -EPS:
                out.append(p)
            if (dp >= -EPS) != (dq >= -EPS) and abs(dp-dq) > EPS:
                t=dp/(dp-dq)
                out.append((p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])))
        poly=out
        if not poly:
            return 0.0
    return area(poly)


def sobreposicoes(triangles, max_candidates=180000):
    boxes,degenerate=[],set()
    for face,uv in triangles:
        if area(uv) <= EPS:
            degenerate.add(face)
        else:
            boxes.append((min(p[0] for p in uv),max(p[0] for p in uv),min(p[1] for p in uv),max(p[1] for p in uv),face,uv))
    active,hits,checks,examples=[],set(),0,[]
    for current in sorted(boxes, key=lambda row:row[0]):
        active=[other for other in active if other[1]>current[0]+EPS]
        for other in active:
            if other[4]==current[4] or other[3]<=current[2]+EPS or current[3]<=other[2]+EPS:
                continue
            checks+=1
            if checks>max_candidates:
                return {'faces':sorted(hits),'exemplos':examples,'degeneradas':sorted(degenerate),'completa':False}
            if intersecao(current[5],other[5])>EPS:
                hits.update((current[4],other[4]))
                if len(examples)<8:
                    examples.append([other[4],current[4]])
        active.append(current)
    return {'faces':sorted(hits),'exemplos':examples,'degeneradas':sorted(degenerate),'completa':True}


def assinatura_geometria(triangles):
    faces=sorted(tuple(sorted(tuple(round(float(v),6) for v in p) for p in tri)) for tri in triangles)
    return hashlib.sha256(json.dumps(faces,separators=(',',':')).encode()).hexdigest()
