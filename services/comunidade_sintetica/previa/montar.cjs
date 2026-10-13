const fs = require('node:fs');
const path = require('node:path');
const base = __dirname;
const modelo = fs.readFileSync(path.join(base, 'index.template.html'), 'utf8');
const motor = fs.readFileSync(path.join(base, 'motor.cjs'), 'utf8').trim();
fs.writeFileSync(path.join(base, 'index.html'), modelo.replace('/* MOTOR_INLINE */', () => motor));
