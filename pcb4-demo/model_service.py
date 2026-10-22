"""Loopback-only image inference. No network downloads or checkpoint fallback."""
import base64
import io
import json
import hashlib
import math
import time
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

RUN = Path('D:/Project/aiot-model/runs/visa-pcb4-20261022-213717')

class Predictor:
    def __init__(self):
        import torch
        from torchvision import transforms
        from anomalib.models.image.patchcore.torch_model import PatchcoreModel
        self.torch = torch
        torch.set_num_threads(4)
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        saved = torch.load(RUN/'model.pt', map_location='cpu', weights_only=True)
        self.model = PatchcoreModel(**saved['config'], pre_trained=False)
        self.model.load_state_dict(saved['state_dict'])
        self.model.to(self.device).eval()
        self.threshold = json.loads((RUN/'threshold.json').read_text())['threshold']
        assert math.isfinite(self.threshold) and self.threshold > 0
        self.version = hashlib.sha256((RUN/'model.pt').read_bytes()).hexdigest()[:16]
        self.transform = transforms.Compose([transforms.Resize((256,256)), transforms.ToTensor(),
            transforms.Normalize([.485,.456,.406],[.229,.224,.225])])

    def predict(self, raw):
        from PIL import Image
        import numpy as np
        if len(raw) > 5*1024*1024:
            raise ValueError('IMAGE_TOO_LARGE')
        with Image.open(io.BytesIO(raw)) as im:
            if im.width*im.height > 16_000_000 or im.format not in ('JPEG','PNG'):
                raise ValueError('IMAGE_FORMAT_OR_SIZE')
            im.load()
            display=im.convert('RGB')
            tensor = self.transform(display).unsqueeze(0).to(self.device)
            display.thumbnail((700,700))
        started = time.perf_counter()
        with self.torch.inference_mode():
            out = self.model(tensor)
            score = float(out.pred_score.item())
            heat = out.anomaly_map.squeeze().cpu().numpy()
        if not math.isfinite(score) or score < 0:
            raise RuntimeError('INVALID_MODEL_SCORE')
        # Display only: per-image min/max, never used for classification.
        h = (heat-heat.min()) / max(float(heat.max()-heat.min()), 1e-9)
        rgb = np.stack([h, .25*(1-h), 1-h], axis=-1)
        buf = io.BytesIO()
        Image.fromarray((rgb*255).astype('uint8')).save(buf, format='PNG')
        overlay=Image.blend(display,Image.fromarray((rgb*255).astype('uint8')).resize(display.size),.4)
        overlay_buffer=io.BytesIO()
        overlay.save(overlay_buffer,format='PNG')
        return {'raw_score': score, 'raw_threshold': self.threshold,
                'anomaly_score': score/(score+self.threshold), 'model_version': self.version,
                'image_sha256': hashlib.sha256(raw).hexdigest(), 'inference_ms': (time.perf_counter()-started)*1000,
                'heatmap': 'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode(),
                'overlay': 'data:image/png;base64,'+base64.b64encode(overlay_buffer.getvalue()).decode(),
                'device': self.device, 'simulated': False}

def create_server(predictor, store=None):
    if store is None:
        from storage import Store
        store=Store()
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(20)
        def send(self, code, payload):
            data = json.dumps(payload, allow_nan=False).encode()
            self.send_response(code)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        def do_GET(self):
            if self.path == '/alerts':
                try:
                    return self.send(200,store.snapshot())
                except Exception:
                    return self.send(500,{'code':'STORAGE_ERROR'})
            if self.path != '/health':
                return self.send(404, {'code':'NOT_FOUND'})
            self.send(200, {'ready':True, 'model_version':predictor.version,'device':predictor.device})
        def do_POST(self):
            if self.path not in ('/infer','/records','/ack'):
                return self.send(404, {'code':'NOT_FOUND'})
            try:
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 7*1024*1024:
                    return self.send(413, {'code':'BODY_TOO_LARGE'})
                data = json.loads(self.rfile.read(length))
                if self.path in ('/records','/ack'):
                    code, body=store.handle(self.path[1:],data)
                    return self.send(code,body)
                raw = base64.b64decode(data['image_base64'], validate=True)
                result = predictor.predict(raw)
                self.send(200,result)
            except (ValueError, KeyError, TypeError, OSError) as exc:
                self.send(422, {'status':'error','code':'INVALID_IMAGE','detail':str(exc)[:160]})
            except Exception:
                self.send(500, {'status':'error','code':'MODEL_OR_STORAGE_ERROR'})
    return HTTPServer(('127.0.0.1',1891),Handler)

if __name__ == '__main__':
    create_server(Predictor()).serve_forever()
