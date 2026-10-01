"""English narration transcript via faster-whisper, written to out/<name>.en.json.

distil-large-v3 is used instead of large-v3: on this CPU-only box large-v3 runs at
RTF ~2.1 and hallucinates on silent passages, while distil-large-v3 tracks the same
text at RTF ~1.0. The model is loaded once and reused for both episodes — loading it
inside the loop was what tripped the OOM killer before.
"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import ASR_MODEL, MEDIA, OUT

from faster_whisper import WhisperModel

os.makedirs(OUT, exist_ok=True)
model = WhisperModel(ASR_MODEL, device='cpu', compute_type='int8', cpu_threads=2)

for name in sys.argv[1:] or ['xia', 'shang']:
    dst = os.path.join(OUT, f'{name}.en.json')
    st = time.time()
    segs, _ = model.transcribe(
        os.path.join(MEDIA, f'{name}.mp4'), language='en',
        vad_filter=True, vad_parameters=dict(min_silence_duration_ms=400),
        beam_size=1, condition_on_previous_text=True,
        initial_prompt='National Geographic documentary narration about the human body.')
    out = [{'s': round(s.start, 2), 'e': round(s.end, 2), 't': s.text.strip()} for s in segs]
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{name} EN: {len(out)} segs in {time.time()-st:.0f}s', flush=True)
