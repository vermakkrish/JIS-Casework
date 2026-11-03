import { instance } from '@viz-js/viz';
import { readdirSync,readFileSync,writeFileSync } from 'node:fs';
const viz=await instance();
const root='docs/diagrams';
const files=readdirSync(root).filter(x=>x.endsWith('.dot')).sort();
for(const file of files){
  const result=viz.render(readFileSync(`${root}/${file}`,'utf8'),{format:'svg',engine:'dot'});
  if(result.status!=='success')throw new Error(`${file}: ${JSON.stringify(result.errors)}`);
  writeFileSync(`${root}/${file.replace('.dot','.svg')}`,result.output);
  console.log('Verified and rendered '+file);
}
writeFileSync(`${root}/index.html`,`<!doctype html><html lang="en"><head><meta charset="utf-8"><title>JIS corrected models</title><style>body{font:16px system-ui;color:#183f38;background:#f5f5ef;margin:40px auto;max-width:1200px;padding:0 24px}section{padding:30px;margin:30px 0;background:white;border:1px solid #dce1d8;border-radius:8px}img{width:100%;max-height:850px;object-fit:contain}a{color:#214d40}</style></head><body><h1>JIS corrected models</h1><p>Source-controlled Graphviz diagrams aligned with the implementation. See the requirements and decisions log for corrections and the README for the verified deployment status.</p>${files.map(f=>`<section><h2>${f.replace('.dot','').replaceAll('-',' ')}</h2><img src="${f.replace('.dot','.svg')}" alt="${f.replace('.dot','').replaceAll('-',' ')}"><p><a href="${f}">Editable DOT source</a></p></section>`).join('')}</body></html>`);
