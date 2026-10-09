// Correção do relay descrita em https://github.com/evolution-foundation/evolution-api/releases/tag/2.4.0-rc1
// Mantém a Evolution 2.3.7 e suas dependências; ajusta apenas botões e listas.
const fs = require('fs');
const marca = '/* meshcraft-interativos-237 */';
const inicio = 'if((0,R.isJidGroup)(e)&&(l.useCachedGroupMetadata=!0),a&&(l.ephemeralExpiration=a),r&&(l.messageId=r),t.viewOnceMessage){let u=(0,R.generateWAMessageFromContent)';
const fim = 'if(!t.audio&&!t.poll&&!t.sticker&&!t.conversation&&e!=="status@broadcast"&&t.reactionMessage)';
const substituto = marca + `if((0,R.isJidGroup)(e))l.useCachedGroupMetadata=!0;if(a)l.ephemeralExpiration=a;if(r)l.messageId=r;
if(t.viewOnceMessage||t.interactiveMessage||t.listMessage){
let content=t.viewOnceMessage?.message?.interactiveMessage?t.viewOnceMessage.message:t;
let nodes=[];
if(content.interactiveMessage){nodes=[{tag:"biz",attrs:{},content:[{tag:"interactive",attrs:{type:"native_flow",v:"1"},content:[{tag:"native_flow",attrs:{v:"9",name:"mixed"}}]}]}];}
if(content.listMessage){content={...content,listMessage:{...content.listMessage,listType:1}};nodes=[{tag:"biz",attrs:{},content:[{tag:"list",attrs:{type:"product_list",v:"2"}}]}];}
let message=(0,R.generateWAMessageFromContent)(e,content,{timestamp:new Date,userJid:this.instance.wuid,messageId:r,quoted:n});
let ident=await this.client.relayMessage(e,content,{messageId:message.key.id,...(nodes.length?{additionalNodes:nodes}:{})});
message.key={id:ident,remoteJid:e,participant:(0,R.isPnUser)(e)?e:void 0,fromMe:!0};
return message;}`;

function corrigir(codigo) {
  if (codigo.includes(marca)) return codigo;
  const a = codigo.indexOf(inicio), b = codigo.indexOf(fim, a);
  if (a < 0 || b < a || codigo.indexOf(inicio, a + 1) >= 0) {
    throw new Error('Bundle diferente da Evolution 2.3.7 conferida.');
  }
  return codigo.slice(0, a) + substituto + codigo.slice(b);
}

if (require.main === module) {
  const caminho = process.argv[2];
  fs.writeFileSync(caminho, corrigir(fs.readFileSync(caminho, 'utf8')));
}
module.exports = { corrigir };
