const fs=require('node:fs'),path=require('node:path');
const root=__dirname;
fs.writeFileSync(path.join(root,'index.html'),fs.readFileSync(path.join(root,'index.template.html'),'utf8').replace('/* MOTOR */',fs.readFileSync(path.join(root,'motor.cjs'),'utf8')));
