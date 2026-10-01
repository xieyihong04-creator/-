"""PP-OCRv5-server subtitle OCR on burned-in subs (white text, dark bg)."""
import os, sys
import numpy as np, onnxruntime as ot
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import OCR_SERVER, OCR_DICT

class Rec:
    def __init__(self, path=OCR_SERVER,
                 dictpath=OCR_DICT, threads=4):
        so=ot.SessionOptions(); so.intra_op_num_threads=threads; so.inter_op_num_threads=1
        self.s=ot.InferenceSession(path, sess_options=so, providers=['CPUExecutionProvider'])
        self.iname=self.s.get_inputs()[0].name
        d=[l.rstrip('\n') for l in open(dictpath, encoding='utf-8')]
        self.chars=[' ']+d          # PaddleOCR: index0=blank, index1=space, then dict
    def batch(self, imgs, maxw=1280):
        """imgs: list of uint8 HxW crops -> list of (text, conf)."""
        if not imgs: return []
        prep=[]
        for img in imgs:
            h,w=img.shape
            if h<6 or w<8: prep.append(None); continue
            nh=48; nw=min(maxw, max(16, int(round(w*nh/h))))
            g=np.asarray(Image.fromarray(img, mode='L').resize((nw,nh), Image.BILINEAR), dtype=np.float32)
            prep.append(g)
        valid=[i for i,p in enumerate(prep) if p is not None]
        if not valid: return [('',0.0)]*len(imgs)
        W=max(prep[i].shape[1] for i in valid)
        x=np.zeros((len(valid),3,48,W), np.float32)
        for j,i in enumerate(valid):
            g=(prep[i]/255.0-0.5)/0.5
            x[j,:,:,:g.shape[1]]=np.stack([g,g,g])
        out=self.s.run(None, {self.iname: np.ascontiguousarray(x)})[0]
        res=[('',0.0)]*len(imgs)
        for j,i in enumerate(valid):
            o=out[j]; idx=o.argmax(1); conf=o.max(1)
            ch=[]; cs=[]
            for k,v in enumerate(idx):
                if v==0: continue
                if k>0 and v==idx[k-1]: continue
                if v<len(self.chars): ch.append(self.chars[v]); cs.append(float(conf[k]))
            res[i]=(''.join(ch), float(np.mean(cs)) if cs else 0.0)
        return res

    def __call__(self, img, maxw=1600):
        """img: uint8 grayscale crop of one subtitle line."""
        h,w=img.shape
        if h<6 or w<8: return '', 0.0
        nh=48; nw=min(maxw, max(16, int(round(w*nh/h))))
        g=np.asarray(Image.fromarray(img, mode='L').resize((nw,nh), Image.BILINEAR), dtype=np.float32)
        x=(g/255.0-0.5)/0.5
        x=np.ascontiguousarray(np.stack([x,x,x])[None])
        out=self.s.run(None, {self.iname: x})[0][0]
        idx=out.argmax(1); conf=out.max(1)
        chars=[]; cs=[]
        for i,v in enumerate(idx):
            if v==0: continue
            if i>0 and v==idx[i-1]: continue
            if v < len(self.chars):
                chars.append(self.chars[v]); cs.append(float(conf[i]))
        return ''.join(chars), (float(np.mean(cs)) if cs else 0.0)

def find_rows(y, x0=20, x1=620, y0=300, y1=478, thr=170, min_px=10, min_h=11):
    """Vectorised: locate bright-text rows in the subtitle band."""
    m = y[y0:y1, x0:x1] > thr
    prof = m.sum(1)
    on = prof > min_px
    if not on.any(): return []
    idx = np.flatnonzero(on)
    breaks = np.flatnonzero(np.diff(idx) > 1)
    starts = np.r_[idx[0], idx[breaks + 1]]
    ends = np.r_[idx[breaks], idx[-1]]
    rows = [(y0 + max(0, a - 3), y0 + b + 4) for a, b in zip(starts, ends) if b - a >= min_h]
    out = []
    for r in rows:
        if out and r[0] - out[-1][1] < 4: out[-1] = (out[-1][0], r[1])
        else: out.append(r)
    return [(a, b) for a, b in out if 12 <= b - a <= 60]

def line_boxes(y, ra, rb, x0=20, x1=620, thr=170):
    """Split a row band into left/right text segments (for 2-column or wide subs)."""
    m=(y[ra:rb, x0:x1]>thr).sum(0)
    cols=np.where(m>0)[0]
    if len(cols)==0: return []
    segs=[]; s=cols[0]; p=cols[0]
    for c in cols[1:]:
        if c-p>25: segs.append((s,p)); s=c
        p=c
    segs.append((s,p))
    return [(x0+a-2, x0+b+3) for a,b in segs if b-a>10]
