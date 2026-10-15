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

import server
from textures import TextureLibrary
from fixtures import schematic


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


if __name__=='__main__':unittest.main()
