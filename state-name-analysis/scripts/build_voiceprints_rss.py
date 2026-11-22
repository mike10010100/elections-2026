#!/usr/bin/env python3
"""Stage 3A: Build and empirically validate WavLM-SV voiceprints (sequential GPU phases to keep VRAM <2GB)."""

import gc
import json
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torch.nn.functional as F
from faster_whisper import WhisperModel
from transformers import AutoFeatureExtractor, WavLMForXVector

BASE_DIR = Path("/home/mike10010100/state-name-analysis")
DATA_DIR = BASE_DIR / "data"
AUDIO_DIR = BASE_DIR / "audio"

PURE_REF_SLICES = {
    "scott_colom": [
        ("colom_mstoday_20260505", 142.0, 261.0),
        ("colom_mstoday_20260505", 291.5, 308.5),
        ("colom_breakfastclub_20261102", 193.0, 260.0),
    ],
    "abdul_el_sayed": [
        ("abdul_60min_20261102", 137.0, 173.5),
        ("abdul_60min_20261102", 182.5, 238.0),
        ("abdul_60min_20261102", 247.0, 281.5),
        ("abdul_newsmakers_20261112", 110.0, 262.0),
    ],
}

VAL_TESTS = {
    "scott_colom": ["colom_tavissmiley_20261028", "colom_mtp_20261115", "colom_freshair_20261119"],
    "abdul_el_sayed": ["abdul_morningjoe_20261105", "abdul_jonstewart_20261021", "abdul_psa_20260913"],
}


def embed_chunks(chunks: list[np.ndarray], fe, sv, batch_size: int = 16) -> np.ndarray:
    all_embs = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        inputs = fe(batch, sampling_rate=16000, return_tensors="pt", padding=True)
        inputs = {k: v.to("cuda") for k, v in inputs.items()}
        with torch.inference_mode(), torch.amp.autocast("cuda", dtype=torch.float16):
            out = sv(**inputs).embeddings
            out = F.normalize(out.float(), dim=-1)
        all_embs.append(out.cpu().numpy())
    return np.vstack(all_embs)


def split_turns(segments, pause_thresh: float = 0.45) -> list[dict]:
    turns = []
    for seg in segments:
        words = seg.words or []
        if not words:
            turns.append({"start": float(seg.start), "end": float(seg.end), "text": seg.text.strip()})
            continue
        cur = [words[0]]
        for w in words[1:]:
            if float(w.start) - float(cur[-1].end) >= pause_thresh:
                turns.append({
                    "start": float(cur[0].start),
                    "end": float(cur[-1].end),
                    "text": "".join(x.word for x in cur).strip(),
                })
                cur = [w]
            else:
                cur.append(w)
        turns.append({
            "start": float(cur[0].start),
            "end": float(cur[-1].end),
            "text": "".join(x.word for x in cur).strip(),
        })
    return [t for t in turns if t["text"]]


def main():
    # Phase 1: Transcribe validation excerpts with Whisper, then release GPU memory
    val_turns_cache = {}
    whisper_model = WhisperModel("medium.en", device="cuda", compute_type="int8_float16")
    for cand, tests in VAL_TESTS.items():
        for eid in tests:
            audio, sr = sf.read(str(AUDIO_DIR / f"{eid}.wav"), dtype="float32")
            sub = audio[: min(len(audio), 32 * 60 * sr)]
            segs = list(whisper_model.transcribe(sub, vad_filter=True, word_timestamps=True, beam_size=5)[0])
            val_turns_cache[eid] = split_turns(segs, pause_thresh=0.45)
            print(f"Transcribed val excerpt {eid}: {len(val_turns_cache[eid])} turns")
    del whisper_model
    gc.collect()
    torch.cuda.empty_cache()

    # Phase 2: Load WavLM-SV cleanly on CUDA
    fe = AutoFeatureExtractor.from_pretrained("microsoft/wavlm-base-plus-sv")
    sv = WavLMForXVector.from_pretrained("microsoft/wavlm-base-plus-sv").cuda().eval()

    centroids = {}
    ref_diag = {}

    for cand, slices in PURE_REF_SLICES.items():
        chunks = []
        total_sec = 0.0
        for eid, s0, s1 in slices:
            audio, sr = sf.read(str(AUDIO_DIR / f"{eid}.wav"), dtype="float32")
            t = s0
            while t + 3.0 <= s1:
                e_t = min(s1, t + 4.0)
                ch = audio[int(t * sr) : int(e_t * sr)]
                if float(np.sqrt(np.mean(ch * ch))) >= 0.004:
                    chunks.append(ch)
                t += 2.0
            total_sec += s1 - s0
        embs = embed_chunks(chunks, fe, sv, batch_size=16)
        c = np.mean(embs, axis=0)
        c /= np.linalg.norm(c)
        centroids[cand] = c
        sims_self = embs @ c
        ref_diag[cand] = {
            "slices": slices,
            "total_ref_sec": round(total_sec, 1),
            "window_count": len(chunks),
            "intra_ref_min": round(float(sims_self.min()), 4),
            "intra_ref_p10": round(float(np.percentile(sims_self, 10)), 4),
            "intra_ref_med": round(float(np.median(sims_self)), 4),
            "intra_ref_max": round(float(sims_self.max()), 4),
        }
        print(f"Centroid {cand}: {len(chunks)} windows ({total_sec:.1f}s) | self-sim p10={ref_diag[cand]['intra_ref_p10']}, med={ref_diag[cand]['intra_ref_med']}, min={ref_diag[cand]['intra_ref_min']}")

    cross_sim = float(np.dot(centroids["scott_colom"], centroids["abdul_el_sayed"]))
    print(f"\n*** Cross-candidate WavLM-SV similarity (Colom vs El-Sayed): {cross_sim:.4f} ***")

    val_report = {}
    for cand, tests in VAL_TESTS.items():
        print(f"\n==================== WAVLM-SV VALIDATION: {cand} ====================")
        centroid = centroids[cand]
        all_scored = []
        for eid in tests:
            audio, sr = sf.read(str(AUDIO_DIR / f"{eid}.wav"), dtype="float32")
            sub = audio[: min(len(audio), 32 * 60 * sr)]
            turns = val_turns_cache[eid]

            turn_chunks = []
            valid_turns = []
            for t in turns:
                dur = t["end"] - t["start"]
                if dur < 1.0:
                    continue
                if dur < 1.5:
                    pad = (1.6 - dur) / 2.0
                    s_i = max(0, int((t["start"] - pad) * sr))
                    e_i = min(len(sub), int((t["end"] + pad) * sr))
                else:
                    s_i = max(0, int(t["start"] * sr))
                    e_i = min(len(sub), int(min(t["end"], t["start"] + 8.0) * sr))
                ch = sub[s_i:e_i]
                if len(ch) >= int(0.8 * sr) and float(np.sqrt(np.mean(ch * ch))) >= 0.004:
                    turn_chunks.append(ch)
                    valid_turns.append({**t, "dur": round(dur, 2), "eid": eid})

            embs = embed_chunks(turn_chunks, fe, sv, batch_size=16)
            sims = embs @ centroid
            for t, sim in zip(valid_turns, sims):
                t["sim"] = round(float(sim), 4)
                all_scored.append(t)
            print(
                f"  {eid}: n={len(sims)} | min={sims.min():.3f} p25={np.percentile(sims,25):.3f} "
                f"med={np.median(sims):.3f} p75={np.percentile(sims,75):.3f} p90={np.percentile(sims,90):.3f} max={sims.max():.3f}"
            )

        main_turns = [x for x in all_scored if "freshair" not in x["eid"] and x["dur"] >= 2.0]
        vals = [x["sim"] for x in main_turns]
        bins = np.arange(0.50, 1.02, 0.02)
        counts, edges = np.histogram(vals, bins=bins)
        print("  Similarity histogram (turns >= 2.0s, excluding negative control):")
        for cnt, lo, hi in zip(counts, edges[:-1], edges[1:]):
            if cnt > 0:
                print(f"    [{lo:.2f}, {hi:.2f}): {cnt:3d} " + "#" * min(45, cnt))

        main_long = [x for x in main_turns if x["dur"] >= 2.5]
        main_long.sort(key=lambda x: x["sim"], reverse=True)
        print("  Top 8 highest-sim:")
        for x in main_long[:8]:
            print(f"    {x['sim']:.4f} ({x['eid']} {x['start']:.0f}s) | {x['text'][:95]}")
        print("  Band 0.85..0.95 (inspect transition!):")
        band = [x for x in main_long if 0.85 <= x["sim"] <= 0.95]
        for x in band[:28]:
            print(f"    {x['sim']:.4f} ({x['eid']} {x['start']:.0f}s) | {x['text'][:95]}")

        val_report[cand] = {
            "histogram_edges": [round(float(x), 2) for x in edges],
            "histogram_counts": [int(x) for x in counts],
            "band_085_095": band[:35],
        }

    np.savez(DATA_DIR / "voiceprints.npz", **centroids)
    (DATA_DIR / "voiceprint_calibration.json").write_text(
        json.dumps({
            "model": "microsoft/wavlm-base-plus-sv",
            "cross_candidate_similarity": round(cross_sim, 4),
            "reference_diagnostics": ref_diag,
            "validation": val_report,
        }, indent=2)
    )
    print("\nSaved WavLM-SV voiceprints & calibration report.")


if __name__ == "__main__":
    main()
