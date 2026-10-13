const {test}=require('node:test');
const assert=require('node:assert/strict');
test('falha deliberada exclusivamente para provar recuperação',async()=>{
 await new Promise(resolve=>setTimeout(resolve,8000));
 assert.fail('Falha deliberada na candidata; a referência anterior deve voltar.');
});
