'use strict';
const assert=require('node:assert/strict');
const {model,opaque,mesh}=require('../app/models.js');
const state=(name,properties={})=>({name:'minecraft:'+name,properties});
const stone=state('stone');
assert(opaque(stone));assert(!opaque(state('glass')));
assert.deepEqual(model(state('oak_slab',{type:'top'})),[[0,.5,0,1,1,1]]);
assert(opaque(state('oak_slab',{type:'double'})));
for(const name of ['oak_stairs','oak_fence','cobblestone_wall','glass_pane','oak_door','oak_trapdoor','cactus','hopper','lantern']) {
 const boxes=model(state(name,{north:'true',up:'true'}));assert(boxes.length>0);
 assert(!opaque(state(name)));assert(boxes.every(b=>b.every(v=>v>=0&&v<=1)));
}
assert.notDeepEqual(model(state('oak_stairs',{facing:'east'})),model(state('oak_stairs',{facing:'north'})));
assert.notDeepEqual(model(state('oak_door',{open:'true'})),model(state('oak_door',{open:'false'})));
assert.equal(model(state('oak_stairs',{shape:'inner_left'})).length,3);
const vertices=[];
const faces=mesh(new Uint16Array([0,0,0,0,1,0,0,0]),[stone],[[1,1,1]],[[0,0,0]],v=>vertices.push(v));
assert.equal(faces,10);assert.equal(vertices.reduce((s,v)=>s+v.length/13,0),60);
assert.equal(mesh(new Uint16Array([0,0,0,0,1,0,0,1]),[stone,state('oak_slab')],[[1,1,1],[1,1,1]],[[0,0,0],[1,1,1]],()=>{}),11);
assert.equal(mesh(new Uint16Array([0,0,0,0]),[stone],[[1,1,1]],[[0,0,0]],()=>{}),6);
console.log('PASS: model bounds, slab halves, facing/open states, stair shapes, opaque-neighbor face culling and mesh vertex counts');
