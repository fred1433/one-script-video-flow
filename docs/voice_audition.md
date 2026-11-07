# Voice audition (Kokoro-82M, British voices)

The same two sentences were read by four British voices with `tools/audition_voices.py` (speed 0.94), then transcribed back with Whisper (small, English) to check that every word comes out.

Text: "This is a cartridge lock. A fictional one, built for this demo. At the bottom of the groove, a quarter turn carries the lug sideways, and behind a stop. One click, and it holds."

| Voice | Length | Grade in the model card (VOICES.md) | Whisper transcript |
|---|---|---|---|
| `bm_george` | 12.2 s | C | This is a cartridge lock, a fictional one built for this demo.
At the bottom of the groove, a quarter turn carries the lug sideways and behind a stop, one click and it holds. |
| `bf_emma` | 10.88 s | B- | This is a cartridge lock, a fictional one built for this demo.
At the bottom of the groove a quarter turn carries the lug sideways and behind a stop, one click and it holds. |
| `bm_fable` | 10.35 s | C | This is a cartridge lock, a fictional one built for this demo.
At the bottom of the groove a quarter turn carries the lug sideways and behind a stop.
One click and it holds. |
| `bm_daniel` | 10.18 s | D | This is a cartridge lock, a fictional one built for this demo.
At the bottom of the groove, a quarter turn carries the lug sideways and behind a stop,
one click and it holds. |

All four were transcribed word for word. `bf_emma` was kept: it has the highest overall grade of the British voices in the Kokoro model card (https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md). The choice was not made by ear; a person should listen to the master before it goes out.
