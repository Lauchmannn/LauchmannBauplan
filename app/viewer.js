'use strict';

const $ = (s) => document.querySelector(s);
const canvas = $('#glcanvas');
const loading = $('#loading');
const loadingText = $('#loadingText');
const ySlider = $('#ySlider');
const yValue = $('#yValue');
const visibleCount = $('#visibleCount');
const projectSelect = $('#projectSelect');
const toast = $('#toast');

let meta = null;
let surfaceRecords = new Uint16Array(0); // x,y,z,state
let activeRecords = new Uint16Array(0);
let currentLayerRecords = new Uint16Array(0);
let currentY = 0;
let currentMode = 'full';
let layerCache = new Map();
let loadToken = 0;

const gl = canvas.getContext('webgl2', {antialias:true, preserveDrawingBuffer:false});
if(!gl){ loadingText.textContent='WebGL 2 wird von diesem Browser/Grafiktreiber nicht unterstützt.'; throw new Error('WebGL2 unavailable'); }

// ---------------- Colors and block names ----------------
const COLORS = new Map(Object.entries({
  'minecraft:smooth_stone':[0.62,0.63,0.62], 'minecraft:hopper':[0.28,0.30,0.31], 'minecraft:lantern':[0.91,0.61,0.20],
  'minecraft:green_terracotta':[0.30,0.42,0.23], 'minecraft:lime_terracotta':[0.46,0.57,0.30], 'minecraft:green_wool':[0.25,0.49,0.18],
  'minecraft:green_concrete_powder':[0.32,0.45,0.17], 'minecraft:green_concrete':[0.20,0.43,0.16], 'minecraft:green_carpet':[0.25,0.49,0.18],
  'minecraft:water':[0.16,0.40,0.80], 'minecraft:sand':[0.82,0.77,0.57], 'minecraft:cactus':[0.20,0.50,0.18],
  'minecraft:quartz_block':[0.91,0.89,0.84], 'minecraft:oak_fence':[0.61,0.45,0.26], 'minecraft:stone_brick_wall':[0.47,0.48,0.46],
  'minecraft:oak_door':[0.61,0.44,0.25], 'minecraft:cobbled_deepslate':[0.26,0.27,0.27], 'minecraft:cobblestone':[0.43,0.44,0.43],
  'minecraft:dirt':[0.43,0.31,0.20], 'minecraft:glass':[0.72,0.88,0.90]
}));
function hslToRgb(h,s,l){const f=(p,q,t)=>{if(t<0)t+=1;if(t>1)t-=1;if(t<1/6)return p+(q-p)*6*t;if(t<.5)return q;if(t<2/3)return p+(q-p)*(2/3-t)*6;return p};if(!s)return[l,l,l];const q=l<.5?l*(1+s):l+s-l*s,p=2*l-q;return[f(p,q,h+1/3),f(p,q,h),f(p,q,h-1/3)];}
function fallbackColor(name){
 const dyes={white:[.88,.88,.86],orange:[.85,.39,.08],magenta:[.66,.2,.64],light_blue:[.35,.66,.82],yellow:[.9,.75,.13],lime:[.5,.72,.13],pink:[.9,.5,.62],gray:[.27,.29,.29],light_gray:[.62,.62,.59],cyan:[.09,.5,.53],purple:[.43,.19,.62],blue:[.2,.27,.65],brown:[.4,.26,.16],green:[.28,.38,.12],red:[.65,.14,.11],black:[.09,.1,.12]};
 const n=name.split(':').pop();for(const [d,c]of Object.entries(dyes).sort((a,b)=>b[0].length-a[0].length))if(n.startsWith(d+'_'))return c;
 if(/oak|wood|plank|fence|door|chest/.test(n))return /dark_oak/.test(n)?[.26,.18,.1]:/birch/.test(n)?[.78,.72,.5]:/spruce/.test(n)?[.43,.31,.18]:[.62,.48,.28];
 if(/grass|leaves|moss/.test(n))return [.35,.54,.2];if(/dirt|mud/.test(n))return [.45,.31,.2];
 if(/brick/.test(n)&&!/stone/.test(n))return [.58,.3,.23];if(/sand/.test(n))return [.8,.75,.55];
 if(/glass|ice/.test(n))return [.65,.82,.88];if(/deepslate/.test(n))return [.28,.29,.3];
 if(/quartz|snow|iron/.test(n))return [.83,.83,.8];if(/stone|cobble|andesite|gravel/.test(n))return [.52,.52,.5];
 if(/gold|lantern/.test(n))return [.9,.65,.2];
 let h=2166136261;for(let i=0;i<name.length;i++){h^=name.charCodeAt(i);h=Math.imul(h,16777619);}return hslToRgb(((h>>>0)%360)/360,.28,.52);
}

function stateInfo(idx){const p=meta.palette[idx]||{name:'minecraft:unknown',displayName:'Unbekannt'};const props=p.properties||{};const propText=Object.keys(props).length?Object.entries(props).map(([k,v])=>`${k}=${v}`).join(' · '):'Standard';return {...p,props,propText,color:COLORS.get(p.name)||fallbackColor(p.name)};}

// ---------------- Matrix helpers ----------------
function mat4Perspective(fovy,aspect,near,far){const f=1/Math.tan(fovy/2),nf=1/(near-far);return new Float32Array([f/aspect,0,0,0,0,f,0,0,0,0,(far+near)*nf,-1,0,0,2*far*near*nf,0]);}
function mat4Ortho(l,r,b,t,n,f){const lr=1/(l-r),bt=1/(b-t),nf=1/(n-f);return new Float32Array([-2*lr,0,0,0,0,-2*bt,0,0,0,0,2*nf,0,(l+r)*lr,(t+b)*bt,(f+n)*nf,1]);}
function mat4LookAt(eye,center,up){let[ex,ey,ez]=eye,[cx,cy,cz]=center;let zx=ex-cx,zy=ey-cy,zz=ez-cz;let len=Math.hypot(zx,zy,zz)||1;zx/=len;zy/=len;zz/=len;let xx=up[1]*zz-up[2]*zy,xy=up[2]*zx-up[0]*zz,xz=up[0]*zy-up[1]*zx;len=Math.hypot(xx,xy,xz)||1;xx/=len;xy/=len;xz/=len;let yx=zy*xz-zz*xy,yy=zz*xx-zx*xz,yz=zx*xy-zy*xx;return new Float32Array([xx,yx,zx,0,xy,yy,zy,0,xz,yz,zz,0,-(xx*ex+xy*ey+xz*ez),-(yx*ex+yy*ey+yz*ez),-(zx*ex+zy*ey+zz*ez),1]);}
function mat4Mul(a,b){const out=new Float32Array(16);for(let c=0;c<4;c++)for(let r=0;r<4;r++)out[c*4+r]=a[r]*b[c*4]+a[4+r]*b[c*4+1]+a[8+r]*b[c*4+2]+a[12+r]*b[c*4+3];return out;}

// ---------------- GL ----------------
function shader(type,src){const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(s));return s;}
function program(vs,fs){const p=gl.createProgram();gl.attachShader(p,shader(gl.VERTEX_SHADER,vs));gl.attachShader(p,shader(gl.FRAGMENT_SHADER,fs));gl.linkProgram(p);if(!gl.getProgramParameter(p,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(p));return p;}
const VS=`#version 300 es
precision highp float;
layout(location=0)in vec3 aPos;layout(location=1)in vec3 aNormal;layout(location=2)in vec3 aColor;
layout(location=3)in vec2 aUV;layout(location=4)in float aTile;layout(location=5)in float aId;
uniform mat4 uVP;uniform vec3 uCenter;
out vec3 vNormal;out vec2 vUV;flat out float vTile;flat out uint vId;
void main(){gl_Position=uVP*vec4(aPos-uCenter,1.);vNormal=aNormal;vUV=aUV;vTile=aTile;vId=uint(aId);}`;
const FS=`#version 300 es
precision highp float;
in vec3 vNormal;in vec2 vUV;flat in float vTile;uniform sampler2D uAtlas;uniform float uCols;out vec4 outColor;
void main(){vec2 tile=vec2(mod(vTile,uCols),floor(vTile/uCols));vec2 uv=(tile+(clamp(vec2(vUV.x,1.-vUV.y),0.,1.)*15.+.5)/16.)/uCols;
vec4 tex=texture(uAtlas,uv);if(tex.a<.3)discard;
float d=max(dot(normalize(vNormal),normalize(vec3(-.45,.9,.35))),0.);outColor=vec4(tex.rgb*(.58+d*.42),1.);}`;
const PICK_FS=`#version 300 es
precision highp float;precision highp int;
in vec2 vUV;flat in float vTile;flat in uint vId;uniform sampler2D uAtlas;uniform float uCols;out vec4 outColor;
void main(){vec2 tile=vec2(mod(vTile,uCols),floor(vTile/uCols));if(texture(uAtlas,(tile+(clamp(vec2(vUV.x,1.-vUV.y),0.,1.)*15.+.5)/16.)/uCols).a<.3)discard;
uint v=vId;outColor=vec4(float(v&255u)/255.,float((v>>8u)&255u)/255.,float((v>>16u)&255u)/255.,1.);}`;
const renderProgram=program(VS,FS),pickProgram=program(VS,PICK_FS);
let meshes=[],instanceCount=0,atlas=null;
function bindGeometry(buffer){
 gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
 const sizes=[3,3,3,2,1,1];let offset=0;
 for(let i=0;i<sizes.length;i++){gl.enableVertexAttribArray(i);gl.vertexAttribPointer(i,sizes[i],gl.FLOAT,false,52,offset*4);offset+=sizes[i];}
}
function drawMeshes(prog){
 gl.useProgram(prog);gl.uniformMatrix4fv(gl.getUniformLocation(prog,'uVP'),false,viewProjection());gl.uniform3fv(gl.getUniformLocation(prog,'uCenter'),centerVec());
 gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,atlas.texture);gl.uniform1i(gl.getUniformLocation(prog,'uAtlas'),0);gl.uniform1f(gl.getUniformLocation(prog,'uCols'),atlas.cols);
 for(const m of meshes){bindGeometry(m.buffer);gl.drawArrays(gl.TRIANGLES,0,m.count);}
}
gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.enable(gl.CULL_FACE);gl.cullFace(gl.BACK);gl.frontFace(gl.CCW);gl.disable(gl.DITHER);

const camera={yaw:-.72,pitch:.48,distance:100,target:[0,0,0],ortho:false};
function eye(){const cp=Math.cos(camera.pitch);return[camera.target[0]+camera.distance*cp*Math.sin(camera.yaw),camera.target[1]+camera.distance*Math.sin(camera.pitch),camera.target[2]+camera.distance*cp*Math.cos(camera.yaw)];}
function centerVec(){if(!meta)return new Float32Array([0,0,0]);return new Float32Array([(meta.size.x-1)/2,(meta.size.y-1)/2,(meta.size.z-1)/2]);}
function viewProjection(){const e=eye(),view=mat4LookAt(e,camera.target,[0,1,0]),aspect=canvas.width/Math.max(1,canvas.height);const maxDim=Math.max(meta.size.x,meta.size.y,meta.size.z);const proj=camera.ortho?mat4Ortho(-camera.distance*.52*aspect,camera.distance*.52*aspect,-camera.distance*.52,camera.distance*.52,-maxDim*20,maxDim*20):mat4Perspective(Math.PI/4,aspect,.05,Math.max(2500,maxDim*60));return mat4Mul(proj,view);}
function resize(){const dpr=Math.min(1.25,window.devicePixelRatio||1),w=Math.max(1,Math.floor(canvas.clientWidth*dpr)),h=Math.max(1,Math.floor(canvas.clientHeight*dpr));if(!pickFbo||canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;resizePickBuffer();}}
let renderQueued=false;function requestRender(){if(renderQueued)return;renderQueued=true;requestAnimationFrame(()=>{renderQueued=false;render();});}
function render(){if(!meta||!atlas)return;resize();gl.bindFramebuffer(gl.FRAMEBUFFER,null);gl.viewport(0,0,canvas.width,canvas.height);gl.clearColor(.53,.70,.81,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);drawMeshes(renderProgram);}
let meshJob=null;
function cancelMesh(){if(meshJob){meshJob.worker.terminate();meshJob.resolve(false);meshJob=null;}}
async function setActive(records){
 cancelMesh();activeRecords=records;instanceCount=records.length/4;
 for(const m of meshes)gl.deleteBuffer(m.buffer);meshes=[];
 const colors=meta.palette.map((_,i)=>stateInfo(i).color);
 function chunk(vertices){
   const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,vertices,gl.STATIC_DRAW);meshes.push({buffer,count:vertices.length/13});
 }
 function finish(count){visibleCount.textContent=`${instanceCount.toLocaleString('de-DE')} Blöcke · ${count.toLocaleString('de-DE')} Flächen`;requestRender();}
 if(instanceCount<4096){finish(BlockModels.mesh(records,meta.palette,colors,atlas.slots,chunk));return true;}
 loadingText.textContent='Sichtbare Flächen werden berechnet …';
 return new Promise((resolve,reject)=>{
   const worker=new Worker('/app/mesh-worker.js');meshJob={worker,resolve};
   worker.onmessage=({data})=>{
     if(data.vertices)chunk(new Float32Array(data.vertices));
     if(data.done||data.error){worker.terminate();meshJob=null;if(data.error)reject(new Error(data.error));else {finish(data.count);resolve(true);}}
   };
   worker.onerror=e=>{worker.terminate();meshJob=null;reject(new Error(e.message));};
   const copy=records.slice();worker.postMessage({records:copy.buffer,palette:meta.palette,colors,tiles:atlas.slots},[copy.buffer]);
 });
}

// ---------------- Data loading ----------------
async function fetchJSON(url){const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw new Error(`${url}: HTTP ${r.status}`);return r.json();}
async function fetchU16(url){const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw new Error(`${url}: HTTP ${r.status}`);return new Uint16Array(await r.arrayBuffer());}
function padY(y){return String(y).padStart(4,'0');}
async function loadLayer(y){if(layerCache.has(y))return layerCache.get(y);if(!(meta.nonemptyLayers||[]).includes(y)){const e=new Uint16Array(0);layerCache.set(y,e);return e;}const cache=layerCache;const raw=await fetchU16(`/projects/${meta.slug}/layers/y${padY(y)}.bin`);const n=raw.length/3,out=new Uint16Array(n*4);for(let i=0;i<n;i++){out[i*4]=raw[i*3];out[i*4+1]=y;out[i*4+2]=raw[i*3+1];out[i*4+3]=raw[i*3+2];}cache.set(y,out);return out;}
function filterSurface(maxY){let n=0;for(let i=0;i<surfaceRecords.length;i+=4)if(surfaceRecords[i+1]<maxY)n++;const out=new Uint16Array(n*4);let p=0;for(let i=0;i<surfaceRecords.length;i+=4)if(surfaceRecords[i+1]<maxY){out[p++]=surfaceRecords[i];out[p++]=surfaceRecords[i+1];out[p++]=surfaceRecords[i+2];out[p++]=surfaceRecords[i+3];}return out;}
function concatRecords(a,b){const out=new Uint16Array(a.length+b.length);out.set(a);out.set(b,a.length);return out;}
let rebuildToken=0;
async function rebuildActive(){if(!meta||!atlas)return;const token=++rebuildToken;loading.classList.remove('hidden');try{const layer=await loadLayer(currentY);if(token!==rebuildToken)return;currentLayerRecords=layer;let rec;if(currentMode==='layer')rec=currentLayerRecords;else if(currentMode==='cut')rec=concatRecords(filterSurface(currentY),currentLayerRecords);else rec=surfaceRecords;if(!await setActive(rec)||token!==rebuildToken)return;updateMaterials();updateDoneButton();}catch(e){showToast('Ladefehler: '+e.message,6000);}finally{if(token===rebuildToken)loading.classList.add('hidden');}}

async function loadProject(slug){
 const token=++loadToken;++rebuildToken;cancelMesh();
 loading.classList.remove('hidden');loadingText.textContent='Litematic wird geladen …';
 let nextAtlas=null;
 try {
   const nextMeta=await fetchJSON(`/projects/${encodeURIComponent(slug)}/metadata.json`);
   const nextSurface=await fetchU16(`/projects/${encodeURIComponent(slug)}/surface.bin`);
   if(token!==loadToken)return;
   const colors=nextMeta.palette.map(p=>COLORS.get(p.name)||fallbackColor(p.name));
   let textureStatus='';
   nextAtlas=await BlockTextures.create(gl,nextMeta.palette,colors,text=>{textureStatus=text;});
   if(token!==loadToken){gl.deleteTexture(nextAtlas.texture);return;}
   if(atlas)gl.deleteTexture(atlas.texture);
   for(const m of meshes)gl.deleteBuffer(m.buffer);meshes=[];
   meta=nextMeta;surfaceRecords=nextSurface;atlas=nextAtlas;layerCache=new Map();
   $('#textureStatus').textContent=textureStatus;
   $('#blockInfo').hidden=true;$('#blockEmpty').hidden=false;
   currentY=meta.initialY||0;ySlider.min=0;ySlider.max=Math.max(0,meta.size.y-1);ySlider.value=currentY;yValue.textContent=currentY+meta.originalBounds.minY;
   $('#projectTitle').textContent=meta.name;$('#mapBadge').textContent=`LITEMATIC · ${meta.size.x}×${meta.size.y}×${meta.size.z}`;
   fillProjectPanel();fitCamera();await rebuildActive();if(token!==loadToken)return;updateProgress();
   const u=new URL(location.href);u.searchParams.set('project',slug);history.replaceState(null,'',u);
 }catch(e){showToast(`Fehler: ${e.message}`,5000);console.error(e);}
 finally{if(token===loadToken)loading.classList.add('hidden');}
}

async function refreshProjects(preferred=null){const projects=await fetchJSON('/api/projects');projectSelect.innerHTML='';for(const p of projects){const o=document.createElement('option');o.value=p.slug;o.textContent=p.name;projectSelect.appendChild(o);}if(!projects.length){loading.classList.add('hidden');$('#visibleCount').textContent='Datei auswählen oder hierher ziehen';showToast('Noch kein Bauwerk importiert.',4000);return;}const q=new URL(location.href).searchParams.get('project');const wanted=preferred||q||projects[0].slug;projectSelect.value=projects.some(p=>p.slug===wanted)?wanted:projects[0].slug;await loadProject(projectSelect.value);}

// ---------------- Material lists ----------------
function aggregateLayer(records){const byName=new Map();for(let i=0;i<records.length;i+=4){const s=stateInfo(records[i+3]);const row=byName.get(s.name)||{name:s.name,displayName:s.displayName,count:0,color:s.color};row.count++;byName.set(s.name,row);}return [...byName.values()].sort((a,b)=>b.count-a.count||a.displayName.localeCompare(b.displayName));}
function materialRows(){if($('#materialScope').value==='all')return meta.materials.map(m=>({...m,color:COLORS.get(m.name)||fallbackColor(m.name)}));return aggregateLayer(currentLayerRecords);}
function updateMaterials(){if(!meta)return;const rows=materialRows(),sum=rows.reduce((a,b)=>a+b.count,0);$('#materialSummary').textContent=`${sum.toLocaleString('de-DE')} Blöcke · ${rows.length} Materialien`;const root=$('#materials');root.innerHTML='';for(const m of rows){const row=document.createElement('div');row.className='matRow';const c=m.color||COLORS.get(m.name)||fallbackColor(m.name);const stacks=Math.floor(m.count/64),rest=m.count%64;row.innerHTML=`<span class="matColor" style="background:rgb(${Math.round(c[0]*255)},${Math.round(c[1]*255)},${Math.round(c[2]*255)})"></span><span class="matName" title="${escapeHTML(m.name)}">${escapeHTML(m.displayName||m.name)}</span><span class="matCount">${m.count.toLocaleString('de-DE')}<small>${stacks?` · ${stacks} Stk${stacks!==1?'s':''}${rest?` + ${rest}`:''}`:''}</small></span>`;root.appendChild(row);}}
function escapeHTML(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

// ---------------- Project panel and progress ----------------
function fillProjectPanel(){$('#projectPanelTitle').textContent=meta.name;$('#projSource').textContent=meta.sourceFile;$('#projAuthor').textContent=meta.author||'Unbekannt';$('#projSize').textContent=`${meta.size.x} × ${meta.size.y} × ${meta.size.z}`;$('#projBlocks').textContent=meta.blockCount.toLocaleString('de-DE');$('#projSurface').textContent=meta.surfaceBlockCount.toLocaleString('de-DE');$('#projDataVersion').textContent=meta.minecraftDataVersion||'–';}
function progressKey(){return `lbp:${meta.slug}:doneLayers`;}
function doneLayers(){try{return new Set(JSON.parse(localStorage.getItem(progressKey())||'[]'));}catch{return new Set();}}
function setDoneLayers(s){try{localStorage.setItem(progressKey(),JSON.stringify([...s].sort((a,b)=>a-b)));}catch{showToast('Browser-Speicher ist gesperrt oder voll.',6000);}}
function updateDoneButton(){if(!meta)return;const d=doneLayers().has(currentY);$('#doneLayer').classList.toggle('isDone',d);$('#doneLayer').textContent=d?'Ebene fertig ✓':'Ebene fertig';}
function updateProgress(){if(!meta)return;const all=meta.nonemptyLayers||[],done=doneLayers(),count=all.filter(y=>done.has(y)).length,pct=all.length?Math.round(count/all.length*100):0;$('#progressText').textContent=`${pct} % (${count}/${all.length})`;$('#progressBar').style.width=`${pct}%`;}

// ---------------- Picking ----------------
let pickFbo=null,pickTex=null,pickDepth=null;
function resizePickBuffer(){if(!canvas.width||!canvas.height)return;if(!pickFbo){pickFbo=gl.createFramebuffer();pickTex=gl.createTexture();pickDepth=gl.createRenderbuffer();}gl.bindTexture(gl.TEXTURE_2D,pickTex);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.NEAREST);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.NEAREST);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA8,canvas.width,canvas.height,0,gl.RGBA,gl.UNSIGNED_BYTE,null);gl.bindRenderbuffer(gl.RENDERBUFFER,pickDepth);gl.renderbufferStorage(gl.RENDERBUFFER,gl.DEPTH_COMPONENT16,canvas.width,canvas.height);gl.bindFramebuffer(gl.FRAMEBUFFER,pickFbo);gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_2D,pickTex,0);gl.framebufferRenderbuffer(gl.FRAMEBUFFER,gl.DEPTH_ATTACHMENT,gl.RENDERBUFFER,pickDepth);gl.bindFramebuffer(gl.FRAMEBUFFER,null);}
function pick(clientX,clientY){if(!meta||!instanceCount)return;resize();gl.bindFramebuffer(gl.FRAMEBUFFER,pickFbo);gl.viewport(0,0,canvas.width,canvas.height);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);drawMeshes(pickProgram);const rect=canvas.getBoundingClientRect(),x=Math.floor((clientX-rect.left)*canvas.width/rect.width),y=Math.floor((rect.bottom-clientY)*canvas.height/rect.height),px=new Uint8Array(4);gl.readPixels(x,y,1,1,gl.RGBA,gl.UNSIGNED_BYTE,px);gl.bindFramebuffer(gl.FRAMEBUFFER,null);const id=px[0]+(px[1]<<8)+(px[2]<<16)-1;if(id>=0&&id<instanceCount){const o=id*4,xv=activeRecords[o]+meta.originalBounds.minX,yv=activeRecords[o+1]+meta.originalBounds.minY,zv=activeRecords[o+2]+meta.originalBounds.minZ,state=activeRecords[o+3],info=stateInfo(state);$('#blockEmpty').hidden=true;$('#blockInfo').hidden=false;$('#blockName').textContent=info.displayName||info.name;$('#blockCoord').textContent=`X ${xv} · Y ${yv} · Z ${zv}`;$('#blockId').textContent=info.name;$('#blockVariant').textContent=info.propText;const c=info.color;$('#blockSwatch').style.background=`rgb(${c.map(v=>Math.round(v*255)).join(',')})`;$('#coords').textContent=`X ${xv} · Y ${yv} · Z ${zv}`;}}

// ---------------- Camera interaction ----------------
function fitCamera(){if(!meta)return;const maxDim=Math.max(meta.size.x,meta.size.y,meta.size.z);camera.target=[0,0,0];camera.yaw=-.72;camera.pitch=.48;camera.distance=Math.max(18,maxDim*2.1);camera.ortho=false;$('#view3d').classList.add('active');$('#viewTop').classList.remove('active');requestRender();}
let drag=null,moved=false;canvas.addEventListener('mousedown',e=>{drag={x:e.clientX,y:e.clientY,button:e.button};moved=false;e.preventDefault();});window.addEventListener('mousemove',e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>2)moved=true;if(drag.button===0){camera.yaw-=dx*.008;camera.pitch=Math.max(-1.45,Math.min(1.45,camera.pitch-dy*.008));}else if(drag.button===2){const scale=camera.distance*.0024;camera.target[0]-=dx*scale;camera.target[1]+=dy*scale;}drag.x=e.clientX;drag.y=e.clientY;requestRender();});window.addEventListener('mouseup',e=>{if(drag&&!moved&&e.button===0)pick(e.clientX,e.clientY);drag=null;});canvas.addEventListener('contextmenu',e=>e.preventDefault());canvas.addEventListener('wheel',e=>{e.preventDefault();camera.distance=Math.max(4,Math.min(5000,camera.distance*Math.exp(e.deltaY*.001)));requestRender();},{passive:false});window.addEventListener('resize',requestRender);

// ---------------- UI ----------------
function setY(y){if(!meta)return;currentY=Math.max(0,Math.min(meta.size.y-1,Number(y)));ySlider.value=currentY;yValue.textContent=currentY+meta.originalBounds.minY;rebuildActive();}
ySlider.addEventListener('input',()=>setY(ySlider.value));$('#yMinus').onclick=()=>setY(currentY-1);$('#yPlus').onclick=()=>setY(currentY+1);
$('#modeButtons').addEventListener('click',e=>{const b=e.target.closest('button[data-mode]');if(!b)return;currentMode=b.dataset.mode;for(const x of $('#modeButtons').querySelectorAll('button'))x.classList.toggle('active',x===b);rebuildActive();});
$('#view3d').onclick=()=>{camera.ortho=false;camera.yaw=-.72;camera.pitch=.48;$('#view3d').classList.add('active');$('#viewTop').classList.remove('active');requestRender();};
$('#viewTop').onclick=()=>{camera.ortho=true;camera.yaw=0;camera.pitch=1.569;$('#viewTop').classList.add('active');$('#view3d').classList.remove('active');requestRender();};
$('#fitBtn').onclick=fitCamera;$('#materialScope').onchange=updateMaterials;projectSelect.onchange=()=>loadProject(projectSelect.value);
for(const t of document.querySelectorAll('.tab'))t.onclick=()=>{for(const x of document.querySelectorAll('.tab'))x.classList.toggle('active',x===t);for(const p of document.querySelectorAll('.panel'))p.classList.toggle('active',p.id===`panel-${t.dataset.tab}`);if(t.dataset.tab==='materials')updateMaterials();};
$('#doneLayer').onclick=()=>{if(!meta)return;const d=doneLayers();if(d.has(currentY))d.delete(currentY);else d.add(currentY);setDoneLayers(d);updateDoneButton();updateProgress();};
$('#importBtn').onclick=()=>$('#importInput').click();$('#importInput').onchange=()=>importFile($('#importInput').files[0]);
let importing=false;
async function importFile(f){if(!f||importing)return;if(!f.name.toLowerCase().endsWith('.litematic')){showToast('Bitte eine .litematic-Datei auswählen.');return;}if(f.size>100*1024*1024){showToast('Die Datei ist größer als 100 MB.');return;}importing=true;$('#importBtn').disabled=true;loading.classList.remove('hidden');loadingText.textContent=`${f.name} wird importiert …`;try{const r=await fetch(`/api/import-litematic?filename=${encodeURIComponent(f.name)}`,{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:f});const obj=await r.json();if(!r.ok||obj.error)throw new Error(obj.error||`HTTP ${r.status}`);showToast(`${obj.project.name} importiert: ${obj.project.blockCount.toLocaleString('de-DE')} Blöcke`);await refreshProjects(obj.project.slug);}catch(e){showToast(`Import fehlgeschlagen: ${e.message}`,6000);}finally{importing=false;$('#importBtn').disabled=false;$('#importInput').value='';loading.classList.add('hidden');loadingText.textContent='Bauwerk wird geladen …';}};
document.addEventListener('dragover',e=>{e.preventDefault();document.body.classList.add('dropActive');});
document.addEventListener('dragleave',e=>{if(!e.relatedTarget)document.body.classList.remove('dropActive');});
document.addEventListener('drop',e=>{e.preventDefault();document.body.classList.remove('dropActive');importFile(e.dataTransfer.files[0]);});
function showToast(msg,ms=3200){toast.textContent=msg;toast.classList.add('show');clearTimeout(showToast.t);showToast.t=setTimeout(()=>toast.classList.remove('show'),ms);}

refreshProjects().catch(e=>{loading.classList.add('hidden');showToast(`Startfehler: ${e.message}`,6000);console.error(e);});
