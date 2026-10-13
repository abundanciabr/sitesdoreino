// Código de controle fixo: nunca importa ou executa arquivos da prévia.
import http from 'node:http';
import {readFile} from 'node:fs/promises';
const BASE='/admin/previas-operacionais';
const ROOT='/state';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function json(file){return JSON.parse(await readFile(ROOT+'/'+file,'utf8'));}
async function authorized(cookie){
 if(!cookie)return false;
 return await new Promise(resolve=>{
  const req=http.get('http://meshcraft-trilha-previa:8000/trilha/previa/autorizar/',{headers:{Host:'meshcraft.top',Cookie:cookie,'X-Forwarded-Proto':'https'}},res=>{res.resume();resolve(res.statusCode===204);});
  req.setTimeout(5000,()=>req.destroy());req.on('error',()=>resolve(false));
 });
}
const css='body{font:16px system-ui;margin:40px auto;max-width:1100px;padding:0 24px;background:#101820;color:#e5edf3}h1{font-size:32px}a{color:#8bd6cb}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:12px;border-bottom:1px solid #33414d}code{font-size:13px}iframe{background:white;width:100%;height:330px;border:1px solid #5c7383;border-radius:12px}p{line-height:1.6}.tag{color:#8bd6cb}';
http.createServer(async(req,res)=>{
 res.setHeader('Cache-Control','private, no-store');res.setHeader('X-Robots-Tag','noindex, nofollow');res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Referrer-Policy','no-referrer');
 res.setHeader('Content-Security-Policy',"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-src about:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'");
 if(req.url==='/healthz'){res.writeHead(200);res.end('ok');return;}
 try{
  const url=new URL(req.url,'http://local');
  if(url.pathname!==BASE&&url.pathname!==BASE+'/'){res.writeHead(404);res.end();return;}
  if(!await authorized(req.headers.cookie)){res.writeHead(403,{'Content-Type':'text/html; charset=utf-8'});res.end('<h1>Esta prévia é exclusiva para administradores.</h1>');return;}
  if(!['GET','HEAD'].includes(req.method)){res.writeHead(405);res.end();return;}
  const state=await json('public.json');
  let selected=url.searchParams.get('previa');
  let preview='';
  if(selected&&/^[a-z][a-z0-9-]{2,39}$/.test(selected)){
   const id=state.previas[selected];
   if(id&&/^[0-9a-f]{24}$/.test(id)){
    const record=await json('operations/'+id+'.json');
    if(record.estado==='concluida'&&/^[A-Za-z0-9_./-]+\.html$/.test(record.pagina)&&!record.pagina.includes('..')){
     const page=await readFile(ROOT+'/releases/'+id+'/'+record.pagina,'utf8');
     const policy="<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'\">";
     preview='<h2>'+esc(selected)+'</h2><p>Versão '+esc(id)+'</p><iframe sandbox="allow-scripts" referrerpolicy="no-referrer" srcdoc="'+esc(policy+page)+'"></iframe>';
    }else preview='<p>Operação em execução. A prévia aparece após os testes.</p>';
   }
  }
  const rows=state.operacoes.map(r=>'<tr><td><a href="?previa='+esc(r.nome)+'">'+esc(r.nome)+'</a></td><td><code>'+esc(r.id)+'</code></td><td>'+esc(r.estado)+'</td><td>'+esc(r.teste_exit_code??'—')+'</td><td>'+esc(r.atualizada_em)+'</td></tr>').join('');
  const html='<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Prévias operacionais • Meshcraft</title><style>'+css+'</style><p class="tag">MESHCRAFT · ADMINISTRAÇÃO</p><h1>Prévias operacionais</h1><p>Versões de código e testes isolados na VPS. Operações continuam após fechar a conexão e podem ser consultadas pelo mesmo identificador.</p>'+preview+'<h2>Operações</h2><table><tr><th>Prévia</th><th>Identificador</th><th>Resultado</th><th>Teste</th><th>Atualização (UTC)</th></tr>'+rows+'</table><p>Backup de código antes da alteração. Em falha, a referência anterior volta automaticamente. Nenhum banco é restaurado.</p><p><a href="'+BASE+'/">Atualizar acompanhamento</a> · <a href="/admin/documentos/operacao-site-contexto-retomada-20261013">Referência operacional</a></p></html>';
  res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(req.method==='HEAD'?undefined:html);
 }catch{res.writeHead(503);res.end('Acompanhamento temporariamente indisponível.');}
}).listen(8080,'0.0.0.0');
