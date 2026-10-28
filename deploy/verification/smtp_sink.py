"""Local-only SMTP verification fixture. Never use as an institutional relay."""
import os
import signal
import ssl
import threading
import time
import uuid
from pathlib import Path
from aiosmtpd.controller import Controller

if os.environ.get('FINDIT_TEST_SMTP') != '1':
    raise SystemExit('This SMTP sink may only run in an explicit synthetic verification stack')

sink=Path(os.environ['FINDIT_TEST_MAIL_DIRECTORY'])
sink.mkdir(parents=True,exist_ok=True)
os.umask(0o077)

class Handler:
    async def handle_DATA(self,server,session,envelope):
        (sink/f'{time.time_ns():020d}-{uuid.uuid4().hex}.eml').write_bytes(envelope.original_content)
        return '250 Stored in private test sink'

context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain('/test-cert.crt','/test-key.pem')
controller=Controller(Handler(),hostname='0.0.0.0',port=1025,tls_context=context,require_starttls=True)
controller.start()
stopped=threading.Event()
for signum in (signal.SIGINT,signal.SIGTERM):
    signal.signal(signum,lambda *_:stopped.set())
stopped.wait()
controller.stop()
