"""Shared paths. Everything is resolved relative to the repo root so the pipeline
runs from any checkout; set HM_ROOT to override (e.g. to keep big model/video files
outside the git tree)."""
import os


def _find_root():
    """Walk up from this file until a directory holding models/ocr/rec.onnx appears.
    Works both as a flat working copy and as pipeline/ inside the repo."""
    here = os.path.dirname(os.path.abspath(__file__))
    d = here
    for _ in range(4):
        if os.path.exists(os.path.join(d, 'models', 'ocr', 'rec.onnx')):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return os.path.dirname(here)          # repo layout: pipeline/ -> repo root


ROOT = os.environ.get('HM_ROOT', _find_root())

MEDIA = os.path.join(ROOT, 'media')
OUT = os.path.join(ROOT, 'out')
DIST = os.path.join(ROOT, 'dist')
MODELS = os.path.join(ROOT, 'models')

OCR_MOBILE = os.path.join(MODELS, 'ocr', 'rec_mobile.onnx')
OCR_SERVER = os.path.join(MODELS, 'ocr', 'rec.onnx')
OCR_DICT = os.path.join(MODELS, 'ocr', 'dict.txt')
ASR_MODEL = os.path.join(MODELS, 'distil-v3')


def syspath():
    """Make the sibling pipeline modules importable when running scripts directly."""
    if ROOT not in os.sys.path:
        os.sys.path.insert(0, os.path.join(ROOT, 'pipeline'))
