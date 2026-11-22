#!/usr/bin/env python3
"""Stage 3B: Download RSS audio, localize full broadcasts with WavLM-SV, and transcribe on GPU."""

import argparse
import gc
import json
import os
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import requests
import soundfile as sf
import torch
import torch.nn.functional as F
from faster_whisper import WhisperModel
from transformers import AutoFeatureExtractor, WavLMForXVector

BASE_DIR = Path("/home/mike10010100/state-name-analysis")
DATA_DIR = BASE_DIR / "data"
AUDIO_RAW = BASE_DIR / "audio" / "raw"
AUDIO_DIR = BASE_DIR / "audio"
TRANS_DIR = BASE_DIR / "transcripts"
AUDIO_RAW.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
TRANS_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PodcastCorpusResearch/1.0)"}


def valid_wav(path: Path) -> float | None:
    if not path.exists() or path.stat().st_size < 32000:
        return None
    try:
        info = sf.info(str(path))
        if info.samplerate == 16000 and info.channels == 1 and info.duration > 15.0:
            return float(info.duration)
    except Exception:
        return None
    return None


def download_and_convert(item: dict) -> dict:
    eid = item["episode_id"]
    wav_path = AUDIO_DIR / f"{eid}.wav"
    existing = valid_wav(wav_path)
    if existing is not None:
        return {"episode_id": eid, "status": "cached", "audio_duration": existing}

    raw_path = AUDIO_RAW / f"{eid}.mp3"
    try:
        if not raw_path.exists() or raw_path.stat().st_size < 16000:
            r = requests.get(item["audio_url"], headers=HEADERS, stream=True, timeout=240, allow_redirects=True)
            r.raise_for_status()
            tmp_path = AUDIO_RAW / f"{eid}.part"
            with open(tmp_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=131072):
                    if chunk:
                        f.write(chunk)
            tmp_path.replace(raw_path)

        env = os.environ.copy()
        env["PATH"] = f"/home/mike10010100/.local/bin:{env.get('PATH', '')}"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(raw_path),
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            str(wav_path),
        ]
        subprocess.run(cmd, check=True, env=env, timeout=240)
        dur = valid_wav(wav_path)
        if dur is None:
            return {"episode_id": eid, "status": "error", "error": "invalid wav after ffmpeg"}
        return {"episode_id": eid, "status": "downloaded", "audio_duration": dur}
    except Exception as e:
        return {"episode_id": eid, "status": "error", "error": str(e)[:200]}


def embed_chunks(chunks: list[np.ndarray], fe, sv, batch_size: int = 24) -> np.ndarray:
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


def localize_candidate_windows(
    audio: np.ndarray,
    sr: int,
    fe,
    sv,
    centroid: np.ndarray,
    tau: float,
) -> tuple[list[tuple[float, float]], list[dict]]:
    total_sec = len(audio) / sr
    win_sec = 3.0
    hop_sec = 1.5
    win_samples = int(win_sec * sr)
    hop_samples = int(hop_sec * sr)

    chunks = []
    spans = []
    pos = 0
    while pos + int(1.5 * sr) <= len(audio):
        end_pos = min(len(audio), pos + win_samples)
        ch = audio[pos:end_pos]
        if float(np.sqrt(np.mean(ch * ch))) >= 0.004:
            chunks.append(ch)
            spans.append((pos / sr, end_pos / sr))
        pos += hop_samples

    if not chunks:
        return [], []

    embs = embed_chunks(chunks, fe, sv, batch_size=24)
    sims = embs @ centroid

    scan_thresh = tau - 0.03
    hits = [(s0, s1, float(sim)) for (s0, s1), sim in zip(spans, sims) if sim >= scan_thresh]
    if not hits:
        return [], [{"max_sim_overall": round(float(sims.max()), 4), "kept": False}]

    clusters = []
    cur = [hits[0]]
    for h in hits[1:]:
        if h[0] - cur[-1][1] <= 180.0:
            cur.append(h)
        else:
            clusters.append(cur)
            cur = [h]
    clusters.append(cur)

    kept_windows = []
    cluster_meta = []
    for cl in clusters:
        hit_count = len(cl)
        c_start = cl[0][0]
        c_end = cl[-1][1]
        max_sim = max(h[2] for h in cl)
        mean_sim = float(np.mean([h[2] for h in cl]))
        info = {
            "raw_start": round(c_start, 2),
            "raw_end": round(c_end, 2),
            "hit_windows": hit_count,
            "approx_hit_sec": round(hit_count * hop_sec, 1),
            "max_sim": round(max_sim, 4),
            "mean_sim": round(mean_sim, 4),
        }
        if hit_count >= 12 or (hit_count >= 8 and (c_end - c_start) >= 40.0):
            pad_start = max(0.0, c_start - 45.0)
            pad_end = min(total_sec, c_end + 45.0)
            kept_windows.append((pad_start, pad_end))
            info["kept"] = True
        else:
            info["kept"] = False
        cluster_meta.append(info)

    if not kept_windows:
        return [], cluster_meta
    kept_windows.sort()
    merged = [kept_windows[0]]
    for ws, we in kept_windows[1:]:
        if ws <= merged[-1][1] + 5.0:
            merged[-1] = (merged[-1][0], max(merged[-1][1], we))
        else:
            merged.append((ws, we))
    return [(round(s, 3), round(e, 3)) for s, e in merged], cluster_meta


def transcribe_windows(
    model: WhisperModel,
    audio: np.ndarray,
    sr: int,
    windows: list[tuple[float, float]],
) -> list[dict]:
    all_segs = []
    for ws, we in windows:
        sub = audio[int(ws * sr) : int(we * sr)]
        segs_iter, _ = model.transcribe(sub, vad_filter=True, word_timestamps=True, beam_size=5)
        for s in segs_iter:
            words = []
            if s.words:
                for w in s.words:
                    words.append({
                        "word": w.word,
                        "start": round(ws + float(w.start), 3),
                        "end": round(ws + float(w.end), 3),
                        "prob": round(float(w.probability), 3),
                    })
            all_segs.append({
                "start": round(ws + float(s.start), 3),
                "end": round(ws + float(s.end), 3),
                "text": s.text.strip(),
                "words": words,
            })
    return all_segs


def word_ngrams(text: str, n: int = 5) -> set[tuple[str, ...]]:
    tokens = re.findall(r"[a-z0-9']+", text.lower())
    if len(tokens) < n:
        return set()
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def check_duplicates(manifest: list[dict]) -> None:
    by_cand: dict[str, list[tuple[dict, set]]] = {"scott_colom": [], "abdul_el_sayed": []}
    for item in manifest:
        tpath = TRANS_DIR / f"{item['episode_id']}.json"
        if not tpath.exists():
            continue
        data = json.loads(tpath.read_text())
        full_text = " ".join(seg["text"] for seg in data.get("segments", []))
        grams = word_ngrams(full_text, 5)
        by_cand.setdefault(item["candidate"], []).append((item, grams))

    print("\n=== 5-GRAM DUPLICATE CHECK ===")
    found = False
    for cand, rows in by_cand.items():
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, ga = rows[i]
                b, gb = rows[j]
                if not ga or not gb:
                    continue
                inter = len(ga & gb)
                union = len(ga | gb)
                jacc = inter / union if union else 0.0
                contain = inter / min(len(ga), len(gb))
                if jacc > 0.12 or contain > 0.25:
                    found = True
                    print(
                        f"  [OVERLAP {cand}] {a['episode_id']} ({a['title'][:38]}) <-> "
                        f"{b['episode_id']} ({b['title'][:38]}) | jaccard={jacc:.3f}, containment={contain:.3f}"
                    )
    if not found:
        print("  No duplicate transcripts detected (max jaccard <= 0.12, containment <= 0.25).")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(DATA_DIR / "rss_corpus_manifest.json"))
    parser.add_argument("--tau-colom", type=float, required=True)
    parser.add_argument("--tau-abdul", type=float, required=True)
    parser.add_argument("--download-workers", type=int, default=6)
    args = parser.parse_args()

    taus = {"scott_colom": args.tau_colom, "abdul_el_sayed": args.tau_abdul}
    print(f"Using WavLM-SV localization thresholds: {taus}")

    manifest = json.loads(Path(args.manifest).read_text())
    excluded_path = DATA_DIR / "excluded_episodes.json"
    excluded = json.loads(excluded_path.read_text()) if excluded_path.exists() else {}

    filtered_manifest = []
    for item in manifest:
        if item["episode_id"] == "colom_freshair_20261119":
            excluded["colom_freshair_20261119"] = {
                **item,
                "reason": "no_candidate_interview_guest_panel_only",
            }
            continue
        filtered_manifest.append(item)

    print(f"Downloading / checking {len(filtered_manifest)} RSS episodes...")
    dl_errors = []
    with ThreadPoolExecutor(max_workers=args.download_workers) as ex:
        futs = [ex.submit(download_and_convert, item) for item in filtered_manifest]
        for idx, fut in enumerate(as_completed(futs), 1):
            res = fut.result()
            if res["status"] == "error":
                dl_errors.append(res)
                print(f"  [DL ERR {idx}/{len(filtered_manifest)}] {res['episode_id']}: {res['error']}")
            elif res["status"] == "downloaded":
                print(f"  [DL OK {idx}/{len(filtered_manifest)}] {res['episode_id']} ({res['audio_duration']:.1f}s)")

    vps = np.load(DATA_DIR / "voiceprints.npz")
    centroids = {k: vps[k] for k in ["scott_colom", "abdul_el_sayed"]}

    pending = []
    for item in filtered_manifest:
        eid = item["episode_id"]
        wav_path = AUDIO_DIR / f"{eid}.wav"
        tpath = TRANS_DIR / f"{eid}.json"
        if valid_wav(wav_path) is None:
            continue
        if tpath.exists():
            try:
                ex_d = json.loads(tpath.read_text())
                if ex_d.get("episode_id") == eid and ex_d.get("segments") is not None:
                    continue
            except Exception:
                pass
        if eid in excluded:
            continue
        pending.append(item)

    print(f"\nPhase 1: Localizing full broadcasts among {len(pending)} pending episodes with WavLM-SV...")
    win_plan = {}
    if pending:
        fe = AutoFeatureExtractor.from_pretrained("microsoft/wavlm-base-plus-sv")
        sv = WavLMForXVector.from_pretrained("microsoft/wavlm-base-plus-sv").cuda().eval()
        for idx, item in enumerate(pending, 1):
            eid = item["episode_id"]
            cand = item["candidate"]
            audio, sr = sf.read(str(AUDIO_DIR / f"{eid}.wav"), dtype="float32")
            total_sec = len(audio) / sr
            if item.get("is_full_broadcast"):
                t0 = time.time()
                windows, cluster_meta = localize_candidate_windows(audio, sr, fe, sv, centroids[cand], taus[cand])
                if not windows:
                    excluded[eid] = {
                        "episode_id": eid,
                        "candidate": cand,
                        "show": item["show"],
                        "title": item["title"],
                        "pub_date": item["pub_date"],
                        "reason": "pundit_only_no_interview",
                        "cluster_meta": cluster_meta,
                    }
                    excluded_path.write_text(json.dumps(excluded, indent=2))
                    print(f"  [LOC SKIP {idx}/{len(pending)}] {eid} ({total_sec:.0f}s) -> no interview | {cluster_meta}")
                    continue
                win_plan[eid] = (total_sec, windows, cluster_meta)
                print(f"  [LOC HIT  {idx}/{len(pending)}] {eid} ({total_sec:.0f}s) -> {len(windows)} win ({sum(e-s for s,e in windows):.0f}s) in {time.time()-t0:.1f}s")
            else:
                win_plan[eid] = (total_sec, [(0.0, round(total_sec, 3))], [])

        del sv
        gc.collect()
        torch.cuda.empty_cache()

    print(f"\nPhase 2: Transcribing {len(win_plan)} episodes with Whisper medium.en CUDA...")
    if win_plan:
        model = WhisperModel("medium.en", device="cuda", compute_type="int8_float16")
        to_transcribe = [item for item in pending if item["episode_id"] in win_plan]
        for idx, item in enumerate(to_transcribe, 1):
            eid = item["episode_id"]
            total_sec, windows, cluster_meta = win_plan[eid]
            t0 = time.time()
            audio, sr = sf.read(str(AUDIO_DIR / f"{eid}.wav"), dtype="float32")
            segs = transcribe_windows(model, audio, sr, windows)
            trans_dur = sum(e - s for s, e in windows)
            payload = {
                "episode_id": eid,
                "candidate": item["candidate"],
                "show": item["show"],
                "title": item["title"],
                "pub_date": item["pub_date"],
                "category": item["category"],
                "period": item["period"],
                "is_full_broadcast": item["is_full_broadcast"],
                "matched_venue": item.get("matched_venue", ""),
                "audio_duration_sec": round(total_sec, 3),
                "extracted_windows": windows,
                "transcribed_duration_sec": round(trans_dur, 3),
                "cluster_meta": cluster_meta,
                "segments": segs,
            }
            (TRANS_DIR / f"{eid}.json").write_text(json.dumps(payload, indent=2))
            print(
                f"  [TRANS {idx}/{len(to_transcribe)}] {eid} | full={total_sec:.0f}s -> win={trans_dur:.0f}s "
                f"| segs={len(segs)} | elapsed={time.time()-t0:.1f}s | {item['show']} ({item['pub_date']})"
            )
        del model
        gc.collect()
        torch.cuda.empty_cache()

    excluded_path.write_text(json.dumps(excluded, indent=2))
    check_duplicates(filtered_manifest)
    print(f"Done. Download errors: {len(dl_errors)}, Excluded: {len(excluded)}")


if __name__ == "__main__":
    main()
