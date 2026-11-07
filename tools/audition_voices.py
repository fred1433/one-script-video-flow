import sys, soundfile as sf, numpy as np
from kokoro import KPipeline
text = ("This is a cartridge lock. A fictional one, built for this demo. "
        "At the bottom of the groove, a quarter turn carries the lug sideways, and behind a stop. One click, and it holds.")
pipe = KPipeline(lang_code="b")
for v in sys.argv[1:]:
    chunks = []
    for r in pipe(text, voice=v, speed=0.94):
        chunks.append(r.audio.numpy())
        if v == sys.argv[1]:
            print([(t.text, t.start_ts, t.end_ts) for t in r.tokens][:8])
    a = np.concatenate(chunks)
    sf.write(f"{v}.wav", a, 24000)
    print(v, round(len(a)/24000, 2), "s")
