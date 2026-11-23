#!/usr/bin/env python3
"""Download seed & validation episodes for voiceprint slice inspection."""

import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
import soundfile as sf
from faster_whisper import WhisperModel

PF_DIR = Path("/home/mike10010100/state-name-analysis/platner_fetterman")
DATA_DIR = PF_DIR / "data"
AUDIO_RAW = PF_DIR / "audio" / "raw"
AUDIO_DIR = PF_DIR / "audio"
AUDIO_RAW.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PodcastCorpusResearch/1.0)"}

SEEDS_AND_VAL = [
    # Platner seeds & val
    "gp_why_is_this_happening_20250909",
    "gp_lever_time_20251101",
    "gp_weekly_show_stewart_20260429",
    "gp_choose_hard_way_20260421",
    "gp_11th_hour_velshi_20260605",
    # Fetterman seeds & val
    "jf_all_in_pod_20260318",
    "jf_reason_interview_20260513",
    "jf_weekly_show_stewart_20260805",
    "jf_meet_the_press_20260729",
    "jf_conversation_burns_20260213",
]

SEEDS_TO_PRINT = [
    "gp_why_is_this_happening_20250909",
    "gp_lever_time_20251101",
    "jf_all_in_pod_20260318",
    "jf_reason_interview_20260513",
]


def download_and_convert(item: dict) -> dict:
    eid = item["episode_id"]
    wav_path = AUDIO_DIR / f"{eid}.wav"
    if wav_path.exists() and wav_path.stat().st_size > 32000:
        try:
            info = sf.info(str(wav_path))
            if info.samplerate == 16000 and info.channels == 1 and info.duration > 15.0:
                return {"episode_id": eid, "status": "cached", "dur": info.duration}
        except Exception:
            pass
    raw_path = AUDIO_RAW / f"{eid}.mp3"
    try:
        if not raw_path.exists() or raw_path.stat().st_size < 16000:
            r = requests.get(item["audio_url"], headers=HEADERS, stream=True, timeout=240, allow_redirects=True)
            r.raise_for_status()
            tmp = AUDIO_RAW / f"{eid}.part"
            with open(tmp, "wb") as f:
                for ch in r.iter_content(chunk_size=131072):
                    if ch:
                        f.write(ch)
            tmp.replace(raw_path)
        env = os.environ.copy()
        env["PATH"] = f"/home/mike10010100/.local/bin:{env.get('PATH', '')}"
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw_path), "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(wav_path)],
            check=True, env=env, timeout=240,
        )
        info = sf.info(str(wav_path))
        return {"episode_id": eid, "status": "ok", "dur": info.duration}
    except Exception as e:
        return {"episode_id": eid, "status": "error", "error": str(e)[:200]}


def main():
    manifest = {r["episode_id"]: r for r in json.loads((DATA_DIR / "rss_manifest_pf.json").read_text())}
    items = [manifest[eid] for eid in SEEDS_AND_VAL]
    with ThreadPoolExecutor(max_workers=6) as ex:
        for fut in as_completed([ex.submit(download_and_convert, it) for it in items]):
            print(fut.result())

    model = WhisperModel("medium.en", device="cuda", compute_type="int8_float16")
    for eid in SEEDS_TO_PRINT:
        wav_path = AUDIO_DIR / f"{eid}.wav"
        audio, sr = sf.read(str(wav_path), dtype="float32")
        sub = audio[: min(len(audio), 12 * 60 * sr)]
        segs = list(model.transcribe(sub, vad_filter=True, word_timestamps=True, beam_size=5)[0])
        print(f"\n================ SEED TRANSCRIPT: {eid} ================")
        for s in segs:
            print(f"[{s.start:6.1f} -> {s.end:6.1f}] ({s.end - s.start:4.1f}s) {s.text.strip()}")


if __name__ == "__main__":
    main()
