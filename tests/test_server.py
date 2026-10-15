import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
import zipfile
import struct

import server
from textures import TextureLibrary
from fixtures import schematic, region


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'app').mkdir();(self.root/'app/index.html').write_text('Lauchmann Bauplan')
        self.patch=patch.object(server,'ROOT',self.root);self.patch.start()
        self.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{self.http.server_port}'

    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join();self.patch.stop();self.tmp.cleanup()

    def request(self,path,data=None,headers=None):
        with urlopen(Request(self.base+path,data=data,headers=headers or {}),timeout=5) as r:
            return r.status,r.read()

    def test_import_reimport_and_same_title_different_content(self):
        data=schematic()
        first=json.loads(self.request('/api/import-litematic?filename=demo.litematic',data)[1])
        again=json.loads(self.request('/api/import-litematic?filename=demo.litematic',data)[1])
        self.assertEqual(first,again)
        second=json.loads(self.request('/api/import-litematic?filename=other.litematic',data)[1])
        self.assertNotEqual(first['project']['slug'],second['project']['slug'])
        projects=json.loads(self.request('/api/projects')[1]);self.assertEqual(len(projects),2)
        slug=first['project']['slug']
        meta=json.loads(self.request('/projects/'+slug+'/metadata.json')[1])
        self.assertEqual(meta['materials'][0]['name'],'minecraft:stone')
        self.assertEqual(len(self.request('/projects/'+slug+'/surface.bin')[1]),8)
        self.assertEqual(len(self.request('/projects/'+slug+'/layers/y0000.bin')[1]),6)

    def test_invalid_upload_does_not_persist_and_origin_guard(self):
        for data,headers,code in [(b'bad',{},400),(b'',{},400),(schematic(),{'Origin':'https://example.com'},403)]:
            with self.assertRaises(HTTPError) as e:self.request('/api/import-litematic',data,headers)
            self.assertEqual(e.exception.code,code)
        self.assertEqual(list((self.root/'schematics').glob('*')),[])

    def test_private_files_and_directory_listing_not_served(self):
        (self.root/'.git').mkdir();(self.root/'.git/config').write_text('private')
        for path in ['/.git/config','/server.py','/app/','/projects/../.git/config','/schematics/demo.litematic']:
            with self.assertRaises(HTTPError) as e:self.request(path)
            self.assertEqual(e.exception.code,404)
        self.assertEqual(self.request('/')[0],200)

    def test_optional_local_texture_jar_is_read_only(self):
        jar=self.root/'minecraft.jar'
        with zipfile.ZipFile(jar,'w') as z:z.writestr('assets/minecraft/textures/block/stone.png',b'example-png')
        original=jar.read_bytes()
        with patch.dict('os.environ',{'MINECRAFT_JAR':str(jar)}):lib=TextureLibrary()
        with patch.object(server,'TEXTURES',lib):
            self.assertEqual(json.loads(self.request('/api/textures')[1])['names'],['stone'])
            self.assertEqual(self.request('/api/texture?name=stone')[1],b'example-png')
            with self.assertRaises(HTTPError):self.request('/api/texture?name=../../.git/config')
        self.assertEqual(jar.read_bytes(),original)

    def test_legacy_upside_down_project_is_refreshed_from_original(self):
        from litematic import convert_litematic, CONVERTER_VERSION
        source=self.root/'schematics'/'legacy.litematic'
        source.parent.mkdir()
        source.write_bytes(schematic(region(size=(1,-2,1),position=(0,10,0),palette=[('minecraft:stone',{}),('minecraft:gold_block',{})],states=[0,1])))
        original=source.read_bytes()
        meta=convert_litematic(source,self.root/'projects',preferred_slug='legacy')
        project=self.root/'projects'/'legacy'
        meta.pop('converterVersion')
        (project/'metadata.json').write_text(json.dumps(meta))
        # Simulate the old converter: gold at the bottom, stone at the top.
        (project/'surface.bin').write_bytes(struct.pack('<8H',0,0,0,0,0,1,0,1))
        (project/'local-note.txt').write_text('Preserve local files')
        response=json.loads(self.request('/projects/legacy/metadata.json')[1])
        self.assertEqual(response['converterVersion'],CONVERTER_VERSION)
        self.assertEqual(response['slug'],'legacy')
        self.assertEqual(response['originalBounds']['minY'],9)
        # Stone belongs at Y=9; gold belongs at Y=10, matching Litematica.
        self.assertEqual(self.request('/projects/legacy/surface.bin')[1],struct.pack('<8H',0,0,0,1,0,1,0,0))
        self.assertEqual(self.request('/projects/legacy/layers/y0000.bin')[1],struct.pack('<3H',0,0,1))
        self.assertEqual(self.request('/projects/legacy/layers/y0001.bin')[1],struct.pack('<3H',0,0,0))
        self.assertEqual(source.read_bytes(),original)
        self.assertEqual((project/'local-note.txt').read_text(),'Preserve local files')
        self.assertEqual(json.loads(self.request('/projects/legacy/metadata.json')[1]),response)

    def test_legacy_without_original_requests_reimport_instead_of_guessing(self):
        project=self.root/'projects'/'legacy';project.mkdir(parents=True)
        (project/'metadata.json').write_text(json.dumps({'slug':'legacy','sourceFile':'missing.litematic'}))
        (project/'surface.bin').write_bytes(b'unchanged')
        response=json.loads(self.request('/projects/legacy/metadata.json')[1])
        self.assertTrue(response['needsReimport'])
        self.assertEqual((project/'surface.bin').read_bytes(),b'unchanged')


if __name__=='__main__':unittest.main()
