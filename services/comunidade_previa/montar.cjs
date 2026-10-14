const fs=require('node:fs'),path=require('node:path');
const root=__dirname;
const html=fs.readFileSync(path.join(root,'index.template.html'),'utf8').replace('/* MOTOR */',fs.readFileSync(path.join(root,'motor.cjs'),'utf8'));
fs.writeFileSync(path.join(root,'index.html'),html);
// A mesma interface em página administrativa completa, sob CSP sem inline.
const assets=path.join(root,'../admin/apps/core/comunidade_assets');
fs.mkdirSync(assets,{recursive:true});
fs.writeFileSync(path.join(assets,'percurso.js'),html.match(/<script>([\s\S]*?)<\/script>/)[1]);
fs.writeFileSync(path.join(assets,'percurso.css'),html.match(/<style>([\s\S]*?)<\/style>/)[1]);
fs.writeFileSync(path.join(assets,'percurso.html'),html.replace(/<style>[\s\S]*?<\/style>/,'<link rel="stylesheet" href="/comunidade/assets/percurso.css">').replace(/<script>[\s\S]*?<\/script>/,'<script defer src="/comunidade/assets/percurso.js"></script>'));
