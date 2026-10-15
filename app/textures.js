/* Pixel fallbacks generated locally; installed Minecraft PNGs are used read-only. */
(function(root) {
'use strict';
function textureNames(state) {
 let n=state.name.split(':').pop(),p=state.properties||{}, base=n;
 for(const suffix of ['_stairs','_slab','_fence','_fence_gate','_wall','_button','_pressure_plate']) if(n.endsWith(suffix)) base=n.slice(0,-suffix.length);
 if(/^(oak|spruce|birch|jungle|acacia|dark_oak|mangrove|cherry|bamboo|crimson|warped|pale_oak)$/.test(base)) base+='_planks';
 const aliases={stone_brick:'stone_bricks',nether_brick:'nether_bricks',red_nether_brick:'red_nether_bricks',brick:'bricks',quartz:'quartz_block_side',purpur:'purpur_block',sandstone:'sandstone',cobblestone:'cobblestone'};
 base=aliases[base]||base;
 if(n.endsWith('_pane')) base=n.replace(/_pane$/,'');
 if(n.endsWith('_door')) base=n+'_'+(p.half==='upper'?'top':'bottom');
 if(n.endsWith('_trapdoor')) base=n;
 if(n==='cactus') return ['cactus_side','cactus_top','cactus_bottom'];
 if(n.endsWith('_log')||n.endsWith('_stem')) return [n,n+'_top',n+'_top'];
 if(n==='grass_block') return ['grass_block_side','grass_block_top','dirt'];
 if(n==='hopper') return ['hopper_outside','hopper_top','hopper_outside'];
 if(n==='water'||n==='lava') return [n+'_still',n+'_still',n+'_still'];
 if(n==='quartz_block') return ['quartz_block_side','quartz_block_top','quartz_block_bottom'];
 if(n==='sandstone'||n==='red_sandstone') return [n,n+'_top',n+'_bottom'];
 return [base,base,base];
}
function pixelTile(ctx,x,y,name,color) {
 let seed=2166136261;for(const c of name)seed=Math.imul(seed^c.charCodeAt(0),16777619);
 const noise=()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return (seed>>>0)/4294967295;};
 for(let j=0;j<16;j++)for(let i=0;i<16;i++) {
   let v=.85+noise()*.3;
   if(/brick|stone/.test(name)&&((j%8===0)||((i+(j<8?0:8))%16===0)))v=.60;
   if(/plank|door/.test(name)&&j%4===0)v=.65;
   if(/log|stem/.test(name)&&i%4===0)v=.65;
   if(/glass|pane/.test(name))v=(i===0||j===0||i===15||j===15||i===j)?1.3:.75;
   ctx.globalAlpha=/glass|pane/.test(name)&&!(i===0||j===0||i===15||j===15||i===j)?.15:1;
   ctx.fillStyle=`rgb(${color.map(c=>Math.max(0,Math.min(255,Math.round(c*255*v)))).join(',')})`;ctx.fillRect(x+i,y+j,1,1);ctx.globalAlpha=1;
 }
}
async function create(gl,palette,colors,changed) {
 const max=Math.min(1024,gl.getParameter(gl.MAX_TEXTURE_SIZE)),cols=max/16,limit=cols*cols;
 const image=document.createElement('canvas');image.width=image.height=max;const ctx=image.getContext('2d');ctx.imageSmoothingEnabled=false;
 const names=new Map(), slots=[];
 for(let i=0;i<palette.length;i++) slots.push(textureNames(palette[i]).map(name=>{
   if(!names.has(name)&&names.size<limit){const tile=names.size;names.set(name,tile);pixelTile(ctx,(tile%cols)*16,Math.floor(tile/cols)*16,name,colors[i]);}
   return names.get(name)??0;
 }));
 const texture=gl.createTexture();
 function upload(){gl.bindTexture(gl.TEXTURE_2D,texture);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,false);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,image);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.NEAREST);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.NEAREST);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);}
 upload();
 let local=0;
 try {
   const response=await fetch('/api/textures');if(!response.ok)throw new Error('texture catalog');
   const catalog=await response.json();const available=new Set(catalog.names);
   // Decode locally installed PNGs in small batches rather than opening thousands of requests.
   const entries=[...names].filter(([n])=>available.has(n));
   for(let i=0;i<entries.length;i+=8) await Promise.all(entries.slice(i,i+8).map(async([n,t])=>{
     try {const r=await fetch('/api/texture?name='+encodeURIComponent(n));if(!r.ok)return;const bmp=await createImageBitmap(await r.blob());ctx.drawImage(bmp,0,0,bmp.width,bmp.width,(t%cols)*16,Math.floor(t/cols)*16,16,16);bmp.close();local++;}catch{/* retain generated fallback */}
   }));
   upload();
 }catch{/* Minecraft installation is optional. */}
 changed(`${local} lokale Minecraft-Texturen · ${names.size-local} Pixel-Fallbacks`);
 return {texture,slots,cols};
}
root.BlockTextures={create,textureNames};
})(globalThis);
