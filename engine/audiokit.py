"""Audio measurement with numpy only: decode, beat grid, downbeat, drop, effect peaks."""
import subprocess
import numpy as np

SR = 44100
HOP = 256  # onset envelope resolution: 5.8 ms


def load(path, sr=SR, ch=1):
    """Decode any file to float32 via ffmpeg: 1-D when ch is 1, else (samples, ch)."""
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-ac", str(ch), "-ar", str(sr),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32)
    return x.copy() if ch == 1 else x.reshape(-1, ch).copy()


def _spec(x, n_fft=2048):
    frames = np.lib.stride_tricks.sliding_window_view(np.pad(x, (n_fft // 2, n_fft)), n_fft)[::HOP]
    return np.abs(np.fft.rfft(frames * np.hanning(n_fft), axis=1))


def onset_env(x):
    """Half-wave rectified log spectral flux."""
    L = np.log1p(100 * _spec(x))
    o = np.maximum(np.diff(L, axis=0, prepend=L[:1]), 0).sum(1)
    return o - np.convolve(o, np.ones(64) / 64, "same")  # remove slow loudness trend


def beat_grid(x, bpm_lo=80, bpm_hi=160):
    """Fit one fixed tempo + phase to the whole track (produced music has a constant grid).
    The search spans exactly one octave, so every tempo has one answer (no half/double confusion).
    Returns (bpm, beat_times) for every beat from 0 to the end of the track."""
    o = np.maximum(onset_env(x), 0)
    fps = SR / HOP
    # Coarse: autocorrelation with a harmonic sum so the true beat beats its half/double.
    ac = np.correlate(o, o, "full")[len(o) - 1:]
    lags = np.arange(int(fps * 60 / bpm_hi), int(fps * 60 / bpm_lo))
    score = ac[lags] + 0.5 * ac[np.minimum(2 * lags, len(ac) - 1)] + 0.5 * ac[lags // 2]
    period = lags[np.argmax(score)] / fps
    # Fine: comb search over period and phase, sampling the envelope at every predicted beat.
    t_env = np.arange(len(o)) / fps
    best = (-1, period, 0)
    for p in np.linspace(period * 0.99, period * 1.01, 401):
        for ph in np.linspace(0, p, 120, endpoint=False):
            s = np.interp(np.arange(ph, t_env[-1], p), t_env, o).sum()
            if s > best[0]:
                best = (s, p, ph)
    _, p, ph = best
    for ph2 in np.linspace(ph - p / 120, ph + p / 120, 41):  # sub-hop phase refinement
        s = np.interp(np.arange(ph2 % p, t_env[-1], p), t_env, o).sum()
        if s > best[0]:
            best = (s, p, ph2 % p)
    _, p, ph = best
    # Broadband flux can lock onto off-beat hi-hats. The beat is where the kick is: keep whichever of
    # ph or ph + p/2 has more bass energy in the quarter-beat after it.
    X = np.fft.rfft(x)
    X[np.fft.rfftfreq(len(x), 1 / SR) > 120] = 0
    bass = np.fft.irfft(X, len(x)) ** 2
    kick = lambda q: sum(bass[int(t * SR): int((t + p / 4) * SR)].sum() for t in np.arange(q, len(x) / SR - p, p))
    ph = max((ph, (ph + p / 2) % p), key=kick)
    # The 46 ms FFT window smears onsets early; re-align phase on a ~1 ms time-domain attack envelope.
    ms = SR // 1000
    env = np.sqrt(np.mean(x[: len(x) // ms * ms].reshape(-1, ms) ** 2, axis=1) + 1e-10)
    db = np.maximum(20 * np.log10(env), 20 * np.log10(env.max()) - 60)  # 60 dB floor below peak
    att = np.convolve(np.maximum(np.diff(db, prepend=db[0]), 0), np.bartlett(9), "same")  # ±4 ms tolerance
    t_ms = np.arange(len(att)) * ms / SR + ms / SR / 2  # bin centres, true bin length
    score = lambda pq: np.interp(np.arange(pq[1] % pq[0], t_ms[-1], pq[0]), t_ms, att).sum()
    p, ph = max(((p2, q) for p2 in np.linspace(p * 0.9995, p * 1.0005, 21)
                 for q in np.arange(ph - 0.03, ph + 0.03, 0.0005)), key=score)
    ph %= p
    return 60 / p, np.arange(ph, len(x) / SR, p)


def downbeat_phase(x, beats, top=16):
    """Which of the 4 beat positions is beat 1. Sections (breakdowns, drops, new layers) start on
    downbeats, so the biggest beat-to-beat loudness steps vote for their position in the bar.
    Kick onsets can't tell: four-on-the-floor music hits every beat equally."""
    e = level_db(x, beats)
    e = np.maximum(e, np.median(e) - 20)  # silence (intro/outro) counts as one level, not -100 dB
    step = np.abs(np.diff(e))
    idx = [i for i in np.argsort(step)[::-1][:top] if step[i] > 3]  # real section changes only
    votes = np.zeros(4)
    np.add.at(votes, (np.array(idx, int) + 1) % 4, np.minimum(step[idx], 12))  # no single step dominates
    return int(np.argmax(votes))


def level_db(x, marks):
    """Loudness of each stretch between consecutive marks (beats or downbeats), in dB."""
    edges = (np.append(marks, len(x) / SR) * SR).astype(int)
    return np.array([10 * np.log10(np.mean(x[a:b] ** 2) + 1e-12) for a, b in zip(edges[:-1], edges[1:])])


def find_drop(x, downbeats, span=4):
    """Downbeat with the biggest jump in loudness: mean of the next `span` bars minus the previous `span`."""
    e = level_db(x, downbeats)
    jumps = [(e[i:i + span].mean() - e[i - span:i].mean(), i) for i in range(span, len(e) - span)]
    if not jumps:
        raise SystemExit(f"a drop needs {2 * span + 1} bars or more; this track has {len(e)}")
    jump, i = max(jumps)
    return downbeats[i], jump


def peak_ms(x):
    return 1000 * np.argmax(np.abs(x)) / SR


if __name__ == "__main__":
    # Self-check on a real-shaped signal: 120 BPM, kick on the beat and louder hi-hats on the off-beat
    # (the case that fools broadband onset detection), a drop at 16.25 s and a breakdown at 28.25 s.
    t = np.arange(int(SR * 40)) / SR
    x = np.zeros_like(t)
    n = 4000
    kick = np.sin(2 * np.pi * 55 * t[:n]) * np.exp(-t[:n] * 25)
    hat = np.random.default_rng(0).standard_normal(n) * np.exp(-t[:n] * 300)
    for bt in np.arange(0.25, 39.5, 0.5):
        i, j = int(bt * SR), int((bt + 0.25) * SR)
        gain = 1 if bt < 16.25 else (3 if bt < 28.25 else 1.5)
        x[i:i + n] += gain * kick
        x[j:j + n] += 1.5 * gain * hat
    bpm, beats = beat_grid(x)
    assert abs(bpm - 120) < 0.1, bpm
    assert abs(beats[0] - 0.25) < 0.004, beats[0]
    ph = downbeat_phase(x, beats)
    assert ph == 0, ph
    drop, _ = find_drop(x, beats[ph::4])
    assert abs(drop - 16.25) < 0.01, drop
    print("audiokit self-check ok")
