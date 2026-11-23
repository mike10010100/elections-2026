#!/usr/bin/env python3
"""Rebuild & calibrate cohort-centered WavLM-SV + Resemblyzer voiceprints for Platner & Fetterman."""

import gc
import json
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torch.nn.functional as F
from faster_whisper import WhisperModel
from resemblyzer import VoiceEncoder
from transformers import AutoFeatureExtractor, WavLMForXVector

PF_DIR = Path("/home/mike10010100/state-name-analysis/platner_fetterman")
DATA_DIR = PF_DIR / "data"
AUDIO_DIR = PF_DIR / "audio"
CE_VP_PATH = Path("/home/mike10010100/state-name-analysis/data/voiceprints.npz")

PURE_REF_SLICES = {
    "graham_platner": [
        ("gp_why_is_this_happening_20250909", 253.0, 346.0),
        ("gp_why_is_this_happening_20250909", 460.0, 488.5),
        ("gp_why_is_this_happening_20250909", 549.0, 614.5),
        ("gp_lever_time_20251101", 292.0, 421.5),
        ("gp_lever_time_20251101", 503.5, 569.0),
    ],
    "john_fetterman": [
        ("jf_all_in_pod_20260318", 98.0, 263.0),
        ("jf_all_in_pod_20260318", 433.0, 537.0),
        ("jf_reason_interview_20260513", 160.5, 271.5),
    ],
}

# Fixed non-target cohort slices (zero target leakage)
BG_SPEAKER_SLICES = {
    "chris_hayes": [("gp_why_is_this_happening_20250909", 107.0, 143.0), ("gp_why_is_this_happening_20250909", 170.0, 205.0)],
    "david_sirota": [("gp_lever_time_20251101", 173.0, 270.0)],
    "jon_stewart": [("jf_weekly_show_stewart_20260805", 1120.0, 1135.0), ("jf_weekly_show_stewart_20260805", 1515.0, 1525.0), ("jf_weekly_show_stewart_20260805", 1635.0, 1650.0)],
    "nick_gillespie": [("jf_reason_interview_20260513", 52.0, 95.0), ("jf_reason_interview_20260513", 590.0, 640.0)],
    "david_friedberg": [("jf_all_in_pod_20260318", 65.0, 96.0), ("jf_all_in_pod_20260318", 393.0, 430.0)],
    "indeed_ad": [("jf_weekly_show_stewart_20260805", 5.0, 62.0)],
}

VAL_TESTS = {
    "graham_platner": [
        "gp_weekly_show_stewart_20260429",
        "gp_choose_hard_way_20260421",
        "gp_11th_hour_velshi_20260605",
        "jf_reason_interview_20260513",  # male negative control
    ],
    "john_fetterman": [
        "jf_weekly_show_stewart_20260805",
        "jf_conversation_burns_20260213",
        "jf_meet_the_press_20260729",
        "gp_choose_hard_way_20260421",  # deep-voice male negative control
    ],
}


def embed_chunks_nopad(chunks: list[np.ndarray], fe, sv, batch_size: int = 24) -> np.ndarray:
    """Embed variable-length chunks without any batch zero-padding."""
    if not chunks:
        return np.zeros((0, 512), dtype=np.float32)
    CROP = 48000  # 3.0s at 16 kHz
    TWO_CROP_THRESH = int(4.2 * 16000)

    out = np.zeros((len(chunks), 512), dtype=np.float32)
    fixed_crops = []
    fixed_map = []
    short_items = []

    for i, ch in enumerate(chunks):
        n = len(ch)
        if n >= CROP:
            if n <= TWO_CROP_THRESH:
                s = (n - CROP) // 2
                fixed_crops.append(ch[s : s + CROP])
                fixed_map.append(i)
            else:
                fixed_crops.append(ch[:CROP])
                fixed_map.append(i)
                fixed_crops.append(ch[-CROP:])
                fixed_map.append(i)
        else:
            short_items.append((i, ch))

    if fixed_crops:
        crop_embs = []
        for k in range(0, len(fixed_crops), batch_size):
            batch = fixed_crops[k : k + batch_size]
            inputs = fe(batch, sampling_rate=16000, return_tensors="pt")
            inputs = {kk: vv.to("cuda") for kk, vv in inputs.items()}
            with torch.inference_mode(), torch.amp.autocast("cuda", dtype=torch.float16):
                e = sv(**inputs).embeddings
                e = F.normalize(e.float(), dim=-1)
            crop_embs.append(e.cpu().numpy())
        crop_embs = np.vstack(crop_embs)
        for ci, emb in zip(fixed_map, crop_embs):
            out[ci] += emb
        for ci in set(fixed_map):
            nrm = float(np.linalg.norm(out[ci]))
            if nrm > 0:
                out[ci] /= nrm

    if short_items:
        with torch.inference_mode(), torch.amp.autocast("cuda", dtype=torch.float16):
            for ci, ch in short_items:
                inputs = fe([ch], sampling_rate=16000, return_tensors="pt")
                inputs = {kk: vv.to("cuda") for kk, vv in inputs.items()}
                e = sv(**inputs).embeddings
                out[ci] = F.normalize(e.float(), dim=-1).cpu().numpy()[0]

    return out


def center_norm(arr: np.ndarray, mu_bg: np.ndarray) -> np.ndarray:
    if len(arr) == 0:
        return arr
    x = arr - mu_bg
    norms = np.linalg.norm(x, axis=-1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return x / norms


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


def extract_slice_chunks(slices: list[tuple[str, float, float]]) -> tuple[list[np.ndarray], float]:
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
    return chunks, total_sec


def main():
    # Phase 1: Transcribe validation excerpts with Whisper, then release GPU memory
    val_turns_cache = {}
    unique_eids = sorted({eid for lst in VAL_TESTS.values() for eid in lst})
    whisper_model = WhisperModel("medium.en", device="cuda", compute_type="int8_float16")
    for eid in unique_eids:
        audio, sr = sf.read(str(AUDIO_DIR / f"{eid}.wav"), dtype="float32")
        sub = audio[: min(len(audio), 32 * 60 * sr)]
        segs = list(whisper_model.transcribe(sub, vad_filter=True, word_timestamps=True, beam_size=5)[0])
        val_turns_cache[eid] = split_turns(segs, pause_thresh=0.45)
        print(f"Transcribed val excerpt {eid}: {len(val_turns_cache[eid])} turns")
    del whisper_model
    gc.collect()
    torch.cuda.empty_cache()

    # Phase 2: Load WavLM-SV & Resemblyzer on CUDA
    fe = AutoFeatureExtractor.from_pretrained("microsoft/wavlm-base-plus-sv")
    sv = WavLMForXVector.from_pretrained("microsoft/wavlm-base-plus-sv").cuda().eval()
    res_enc = VoiceEncoder(device="cuda")

    # Build 8-speaker non-target cohort mean mu_bg
    ce_vp = np.load(CE_VP_PATH)
    bg_vecs = []
    for k in ["scott_colom", "abdul_el_sayed"]:
        v = ce_vp[k].astype(np.float32)
        bg_vecs.append(v / np.linalg.norm(v))
    for spk, slices in BG_SPEAKER_SLICES.items():
        bg_chunks, sec = extract_slice_chunks(slices)
        bg_embs = embed_chunks_nopad(bg_chunks, fe, sv, batch_size=24)
        v = np.mean(bg_embs, axis=0)
        v /= np.linalg.norm(v)
        bg_vecs.append(v.astype(np.float32))
        print(f"BG speaker {spk:16s}: {len(bg_chunks):3d} windows ({sec:5.1f}s)")
    mu_bg = np.mean(bg_vecs, axis=0).astype(np.float32)
    print(f"Built fixed 8-speaker mu_bg (norm={float(np.linalg.norm(mu_bg)):.4f})")

    centroids_raw = {}
    centroids_cen = {}
    centroids_res = {}
    ref_diag = {}

    for cand, slices in PURE_REF_SLICES.items():
        chunks, total_sec = extract_slice_chunks(slices)
        embs_w = embed_chunks_nopad(chunks, fe, sv, batch_size=24)
        c_raw = np.mean(embs_w, axis=0)
        c_raw /= np.linalg.norm(c_raw)
        centroids_raw[cand] = c_raw.astype(np.float32)

        embs_cen = center_norm(embs_w, mu_bg)
        c_cen = np.mean(embs_cen, axis=0)
        c_cen /= np.linalg.norm(c_cen)
        centroids_cen[cand] = c_cen.astype(np.float32)

        embs_res = np.vstack([res_enc.embed_utterance(ch) for ch in chunks])
        c_res = np.mean(embs_res, axis=0)
        c_res /= np.linalg.norm(c_res)
        centroids_res[cand] = c_res.astype(np.float32)

        sims_cen_self = embs_cen @ c_cen
        sims_res_self = embs_res @ c_res
        ref_diag[cand] = {
            "slices": slices,
            "total_ref_sec": round(total_sec, 1),
            "window_count": len(chunks),
            "intra_cen_min": round(float(sims_cen_self.min()), 4),
            "intra_cen_p10": round(float(np.percentile(sims_cen_self, 10)), 4),
            "intra_cen_med": round(float(np.median(sims_cen_self)), 4),
            "intra_cen_max": round(float(sims_cen_self.max()), 4),
            "intra_res_min": round(float(sims_res_self.min()), 4),
            "intra_res_p10": round(float(np.percentile(sims_res_self, 10)), 4),
            "intra_res_med": round(float(np.median(sims_res_self)), 4),
        }
        print(
            f"Centroid {cand}: {len(chunks)} wins ({total_sec:.1f}s) | "
            f"cen p10={ref_diag[cand]['intra_cen_p10']}, med={ref_diag[cand]['intra_cen_med']}, min={ref_diag[cand]['intra_cen_min']} | "
            f"res p10={ref_diag[cand]['intra_res_p10']}, med={ref_diag[cand]['intra_res_med']}"
        )

    cross_raw = float(np.dot(centroids_raw["graham_platner"], centroids_raw["john_fetterman"]))
    cross_cen = float(np.dot(centroids_cen["graham_platner"], centroids_cen["john_fetterman"]))
    cross_res = float(np.dot(centroids_res["graham_platner"], centroids_res["john_fetterman"]))
    print(f"\n*** Cross-candidate sim (Platner vs Fetterman): raw={cross_raw:.4f} | cen={cross_cen:.4f} | res={cross_res:.4f} ***")

    val_report = {}
    for cand, tests in VAL_TESTS.items():
        print(f"\n==================== VALIDATION (sim_cen & sim_res): {cand} ====================")
        c_cen = centroids_cen[cand]
        c_res = centroids_res[cand]
        all_scored = []
        neg_ctrl = "jf_reason_interview_20260513" if cand == "graham_platner" else "gp_choose_hard_way_20260421"
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

            embs_w = embed_chunks_nopad(turn_chunks, fe, sv, batch_size=24)
            sims_cen = center_norm(embs_w, mu_bg) @ c_cen
            embs_r = np.vstack([res_enc.embed_utterance(ch) for ch in turn_chunks])
            sims_res = embs_r @ c_res

            for t, sc, sr_val in zip(valid_turns, sims_cen, sims_res):
                t["sim_cen"] = round(float(sc), 4)
                t["sim_res"] = round(float(sr_val), 4)
                all_scored.append(t)
            tag_neg = " [NEG CTRL]" if eid == neg_ctrl else ""
            print(
                f"  {eid}{tag_neg}: n={len(sims_cen)} | cen p25={np.percentile(sims_cen,25):.3f} "
                f"med={np.median(sims_cen):.3f} p75={np.percentile(sims_cen,75):.3f} p90={np.percentile(sims_cen,90):.3f} max={sims_cen.max():.3f}"
            )

        main_turns = [x for x in all_scored if x["eid"] != neg_ctrl and x["dur"] >= 2.0]
        vals = [x["sim_cen"] for x in main_turns]
        bins = np.arange(0.00, 1.05, 0.05)
        counts, edges = np.histogram(vals, bins=bins)
        print("  Centered similarity histogram sim_cen (turns >= 2.0s, excl neg ctrl):")
        below_zero = sum(1 for v in vals if v < 0.0)
        if below_zero:
            print(f"    [< 0.00): {below_zero:3d} " + "#" * min(45, below_zero))
        for cnt, lo, hi in zip(counts, edges[:-1], edges[1:]):
            if cnt > 0:
                print(f"    [{lo:.2f}, {hi:.2f}): {cnt:3d} " + "#" * min(45, cnt))

        main_long = [x for x in main_turns if x["dur"] >= 2.5]
        band = [x for x in main_long if 0.50 <= x["sim_cen"] <= 0.78]
        band.sort(key=lambda x: x["sim_cen"], reverse=True)
        print("  Transition band sim_cen in 0.50..0.78 (showing sim_cen & sim_res):")
        for x in band[:45]:
            print(f"    cen={x['sim_cen']:.4f} res={x['sim_res']:.4f} ({x['eid'][:18]:18s} {x['start']:4.0f}s) | {x['text'][:75]}")

        val_report[cand] = {
            "histogram_edges": [round(float(x), 2) for x in edges],
            "histogram_counts": [int(x) for x in counts],
            "below_zero_count": int(below_zero),
            "band_050_078": band[:50],
        }

    np.savez(
        DATA_DIR / "voiceprints_pf.npz",
        mu_bg=mu_bg,
        graham_platner=centroids_raw["graham_platner"],
        john_fetterman=centroids_raw["john_fetterman"],
        graham_platner_cen=centroids_cen["graham_platner"],
        john_fetterman_cen=centroids_cen["john_fetterman"],
        graham_platner_res=centroids_res["graham_platner"],
        john_fetterman_res=centroids_res["john_fetterman"],
    )
    (DATA_DIR / "voiceprint_calibration.json").write_text(
        json.dumps({
            "model": "microsoft/wavlm-base-plus-sv (8-speaker cohort-centered) + resemblyzer GE2E",
            "bg_cohort_speakers": ["scott_colom", "abdul_el_sayed", *BG_SPEAKER_SLICES.keys()],
            "cross_candidate_similarity_raw": round(cross_raw, 4),
            "cross_candidate_similarity_cen": round(cross_cen, 4),
            "cross_candidate_similarity_res": round(cross_res, 4),
            "reference_diagnostics": ref_diag,
            "validation": val_report,
        }, indent=2)
    )
    print("\nSaved cohort-centered WavLM-SV + Resemblyzer voiceprints & calibration report.")


if __name__ == "__main__":
    main()
