import io
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from PIL import Image
import app
import engine as e
import tasks
from models import example


class IntakeTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        m=patch.object(e,"HOME",Path(temp.name));m.start();self.addCleanup(m.stop)
        g=patch("gateway.profile",return_value={});g.start();self.addCleanup(g.stop)
        self.s=e.create("汇报","","")

    def test_input_payload(self):
        e.update_brief(self.s,dict(audience="院领导",brief="决定试点",content="试点是规划工作",requirements="三页，先结论"))
        e.ingest(self.s,"现场.txt","旧数据".encode());old=self.s["sources"][-1]["id"]
        e.remove_material(self.s,old);e.ingest(self.s,"现场.txt","新数据".encode())
        self.assertNotEqual(old,self.s["sources"][-1]["id"])
        review=e.approvals.review(self.s,"brief")
        e.action(self.s,"approve",dict(checkpoint="brief",code=review["review_code"],user_reply="确认。"))
        with patch("providers.ask",return_value=example()) as ask:
            e.action(self.s,"outline",{});payload=ask.call_args.args[2]
        self.assertEqual([payload[k] for k in ("brief","audience","requirements")],["决定试点","院领导","三页，先结论"])
        self.assertEqual([x["text"] for x in payload["sources"]],["试点是规划工作","新数据"])

    def test_delete_image_copy(self):
        raw=io.BytesIO();Image.new("RGB",(3,3)).save(raw,"PNG");e.ingest(self.s,"图.png",raw.getvalue())
        asset=self.s["assets"][0];path=e.root(self.s)/asset["file"]
        self.assertTrue(path.exists());e.remove_material(self.s,asset["id"])
        self.assertFalse(path.exists());self.assertFalse(e.get(self.s["id"])["assets"])

    def test_pause_resume(self):
        started=threading.Event();release=threading.Event();second=threading.Event()
        @tasks.remote
        def first():started.set();release.wait(5)
        @tasks.remote
        def next_call():second.set()
        def fake(*_):first();next_call()
        id=self.s["id"];url=f"/api/projects/{id}/task"
        with TestClient(app.app,headers={"X-Studio-Token":app.token}) as c,patch.object(e,"action",side_effect=fake),patch("providers.configured",return_value=True):
            j=c.post(url+"/start",json={"op":"outline","updated":self.s["updated"]}).json();self.assertTrue(started.wait(2))
            self.assertEqual(c.post(url+"/pause",json=j).json()["status"],"pausing");release.set()
            for _ in range(100):
                if c.get(url).json()["status"]=="paused":break
                time.sleep(.01)
            self.assertEqual(c.get(url).json()["status"],"paused");self.assertFalse(second.is_set())
            self.assertEqual(c.post(f"/api/projects/{id}/save_brief",json={}).status_code,409)
            c.post(url+"/resume",json=j);self.assertTrue(second.wait(2))

    def test_two_design_requests_can_overlap(self):
        self.s["plan"]=example();gate=threading.Barrier(2);lock=threading.Lock();peaks=[];active=0
        def fake(*args,**kw):
            nonlocal active
            with lock:active+=1;peaks.append(active)
            gate.wait(timeout=3)
            with lock:active-=1
            return {k:k+"_内容" for k in e.art_direction.FIELDS}
        with patch("providers.ask",side_effect=fake):
            e.art_direction.generate(self.s,e.root(self.s))
        self.assertEqual(max(peaks),2);self.assertEqual(len(self.s["directions"]),4)
