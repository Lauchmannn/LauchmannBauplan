"""Optional Playwright integration test using only isolated synthetic data."""
from pathlib import Path
import shutil
import sys
import os
import struct
import zlib
import zipfile
import tempfile
import threading
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
from fixtures import schematic, region
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory(prefix='bauplan-browser-') as td:
        server.ROOT = Path(td)
        shutil.copytree(Path(__file__).resolve().parents[1] / 'app', server.ROOT / 'app')
        # Original synthetic PNG verifies the actual local-JAR decoding path.
        def png_chunk(kind, data):
            return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
        png=b'\x89PNG\r\n\x1a\n'+png_chunk(b'IHDR',struct.pack('>IIBBBBB',16,16,8,2,0,0,0))+png_chunk(b'IDAT',zlib.compress((b'\0'+bytes([128,128,128])*16)*16))+png_chunk(b'IEND',b'')
        jar=server.ROOT/'synthetic-textures.jar'
        with zipfile.ZipFile(jar,'w') as z:z.writestr('assets/minecraft/textures/block/stone.png',png)
        old=os.environ.get('MINECRAFT_JAR');os.environ['MINECRAFT_JAR']=str(jar)
        server.TEXTURES=server.TextureLibrary()
        if old is None:os.environ.pop('MINECRAFT_JAR')
        else:os.environ['MINECRAFT_JAR']=old
        http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        server.PORT = http.server_port
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as p:
                options = dict(headless=True, args=['--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
                if shutil.which('chromium'):
                    options['executable_path'] = shutil.which('chromium')
                browser = p.chromium.launch(**options)
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{http.server_port}/')
                page.wait_for_selector('#loading.hidden', state='attached')
                palette = [('minecraft:stone', {}), ('minecraft:oak_stairs', {'facing': 'east', 'half': 'bottom', 'shape': 'inner_left'}), ('minecraft:oak_slab', {'type': 'top'}), ('minecraft:oak_fence', {'north': 'true', 'east': 'true'}), ('minecraft:cobblestone_wall', {'north': 'low', 'east': 'tall', 'up': 'true'}), ('minecraft:glass_pane', {'north': 'true', 'south': 'true'}), ('minecraft:oak_door', {'facing': 'north', 'half': 'lower', 'open': 'true', 'hinge': 'left'}), ('minecraft:oak_trapdoor', {'facing': 'east', 'open': 'true'}), ('minecraft:cactus', {}), ('minecraft:hopper', {'facing': 'down'}), ('minecraft:lantern', {'hanging': 'true'})]
                regions = b''.join(region('r'+str(i), position=((i % 6)*2, i//6*2, 0), palette=[state]) for i, state in enumerate(palette))
                data = schematic(regions, name='Browser models')
                page.locator('#importInput').set_input_files({'name': 'models.litematic', 'mimeType': 'application/octet-stream', 'buffer': data})
                page.wait_for_function("meta && meta.name==='Browser models' && meshes.length>0")
                page.wait_for_selector('#loading.hidden', state='attached')
                assert page.evaluate('gl.getError()') == 0
                assert page.evaluate('instanceCount') == 11
                assert page.locator('#textureStatus').inner_text().startswith('1 lokale Minecraft-Texturen')
                # Y increases upward on screen, including in the real view-projection.
                assert page.evaluate('''()=>{const m=viewProjection(),c=centerVec();function sy(y){const p=[-c[0],y-c[1],-c[2],1];return -(m[1]*p[0]+m[5]*p[1]+m[9]*p[2]+m[13])/(m[3]*p[0]+m[7]*p[1]+m[11]*p[2]+m[15]);}return sy(2)<sy(0);}''')
                page.locator('#viewTop').click()
                page.locator('[data-mode=layer]').click()
                page.locator('#yPlus').click(); page.locator('#yPlus').click()
                page.wait_for_function('currentY===2 && currentLayerRecords.length===20 && instanceCount===5')
                page.locator('[data-tab=materials]').click()
                assert '5 Blöcke' in page.locator('#materialSummary').inner_text()
                page.locator('#materialScope').select_option('all')
                assert '11 Blöcke' in page.locator('#materialSummary').inner_text()
                page.locator('#doneLayer').click()
                page.reload(); page.wait_for_function('meta && meshes.length>0')
                page.wait_for_selector('#loading.hidden', state='attached')
                assert page.locator('#progressText').inner_text().startswith('50 %')
                page.locator('#view3d').click()
                point = page.evaluate('''()=>{const m=viewProjection(),c=centerVec(),p=[-c[0],-c[1],-c[2],1];const clip=[0,1,2,3].map(r=>m[r]*p[0]+m[4+r]*p[1]+m[8+r]*p[2]+m[12+r]);const r=canvas.getBoundingClientRect();return {x:r.left+(clip[0]/clip[3]+1)*r.width/2,y:r.top+(1-clip[1]/clip[3])*r.height/2};}''')
                page.mouse.click(point['x'], point['y']); page.wait_for_selector('#blockInfo:visible')
                assert page.locator('#blockId').inner_text() == 'minecraft:stone'
                assert page.locator('#blockCoord').inner_text() == 'X 0 · Y 0 · Z 0'
                # Cut includes every block of the selected level, then rapid changes settle on newest Y.
                page.locator('[data-mode=cut]').click()
                page.wait_for_function('instanceCount===6')
                page.evaluate('setY(2);setY(0);setY(2)')
                page.wait_for_function('currentY===2 && instanceCount===11')
                # Real worker: 100,000 cubes -> 24,000 exposed faces, rather than 600,000.
                result = page.evaluate('''()=>new Promise((resolve,reject)=>{const records=new Uint16Array(100000*4);let i=0;for(let y=0;y<10;y++)for(let z=0;z<100;z++)for(let x=0;x<100;x++)records.set([x,y,z,0],4*i++);const w=new Worker('/app/mesh-worker.js');const start=performance.now();let vertices=0;w.onmessage=({data})=>{if(data.vertices)vertices+=data.vertices.byteLength/52;if(data.error){w.terminate();reject(Error(data.error));}if(data.done){w.terminate();resolve({faces:data.count,vertices,ms:Math.round(performance.now()-start)});}};w.onerror=e=>reject(Error(e.message));w.postMessage({records:records.buffer,palette:[{name:'minecraft:stone'}],colors:[[.5,.5,.5]],tiles:[[0,0,0]]},[records.buffer]);})''')
                assert result['faces'] == 24000 and result['vertices'] == 144000, result
                print('Worker performance:', result, flush=True)
                # Drag-and-drop uses the same import path, with real in-memory File bytes.
                dropped = schematic(region(size=(65,1,65)),name='Dropped fixture')
                page.evaluate('''bytes=>{const dt=new DataTransfer();dt.items.add(new File([new Uint8Array(bytes)],'dropped.litematic'));document.dispatchEvent(new DragEvent('drop',{bubbles:true,dataTransfer:dt}));}''', list(dropped))
                page.wait_for_function("meta && meta.name==='Dropped fixture' && instanceCount===4225 && meshJob===null")
                page.wait_for_selector('#loading.hidden', state='attached')
                page.wait_for_timeout(200)
                idle = page.evaluate('''()=>new Promise(resolve=>{let count=0;const original=render;render=()=>{count++;original();};setTimeout(()=>{render=original;resolve(count);},300);})''')
                assert idle == 0, idle
                assert not errors, errors
                browser.close()
                print('PASS: WebGL/model rendering, Y-up, file/drop import, GPU picking, views, layers/cuts, materials, persistent progress, worker meshing and idle rendering.')
        finally:
            http.shutdown(); http.server_close(); thread.join()


if __name__ == '__main__':
    main()
