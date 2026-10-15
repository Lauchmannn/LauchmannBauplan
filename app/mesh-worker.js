'use strict';
importScripts('/app/models.js');
onmessage = ({data}) => {
 try {
   const count=BlockModels.mesh(new Uint16Array(data.records),data.palette,data.colors,data.tiles,vertices=>postMessage({vertices:vertices.buffer},[vertices.buffer]));
   postMessage({done:true,count});
 }catch(error){postMessage({error:String(error.message||error)});}
};
