"""Run the distributed entry point with a fake executable, not mocked Python imports."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "case-lite-lark" / "scripts/feishu_docs.py"

FAKE = '''
import json,sys,pathlib,os
args=sys.argv[1:]
if args[:2]==['api','GET']:
    if args[2].endswith('/blocks'):
        if 'document_revision_id' in json.loads(args[args.index('--params')+1]):
            print(json.dumps({'ok':False,'error':{'code':1770032,'message':'forbidden'}}),file=sys.stderr);sys.exit(1)
        def block(i,t,k=2):
            key='text' if k==2 else 'heading1'
            return {'block_id':i,'block_type':k,key:{'elements':[{'text_run':{'content':t}}]}}
        data={'items':[block('h1','第一章',3),block('p1','原文 amount=100'),block('h2','第二章',3),block('p2','不应读取')],'has_more':False}
        if os.environ.get('FAKE_MEDIA'):
            def board(i):return {'block_id':i,'block_type':43,'board':{'token':i+'token'}}
            data['items'][2:2]=[board('board1'),board('board2'),{'block_id':'image','block_type':27,'image':{'token':'imagetoken'}}]
            data['items'].append(board('board3'))
    else:
        data={'document':{'document_id':'doc','title':'合成需求','revision_id':7}}
elif args[:2]==['markdown','+fetch']:
    data={'content':'# 第一章\\r\\n保留原文  \\r\\n# 第二章\\r\\n不应读取\\r\\n'}
elif args[:2] in (['whiteboard','+export'],['docs','+media-preview']):
    output=pathlib.Path(args[args.index('--output')+1])
    suffix='.jpg' if args[0]=='whiteboard' else '.png'
    if output.suffix and output.suffix!=suffix:
        print(json.dumps({'ok':False,'error':{'type':'validation','subtype':'failed_precondition','message':'preview response is .jpg but output path has extension .png'}}),file=sys.stderr);sys.exit(1)
    saved=output.with_suffix(suffix)
    saved.write_bytes(b'fake-image')
    data={'preview_image_path' if args[0]=='whiteboard' else 'saved_path':str(saved)}
else:
    print(json.dumps({'ok':False,'error':{'message':'unexpected command'}}),file=sys.stderr);sys.exit(1)
assert '--as' in args and args[args.index('--as')+1]=='user'
print(json.dumps({'ok':True,'identity':'user','data':data}))
'''


class ProcessTest(unittest.TestCase):
    def test_three_jpeg_boards_and_image_are_read_with_consistent_paths_on_rerun(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            binary = root / "bin/lark-cli"
            binary.parent.mkdir()
            binary.write_text(f"#!{sys.executable}\n" + FAKE)
            binary.chmod(0o755)
            env = dict(os.environ, PATH=str(binary.parent) + os.pathsep + os.environ.get("PATH", ""), FAKE_MEDIA="1")
            base = [sys.executable, "-B", str(SCRIPT)]
            outline = subprocess.run(base + ["outline", "https://example.feishu.cn/docx/doc", "--output", "outline.json"], cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(outline.returncode, 0, outline.stderr)
            previous = None
            for _ in range(2):
                read = subprocess.run(base + ["read", "--outline-file", "outline.json", "--section-id", "h1", "h2", "--output-dir", "out", "--doc-key", "01-doc"], cwd=root, env=env, capture_output=True, text=True)
                self.assertEqual(read.returncode, 0, read.stderr)
                data = json.loads(read.stdout)["data"]
                self.assertEqual(data["status"], "complete")
                manifest = json.loads(Path(data["manifest_path"]).read_text())
                self.assertEqual(len(manifest["media"]), 4)
                corpus = Path(data["corpus_path"]).read_text()
                self.assertEqual(corpus.count("<!-- SOURCE:"), 2)
                for media in manifest["media"]:
                    path = Path(media["path"])
                    self.assertTrue(path.is_file())
                    self.assertEqual(path.suffix, ".jpg" if media["media_type"] == "board" else ".png")
                    self.assertEqual(media["expected_filename"], path.name)
                    self.assertEqual(media["expected_path"], str(path.relative_to(root / "out")))
                    self.assertIn(media["expected_path"], corpus)
                if previous is not None:
                    self.assertEqual((corpus, manifest), previous)
                previous = corpus, manifest

    def test_standalone_subprocess_selection_and_error_contract(self):
        for kind, section in [("docx", "h1"), ("file", "1")]:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                binary = root / "bin/lark-cli"
                binary.parent.mkdir()
                binary.write_text(f"#!{sys.executable}\n" + FAKE)
                binary.chmod(0o755)
                env = dict(os.environ, PATH=str(binary.parent) + os.pathsep + os.environ.get("PATH", ""))
                base = [sys.executable, "-B", str(SCRIPT)]
                outline = subprocess.run(base + ["outline", f"https://example.feishu.cn/{kind}/doc", "--output", "outline.json"], cwd=root, env=env, capture_output=True, text=True)
                self.assertEqual(outline.returncode, 0, outline.stderr)
                self.assertNotIn("amount=100", outline.stdout)
                read = subprocess.run(base + ["read", "--outline-file", "outline.json", "--section-id", section, "--output-dir", "out", "--doc-key", "01-doc"], cwd=root, env=env, capture_output=True, text=True)
                self.assertEqual(read.returncode, 0, read.stderr)
                result = json.loads(read.stdout)
                corpus = Path(result["data"]["corpus_path"]).read_bytes()
                self.assertIn("原文".encode(), corpus)
                self.assertNotIn("不应读取".encode(), corpus)
                if kind == "file":
                    self.assertIn(b"  \r\n", corpus)
                failed = subprocess.run(base + ["read", "--outline-file", "outline.json", "--section-id", "missing", "--output-dir", "out", "--doc-key", "01-doc"], cwd=root, env=env, capture_output=True, text=True)
                self.assertEqual(failed.returncode, 1)
                self.assertEqual(failed.stdout, "")
                self.assertFalse(json.loads(failed.stderr)["ok"])
                self.assertEqual(Path(result["data"]["corpus_path"]).read_bytes(), corpus)


if __name__ == "__main__":
    unittest.main()
