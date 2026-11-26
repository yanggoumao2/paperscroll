"""Sound for the promo: synthesised music bed + sound effects (all generated here, no samples) mixed with the
voice-over clips at the timeline positions. Writes audio/mix.wav (48 kHz stereo)."""
import json
import subprocess
import wave
from pathlib import Path

import numpy as np

D = Path(__file__).parent
A = D / "audio"
SR = 48000
TL = json.loads((D / "timeline.json").read_text(encoding="utf-8"))
SC = {s["id"]: s for s in TL["scenes"]}
N = int((TL["total"] + 0.5) * SR)
rng = np.random.default_rng(7)


def t_(sec):
    return np.arange(int(sec * SR)) / SR


def env(n, a=0.005, r=0.2, sus=None):
    """attack / exponential release envelope of n samples."""
    x = np.arange(n) / SR
    e = np.minimum(1, x / max(a, 1e-4)) * np.exp(-x / max(r, 1e-4))
    return e


def lowpass(x, cutoff):
    # one-pole low-pass, vectorised enough for short sounds
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x); acc = 0.0
    for i, v in enumerate(x):
        acc = (1 - a) * v + a * acc; y[i] = acc
    return y


def place(buf, snd, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    if i >= len(buf): return
    snd = snd[: len(buf) - i]
    l, r = gain * (1 - max(0, pan)), gain * (1 + min(0, pan))
    buf[i:i + len(snd), 0] += snd * l
    buf[i:i + len(snd), 1] += snd * r


# ---------------------------------------------------------------- sound effects
def whoosh(dur=0.45, up=True, bright=1.0):
    """air whoosh: noise through a low-pass whose cutoff sweeps 250 Hz -> ~2.8 kHz (or back), soft envelope."""
    n = int(dur * SR); x = np.arange(n) / n
    noise = rng.standard_normal(n)
    sweep = (x if up else 1 - x)
    cut = 250 + 2600 * bright * np.sin(np.pi * 0.5 * sweep) ** 2
    a = np.exp(-2 * np.pi * cut / SR)
    y = np.empty(n); acc = 0.0; acc2 = 0.0
    for i in range(n):
        acc = (1 - a[i]) * noise[i] + a[i] * acc
        acc2 = (1 - a[i]) * acc + a[i] * acc2          # two poles: smoother, less hiss
        y[i] = acc2
    e = np.sin(np.pi * x) ** 2
    return 0.55 * y * e


def thump(f0=62, dur=0.6, click=0.5):
    t = t_(dur)
    body = np.sin(2 * np.pi * (f0 + 70 * np.exp(-t * 30)) * t) * np.exp(-t * 7)
    n = rng.standard_normal(len(t)) * np.exp(-t * 60) * click
    return 0.9 * (body + lowpass(n, 2500))


def tick(f=2400, dur=0.03):
    t = t_(dur)
    return 0.25 * np.sin(2 * np.pi * f * t) * np.exp(-t * 180)


def pop(dur=0.25):
    t = t_(dur)
    f = 420 + 900 * (1 - np.exp(-t * 25))
    return 0.5 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14)


def chime(freqs=(1318.5, 1975.5), dur=1.2, g=0.22):
    t = t_(dur)
    s = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * (3 + i)) for i, f in enumerate(freqs))
    s += 0.3 * np.sin(2 * np.pi * freqs[0] * 2.01 * t) * np.exp(-t * 6)
    return g * s * np.minimum(1, t / 0.004)


def key_click():
    t = t_(0.025)
    return 0.18 * lowpass(rng.standard_normal(len(t)), 4000) * np.exp(-t * 220)


# ---------------------------------------------------------------- music bed (C major, 96 bpm, soft)
def music():
    bpm = 96; beat = 60 / bpm; bar = 4 * beat
    chords = [(48, 52, 55, 59, 64), (45, 48, 52, 55, 60), (41, 45, 48, 52, 57), (43, 47, 50, 55, 62)]  # Cmaj7 Am7 Fmaj7 G6
    m = np.zeros((N, 2))
    hz = lambda n: 440 * 2 ** ((n - 69) / 12)
    nbars = int(TL["total"] / bar) + 2
    for b in range(nbars):
        ch = chords[b % 4]; t0 = b * bar
        # pad: detuned saws softened
        tt = t_(bar + 0.6)
        pad = np.zeros(len(tt))
        for nn in ch:
            for det in (-0.12, 0.12):
                f = hz(nn) * 2 ** (det / 12)
                pad += np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(4 * np.pi * f * tt)
        pad = lowpass(pad, 1400) * np.minimum(1, tt / 0.5) * np.minimum(1, np.maximum(0, (bar + 0.6 - tt) / 0.6))
        place(m, pad * 0.024, t0, pan=0)
        # plucked arpeggio, 8th notes
        for k in range(8):
            nn = ch[[0, 2, 4, 2, 1, 3, 4, 3][k]] + 12
            tp = t_(0.5)
            pl = (np.sin(2 * np.pi * hz(nn) * tp) + 0.3 * np.sin(4 * np.pi * hz(nn) * tp)) * np.exp(-tp * 9)
            place(m, pl * 0.035, t0 + k * beat / 2, pan=(-0.35 if k % 2 else 0.35))
        # soft kick on 1 and 3, shaker on off-beats (from bar 2 on, when the product appears)
        if t0 >= SC["brand"]["start"] - 0.1:
            for k in (0, 2):
                place(m, thump(52, 0.35, 0.15) * 0.22, t0 + k * beat)
            for k in range(8):
                sh = rng.standard_normal(int(0.05 * SR)) * np.exp(-np.arange(int(0.05 * SR)) / SR * 90)
                place(m, lowpass(sh - lowpass(sh, 5000), 9000) * 0.012, t0 + k * beat / 2 + beat / 4, pan=0.2)
    # fade in / out
    x = np.arange(N) / SR
    m *= np.minimum(1, x / 2.0)[:, None] * np.clip((TL["total"] + 0.3 - x) / 2.5, 0, 1)[:, None]
    return m


def load_vo(sid):
    wav = A / f"vo_{sid}.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(A / f"vo_{sid}.mp3"), "-ac", "1", "-ar", str(SR), str(wav)], check=True)
    with wave.open(str(wav)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768


def main():
    vo = np.zeros((N, 2)); duck = np.ones(N)
    for s in TL["scenes"]:
        v = load_vo(s["id"]) * 1.05
        place(vo, v, s["vo_at"])
        i0, i1 = int((s["vo_at"] - 0.15) * SR), int((s["vo_at"] + s["vo_len"] + 0.25) * SR)
        duck[max(0, i0):min(N, i1)] = 0.45
    duck = np.convolve(duck, np.ones(int(0.12 * SR)) / int(0.12 * SR), mode="same")   # smooth the ducking

    fx = np.zeros((N, 2))
    H, B, F, V, R, Rd, P, C = (SC[k] for k in ("hook", "brand", "feed", "venue", "reco", "read", "private", "cta"))
    place(fx, whoosh(0.6, True), 0.25, 0.8); place(fx, whoosh(0.5, True, 1.3), 2.45, 0.8)
    for k in range(40):                                                     # the counter rattling up
        at = 1.2 + 4.8 * (k / 40) ** 1.6
        place(fx, tick(2600 + 300 * (k % 3)), at, 0.5, pan=0.3)
    place(fx, whoosh(0.7, False, 0.8), B["start"] - 0.2, 0.7)
    place(fx, thump(60, 0.8, 0.7), B["start"] + 0.45, 0.9)
    place(fx, chime((1046.5, 1568.0)), B["start"] + 1.0, 0.8)
    place(fx, whoosh(0.55, True), F["start"] + 0.05, 0.6)
    for s in (3.2, 5.6, 8.0):
        place(fx, whoosh(0.4, True, 1.6), F["start"] + s - 0.05, 0.7, pan=0.25)
    for i in range(4):
        place(fx, thump(85, 0.35, 0.9) * 0.55, V["start"] + 1.6 + i * 0.45 + 0.12, 0.8, pan=-0.2)
    tap = R["start"] + 1.4
    place(fx, tick(1800, 0.04) * 1.6, tap, 0.9, pan=0.25); place(fx, tick(1800, 0.04) * 1.6, tap + 0.25, 0.9, pan=0.25)
    place(fx, pop(), tap + 0.3, 0.9, pan=0.25)
    place(fx, chime((1760.0, 2637.0), 0.9, 0.15), R["start"] + 3.4, 0.8, pan=0.25)
    place(fx, whoosh(0.45, True, 1.1), Rd["start"] + 0.15, 0.6, pan=0.25)
    rr = np.random.default_rng(3); at = Rd["start"] + 2.2
    while at < Rd["start"] + 5.6:
        place(fx, key_click(), at, 0.8, pan=-0.3); at += 0.045 + rr.random() * 0.06
    for k in range(int((P["end"] - P["start"]) / 1.6) + 1):      # a soft blip each time the packet leaves
        place(fx, tick(880, 0.12) * 0.8, P["start"] + k * 1.6 + 0.05, 0.6, pan=-0.4)
    for i in range(3):
        place(fx, chime((1318.5 + i * 196, 1975.5 + i * 196), 0.8, 0.16), P["start"] + 1.6 + i * 0.9 + 0.1, 0.8, pan=-0.3)
    place(fx, thump(55, 1.0, 0.8), C["start"] + 0.25, 1.0)
    place(fx, chime((1046.5, 1318.5, 1568.0)), C["start"] + 1.55, 0.9)

    mix = music() * duck[:, None] + vo + fx * 0.7
    peak = np.max(np.abs(mix)); mix = mix / peak * 0.89 if peak > 0.89 else mix
    out = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(A / "mix.wav"), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(out.tobytes())
    print("mix.wav", round(N / SR, 2), "s, peak", round(float(peak), 3))


main()
