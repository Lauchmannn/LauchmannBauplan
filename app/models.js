/* Local, original cuboid approximations; no Mojang assets bundled. Coordinates Y-up. */
(function(root) {
'use strict';
const box=(x0,y0,z0,x1,y1,z1)=>[x0,y0,z0,x1,y1,z1];
const full=[box(0,0,0,1,1,1)];
function rotateBox(b, turns) {
  for(let i=0;i<turns;i++) b=[1-b[5],b[1],b[0],1-b[2],b[4],b[3]];
  return b;
}
function model(state) {
 const n=state.name.split(':').pop(), p=state.properties||{};
 let b=full, turns=0;
 const facing={north:0,east:1,south:2,west:3};
 if(n.endsWith('_slab')) b=p.type==='double'?full:[box(0,p.type==='top'?.5:0,0,1,p.type==='top'?1:.5,1)];
 else if(n.endsWith('_stairs')) {
   const top=p.half==='top', lo=top?.5:0, hi=top?1:.5, a=top?0:.5, z=top?.5:1;
   b=[box(0,lo,0,1,hi,1)];
   const shape=p.shape||'straight';
   if(shape.startsWith('outer')) b.push(box(shape.endsWith('left')?0:.5,a,0,shape.endsWith('left')?.5:1,z,.5));
   else {b.push(box(0,a,0,1,z,.5)); if(shape.startsWith('inner')) b.push(box(shape.endsWith('left')?0:.5,a,.5,shape.endsWith('left')?.5:1,z,1));}
   turns=facing[p.facing]||0;
 }
 else if(n.endsWith('_fence')||n==='nether_brick_fence') {
   b=[box(.375,0,.375,.625,1,.625)];
   for(const [dir,turn] of Object.entries(facing)) if(p[dir]==='true') for(const y of [.375,.75]) b.push(rotateBox(box(.4375,y,0,.5625,y+.1875,.5),turn));
 }
 else if(n.endsWith('_wall')) {
   b=p.up==='false'?[]:[box(.25,0,.25,.75,1,.75)];
   for(const [dir,turn] of Object.entries(facing)) if(p[dir]&&p[dir]!=='none'&&p[dir]!=='false') b.push(rotateBox(box(.3125,0,0,.6875,p[dir]==='tall'?1:.875,.5),turn));
 }
 else if(n.endsWith('_pane')||n==='iron_bars') {
   b=[box(.4375,0,.4375,.5625,1,.5625)];
   for(const [dir,turn] of Object.entries(facing)) if(p[dir]==='true') b.push(rotateBox(box(.4375,0,0,.5625,1,.5),turn));
 }
 else if(n.endsWith('_trapdoor')) {
   b=p.open==='true'?[box(0,0,0,1,1,.1875)]:[box(0,p.half==='top'?.8125:0,0,1,p.half==='top'?1:.1875,1)];
   turns=facing[p.facing]||0;
 }
 else if(n.endsWith('_door')) {
   b=[box(0,0,0,1,1,.1875)]; turns=((facing[p.facing]||0)+(p.open==='true'?(p.hinge==='right'?3:1):0))%4;
 }
 else if(n==='cactus') b=[box(.0625,0,.0625,.9375,1,.9375)];
 else if(n==='hopper') {
   b=[box(0,.625,0,1,1,.125),box(0,.625,.875,1,1,1),box(0,.625,.125,.125,1,.875),box(.875,.625,.125,1,1,.875),box(.125,.375,.125,.875,.625,.875),box(.25,.25,.25,.75,.375,.75)];
   if(p.facing==='down'||!p.facing) b.push(box(.375,0,.375,.625,.25,.625));
   else {b.push(box(.375,.25,0,.625,.5,.5));turns=facing[p.facing]||0;}
 }
 else if(n.endsWith('lantern')) {
   b=[box(.3125,.0625,.3125,.6875,.5,.6875),box(.25,0,.25,.75,.0625,.75),box(.25,.5,.25,.75,.5625,.75),box(.4375,.5625,.4375,.5625,p.hanging==='true'?1:.75,.5625)];
 }
 else if(n.endsWith('_carpet')||n==='moss_carpet') b=[box(0,0,0,1,.0625,1)];
 else if(n.endsWith('torch')) b=[box(.4375,0,.4375,.5625,.625,.5625)];
 else if(n==='chain') b=[box(.4375,0,.4375,.5625,1,.5625)];
 else if(n.endsWith('_bed')) b=[box(0,0,0,1,.5625,1)];
 else if(n.includes('chest')) b=[box(.0625,0,.0625,.9375,.875,.9375)];
 else if(n==='water'||n==='lava') b=[box(0,0,0,1,.875,1)];
 return b.map(v=>rotateBox(v.slice(),turns));
}
function opaque(state) {
 const n=state.name.split(':').pop();
 if(/glass|pane|leaves|water|lava|ice|bars/.test(n)) return false;
 const b=model(state);
 return b.length===1&&b[0].every((v,i)=>v===(i<3?0:1));
}
const faces=[
 {n:[0,0,1],c:[[0,0,1],[1,0,1],[1,1,1],[0,1,1]]},
 {n:[0,0,-1],c:[[1,0,0],[0,0,0],[0,1,0],[1,1,0]]},
 {n:[1,0,0],c:[[1,0,1],[1,0,0],[1,1,0],[1,1,1]]},
 {n:[-1,0,0],c:[[0,0,0],[0,0,1],[0,1,1],[0,1,0]]},
 {n:[0,1,0],c:[[0,1,1],[1,1,1],[1,1,0],[0,1,0]]},
 {n:[0,-1,0],c:[[0,0,0],[1,0,0],[1,0,1],[0,0,1]]}
];
// Each vertex: position, normal, RGB, UV, atlas tile, block picking ID.
function mesh(records,palette,colors,tiles,onChunk) {
 const occupied=new Map(), models=palette.map(model), solid=palette.map(opaque);
 const key=(x,y,z)=>`${x},${y},${z}`;
 for(let i=0;i<records.length;i+=4) occupied.set(key(records[i],records[i+1],records[i+2]),records[i+3]);
 const chunks=new Map(); let faceCount=0;
 for(let i=0;i<records.length;i+=4) {
   const [x,y,z,s]=records.subarray(i,i+4), ck=key(x>>4,y>>4,z>>4);
   let verts=chunks.get(ck); if(!verts) {verts=[];chunks.set(ck,verts);}
   for(const b of models[s]) for(const f of faces) {
     const axis=f.n.findIndex(v=>v!==0), side=f.n[axis]>0?axis+3:axis;
     const boundary=b[side]===(f.n[axis]>0?1:0);
     const neighbor=occupied.get(key(x+f.n[0],y+f.n[1],z+f.n[2]));
     if(boundary&&neighbor!==undefined&&solid[neighbor]) continue;
     // Remove faces completely covered by another box of the same model.
     if(models[s].some(other=>other!==b&&other[f.n[axis]>0?axis:axis+3]===b[side]&&[0,1,2].filter(a=>a!==axis).every(a=>other[a]<=b[a]&&other[a+3]>=b[a+3]))) continue;
     const tex=tiles[s][axis===1?(f.n[1]>0?1:2):0];
     const points=f.c.map(c=>c.map((v,a)=>b[a]+v*(b[a+3]-b[a])));
     const uAxis=axis===0?2:0,vAxis=axis===1?2:1;
     for(const idx of [0,1,2,0,2,3]) {const p=points[idx];verts.push(x+p[0]-.5,y+p[1]-.5,z+p[2]-.5,...f.n,...colors[s],p[uAxis],p[vAxis],tex,i/4+1);}
     faceCount++;
   }
   // Bound JS array memory while generating large structures.
   if(verts.length>13*6*8192) {onChunk(new Float32Array(verts));chunks.set(ck,[]);}
 }
 for(const verts of chunks.values()) if(verts.length) onChunk(new Float32Array(verts));
 return faceCount;
}
const api={model,opaque,mesh,rotateBox};
if(typeof module!=='undefined') module.exports=api; else root.BlockModels=api;
})(globalThis);
