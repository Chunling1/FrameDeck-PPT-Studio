"""Cooperative, project-scoped tasks. Issued HTTP calls are never replayed on resume."""
import contextvars
import threading
import time
import uuid
from contextlib import contextmanager
from functools import wraps

current=contextvars.ContextVar("studio_task",default=None)


class Task:
    def __init__(self,op):
        self.id=uuid.uuid4().hex
        self.op=op
        self.cv=threading.Condition()
        self.pausing=False
        self.terminal=None
        self.rewind=None
        self.target=None
        self.inflight=0
        self.done=self.total=0
        self.error=""
        self.started=time.time()

    def snapshot(self):
        with self.cv:
            status=self.terminal or ("returning" if self.rewind else ("pausing" if self.inflight else "paused") if self.pausing else "running")
            return dict(id=self.id,op=self.op,status=status,target=self.target,inflight=self.inflight,done=self.done,total=self.total,error=self.error,started=self.started)

    def control(self,pause):
        with self.cv:
            if not self.terminal and not self.rewind:self.pausing=pause
            self.cv.notify_all()
            return self.snapshot()

    def wait(self):
        with self.cv:
            self.cv.wait_for(lambda:not self.pausing or self.rewind)
            if self.rewind:raise ValueError("已停止，正在返回")

    def return_to(self,target,fn):
        with self.cv:
            if self.terminal or self.rewind:raise ValueError("任务状态已变更，请刷新后返回")
            self.target,self.rewind=target,fn
            self.cv.notify_all()
            return self.snapshot()

    def progress(self,n=0,total=None):
        with self.cv:
            self.done+=n
            if total is not None:self.total=total

    def execute(self,fn):
        token=current.set(self)
        error=None
        try:
            self.wait();fn()
        except Exception as exc:
            error=exc
        finally:current.reset(token)
        with self.cv:
            if self.rewind:
                try:self.rewind();error=None
                except Exception as exc:error=exc
                self.rewind=None
            self.terminal="failed" if error else "done"
            if error:self.error=str(error)[:1200] if isinstance(error,ValueError) else "任务执行失败，请检查服务配置或重试"


def checkpoint():
    t=current.get()
    if t:t.wait()


def remote(fn):
    @wraps(fn)
    def wrapped(*a,**kw):
        t=current.get()
        if not t:return fn(*a,**kw)
        with t.cv:
            t.wait();t.inflight+=1
        try:return fn(*a,**kw)
        finally:
            with t.cv:t.inflight-=1
            t.wait()
    return wrapped
