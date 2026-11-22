#!/usr/bin/env python3
"""Step 4: Turn-level WavLM-SV speaker attribution, mention extraction, and dual verification."""

import argparse
import json
import re
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torch.nn.functional as F
from transformers import AutoFeatureExtractor, WavLMForXVector

BASE_DIR = Path("/home/mike10010100/state-name-analysis")
DATA_DIR = BASE_DIR / "data"
AUDIO_DIR = BASE_DIR / "audio"
TRANS_DIR = BASE_DIR / "transcripts"
OUT_DIR = BASE_DIR / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

EXPLICIT_EXCLUDED = {
    "colom_beat_20261121": "joint_identical_twin_interview_andrew_colom",
    "abdul_morningjoe_20260810": "no_candidate_interview_mike_rogers_and_panel",
    "abdul_macfarlane_20261019": "no_candidate_interview_commentary_and_clips_only",
    "colom_allin_20261112": "no_candidate_interview_victory_clip_and_rally_panel",
    "colom_psaki_20261112": "no_candidate_interview_warnock_and_reporter_panel",
}

STRICT_PATTERNS = {
    "scott_colom": re.compile(r"^mississippi(?:'s)?$"),
    "abdul_el_sayed": re.compile(r"^michigan(?:'s)?$"),
}
BROAD_PATTERNS = {
    "scott_colom": re.compile(r"^mississippian?s?(?:'s|')?$|^mississippi(?:'s)?$"),
    "abdul_el_sayed": re.compile(r"^(?:michigan|michigander|michiganian)s?(?:'s|')?$"),
}
PREFIX_CHECK = {
    "scott_colom": re.compile(r"^missis"),
    "abdul_el_sayed": re.compile(r"^michig"),
}

BENCH_PATTERNS = {
    "america": re.compile(r"^americans?(?:'s)?$|^america(?:'s)?$"),
    "trump": re.compile(r"^trump(?:'s)?$"),
    "healthcare_medicare": re.compile(r"^(?:healthcare|medicare)$"),
    "senate_senator": re.compile(r"^senators?(?:'s)?$|^senate(?:'s)?$"),
}

# Unambiguous sub-state geography phrases/tokens (strictly excluding terms containing Mississippi/Michigan)
SUBSTATE_PHRASES = {
    "scott_colom": {
        ("gulf", "coast"): "gulf coast",
        ("golden", "triangle"): "golden triangle",
        ("pine", "belt"): "pine belt",
        ("natchez", "trace"): "natchez trace",
        ("mound", "bayou"): "mound bayou",
        ("mount", "bayou"): "mound bayou",
        ("ole", "miss"): "ole miss",
        ("the", "delta"): "the delta",
        ("hinds", "county"): "hinds county",
        ("hines", "county"): "hinds county",
        ("hancock", "county"): "hancock county",
        ("harrison", "county"): "harrison county",
        ("george", "county"): "george county",
        ("holmes", "county"): "holmes county",
        ("rankin", "county"): "rankin county",
        ("desoto", "county"): "desoto county",
        ("lowndes", "county"): "lowndes county",
        ("lee", "county"): "lee county",
        ("forrest", "county"): "forrest county",
        ("bolivar", "county"): "bolivar county",
        ("leflore", "county"): "leflore county",
        ("coahoma", "county"): "coahoma county",
        ("sunflower", "county"): "sunflower county",
        ("lafayette", "county"): "lafayette county",
        ("oktibbeha", "county"): "oktibbeha county",
        ("neshoba", "county"): "neshoba county",
        ("madison", "county"): "madison county",
        ("jackson", "state"): "jackson state",
        ("alcorn", "state"): "alcorn state",
        ("tougaloo", "college"): "tougaloo college",
    },
    "abdul_el_sayed": {
        ("sault", "ste", "marie"): "sault ste. marie",
        ("ann", "arbor"): "ann arbor",
        ("grand", "rapids"): "grand rapids",
        ("east", "lansing"): "east lansing",
        ("traverse", "city"): "traverse city",
        ("bay", "city"): "bay city",
        ("battle", "creek"): "battle creek",
        ("royal", "oak"): "royal oak",
        ("farmington", "hills"): "farmington hills",
        ("benton", "harbor"): "benton harbor",
        ("east", "jordan"): "east jordan",
        ("upper", "peninsula"): "upper peninsula",
        ("up", "north"): "up north",
        ("metro", "detroit"): "metro detroit",
        ("motor", "city"): "motor city",
        ("great", "lakes"): "great lakes",
        ("lake", "huron"): "lake huron",
        ("lake", "superior"): "lake superior",
        ("lake", "erie"): "lake erie",
        ("oakland", "county"): "oakland county",
        ("wayne", "county"): "wayne county",
        ("macomb", "county"): "macomb county",
        ("washtenaw", "county"): "washtenaw county",
        ("genesee", "county"): "genesee county",
        ("kent", "county"): "kent county",
        ("ingham", "county"): "ingham county",
        ("ottawa", "county"): "ottawa county",
        ("montcalm", "county"): "montcalm county",
        ("shiawassee", "county"): "shiawassee county",
    },
}

SUBSTATE_UNIGRAMS = {
    "scott_colom": {
        "jackson": "jackson",
        "tupelo": "tupelo",
        "columbus": "columbus",
        "hattiesburg": "hattiesburg",
        "biloxi": "biloxi",
        "gulfport": "gulfport",
        "meridian": "meridian",
        "vicksburg": "vicksburg",
        "natchez": "natchez",
        "starkville": "starkville",
        "clarksdale": "clarksdale",
        "greenville": "greenville",
        "greenwood": "greenwood",
        "corinth": "corinth",
        "pascagoula": "pascagoula",
        "laurel": "laurel",
        "mccomb": "mccomb",
        "yazoo": "yazoo",
        "woodville": "woodville",
        "ripley": "ripley",
        "oktibbeha": "oktibbeha county",
        "neshoba": "neshoba county",
        "tougaloo": "tougaloo",
        "hinds": "hinds county",
        "lowndes": "lowndes county",
    },
    "abdul_el_sayed": {
        "detroit": "detroit",
        "detroiter": "detroit",
        "detroiters": "detroit",
        "detroit's": "detroit",
        "flint": "flint",
        "flint's": "flint",
        "lansing": "lansing",
        "dearborn": "dearborn",
        "kalamazoo": "kalamazoo",
        "saginaw": "saginaw",
        "pontiac": "pontiac",
        "ypsilanti": "ypsilanti",
        "muskegon": "muskegon",
        "marquette": "marquette",
        "hamtramck": "hamtramck",
        "southfield": "southfield",
        "livonia": "livonia",
        "bloomfield": "bloomfield",
        "macomb": "macomb",
        "washtenaw": "washtenaw",
        "mackinac": "mackinac",
        "ferndale": "ferndale",
        "inkster": "inkster",
        "alpena": "alpena",
        "petoskey": "petoskey",
        "escanaba": "escanaba",
        "houghton": "houghton",
        "midland": "midland",
        "wolverine": "wolverine",
        "wolverines": "wolverine",
        "montcalm": "montcalm",
        "shiawassee": "shiawassee",
        "genesee": "genesee",
        "ingham": "ingham",
    },
}


def count_substate_geo(tokens: list[str], cand_key: str) -> tuple[int, dict[str, int]]:
    """Non-overlapping longest-match counter for unambiguous in-state cities/counties/regions."""
    phrases = SUBSTATE_PHRASES[cand_key]
    unigrams = SUBSTATE_UNIGRAMS[cand_key]
    counts: dict[str, int] = {}
    i = 0
    n = len(tokens)
    while i < n:
        matched = None
        step = 1
        if i + 3 <= n:
            tri = (tokens[i], tokens[i + 1], tokens[i + 2])
            if tri in phrases:
                matched = phrases[tri]
                step = 3
        if matched is None and i + 2 <= n:
            bi = (tokens[i], tokens[i + 1])
            if bi in phrases:
                matched = phrases[bi]
                step = 2
        if matched is None:
            uni = tokens[i]
            if uni in unigrams:
                if cand_key == "scott_colom" and uni == "jackson" and i > 0 and tokens[i - 1] in {
                    "jesse", "andrew", "lamar", "troy", "ketanji", "michael", "janet", "bo"
                }:
                    matched = None
                else:
                    matched = unigrams[uni]
                step = 1
        if matched is not None:
            counts[matched] = counts.get(matched, 0) + 1
        i += step
    return sum(counts.values()), counts


def norm_token(raw: str) -> str:
    s = raw.strip().lower().replace("\u2019", "'").replace("\u2018", "'")
    s = re.sub(r"^[^a-z0-9']+|[^a-z0-9']+$", "", s)
    return s


def fmt_mmss(sec: float) -> str:
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m:02d}:{s:02d}"


def split_utterances(
    segments: list[dict],
    pause_thresh: float = 0.35,
    sent_min_dur: float = 1.8,
    q_min_dur: float = 0.0,
    max_dur: float = 6.0,
) -> list[dict]:
    utts = []

    def flush_cur(cur_words: list[dict]) -> None:
        if not cur_words:
            return
        utts.append({
            "start": float(cur_words[0]["start"]),
            "end": float(cur_words[-1]["end"]),
            "text": "".join(x["word"] for x in cur_words).strip(),
            "words": cur_words,
        })

    cur = []
    for seg in segments:
        words = seg.get("words") or []
        if not words:
            flush_cur(cur)
            cur = []
            utts.append({
                "start": float(seg["start"]),
                "end": float(seg["end"]),
                "text": seg["text"].strip(),
                "words": [],
            })
            continue
        for w in words:
            if not cur:
                cur = [w]
                continue
            prev_end = float(cur[-1]["end"])
            cur_start = float(cur[0]["start"])
            w_start = float(w["start"])
            w_end = float(w["end"])
            prev_txt = cur[-1]["word"].strip()
            gap_split = (w_start - prev_end) >= pause_thresh or (w_start < prev_end)
            q_split = prev_txt.endswith("?") and (prev_end - cur_start) >= q_min_dur
            sent_split = prev_txt.endswith((".", "!")) and (prev_end - cur_start) >= sent_min_dur
            dur_split = (w_end - cur_start) > max_dur
            if gap_split or q_split or sent_split or dur_split:
                flush_cur(cur)
                cur = [w]
            else:
                cur.append(w)
    flush_cur(cur)
    return [u for u in utts if u["text"]]


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


def filter_to_kept_clusters(
    utts: list[dict],
    threshold: float,
    min_speech_sec: float = 55.0,
    multi_cluster_min_density: float = 0.25,
) -> tuple[list[dict], float, list[dict], set[int]]:
    pos_utts = [(idx, u) for idx, u in enumerate(utts) if u["sim"] >= threshold]
    active_sec, cluster_info = compute_active_appearance_sec(
        [u for _, u in pos_utts],
        min_speech_sec=min_speech_sec,
        multi_cluster_min_density=multi_cluster_min_density,
    )
    kept_ranges = [(c["start"] - 0.05, c["end"] + 0.05) for c in cluster_info if c["kept"]]
    kept_idxs = {
        idx for idx, u in pos_utts
        if any(r0 <= u["start"] and u["end"] <= r1 for r0, r1 in kept_ranges)
    }
    cand_utts = [utts[idx] for idx, _ in pos_utts if idx in kept_idxs]
    return cand_utts, active_sec, cluster_info, kept_idxs


def compute_active_appearance_sec(
    cand_utts: list[dict],
    min_speech_sec: float = 55.0,
    multi_cluster_min_density: float = 0.25,
) -> tuple[float, list[dict]]:
    """Cluster candidate utterances (gap <= 180s) and filter stray/low-density non-interview clusters."""
    if not cand_utts:
        return 0.0, []
    utts = sorted(cand_utts, key=lambda u: u["start"])
    clusters = []
    cur = [utts[0]]
    for u in utts[1:]:
        if u["start"] - cur[-1]["end"] <= 180.0:
            cur.append(u)
        else:
            clusters.append(cur)
            cur = [u]
    clusters.append(cur)

    raw_stats = []
    for cl in clusters:
        speech_sec = sum(u["end"] - u["start"] for u in cl)
        span_sec = cl[-1]["end"] - cl[0]["start"]
        density = speech_sec / max(1.0, span_sec)
        raw_stats.append((cl[0]["start"], cl[-1]["end"], span_sec, speech_sec, density))

    qual_idxs = [i for i, (_, _, _, sp, _) in enumerate(raw_stats) if sp >= min_speech_sec]
    kept_set = set()
    if len(qual_idxs) > 1:
        for i in qual_idxs:
            if raw_stats[i][4] >= multi_cluster_min_density:
                kept_set.add(i)
        if not kept_set:
            best_i = max(qual_idxs, key=lambda i: raw_stats[i][3])
            kept_set.add(best_i)
    elif len(qual_idxs) == 1:
        kept_set.add(qual_idxs[0])

    total_active = 0.0
    cluster_info = []
    for i, (s0, s1, span_sec, speech_sec, density) in enumerate(raw_stats):
        kept = i in kept_set
        if kept:
            total_active += span_sec
        cluster_info.append({
            "start": round(s0, 2),
            "end": round(s1, 2),
            "span_sec": round(span_sec, 2),
            "cand_speech_sec": round(speech_sec, 2),
            "density": round(density, 3),
            "kept": kept,
        })
    return total_active, cluster_info


def parse_single_rev(
    paras: list[str],
    url: str,
    cand_key: str,
    speaker_prefix: str,
    known_dur_sec: float | None,
    label: str = "",
) -> dict:
    speaker_re = re.compile(r"^(.+?)\s*\(\s*\d{1,2}:\d{2}(?::\d{2})?\s*\)\s*:$")
    inline_ts_re = re.compile(r"^\(\s*\d{1,2}:\d{2}(?::\d{2})?\s*\)\s*")
    current_speaker = None
    seen_target = False
    kept = []
    for p in paras:
        if seen_target and (p.startswith("Luckily for you") or p.startswith("\u200d")):
            break
        m = speaker_re.match(p.strip())
        if m:
            current_speaker = m.group(1).strip()
            if current_speaker.startswith(speaker_prefix):
                seen_target = True
            continue
        if not seen_target or not current_speaker or not current_speaker.startswith(speaker_prefix):
            continue
        cleaned = inline_ts_re.sub("", p).strip()
        if cleaned:
            kept.append(cleaned)
    text = " ".join(kept)
    tokens = [norm_token(t) for t in text.split()]
    tokens = [t for t in tokens if t]
    strict_hits = sum(1 for t in tokens if STRICT_PATTERNS[cand_key].match(t))
    broad_hits = sum(1 for t in tokens if BROAD_PATTERNS[cand_key].match(t))
    hc_hits = sum(1 for t in tokens if BENCH_PATTERNS["healthcare_medicare"].match(t))
    hc_hits += sum(1 for i in range(len(tokens) - 1) if tokens[i] == "health" and tokens[i + 1] == "care")
    sub_hits, sub_bd = count_substate_geo(tokens, cand_key)
    out = {
        "label": label,
        "speaker": speaker_prefix,
        "url": url,
        "paragraph_count": len(kept),
        "word_count": len(tokens),
        "strict_mentions": strict_hits,
        "broad_mentions": broad_hits,
        "per_1k_words_strict": round(1000.0 * strict_hits / len(tokens), 2) if tokens else 0.0,
        "per_1k_words_broad": round(1000.0 * broad_hits / len(tokens), 2) if tokens else 0.0,
        "substate_geo_mentions": sub_hits,
        "per_1k_words_substate_geo": round(1000.0 * sub_hits / len(tokens), 2) if tokens else 0.0,
        "substate_geo_breakdown": sub_bd,
        "america_mentions": sum(1 for t in tokens if BENCH_PATTERNS["america"].match(t)),
        "trump_mentions": sum(1 for t in tokens if BENCH_PATTERNS["trump"].match(t)),
        "healthcare_medicare_mentions": hc_hits,
        "senate_senator_mentions": sum(1 for t in tokens if BENCH_PATTERNS["senate_senator"].match(t)),
    }
    if known_dur_sec:
        out["approx_video_duration_sec"] = known_dur_sec
        out["approx_per_hour_strict"] = round(strict_hits / (known_dur_sec / 3600.0), 2)
    return out


def parse_rev_transcripts() -> tuple[dict, dict]:
    rev_path = DATA_DIR / "victory_speeches_rev.json"
    rev_victory = {}
    rev_all = {}
    if rev_path.exists():
        raw = json.loads(rev_path.read_text())
        for cand, speaker_prefix, known_dur_sec, key, lbl in [
            ("scott_colom", "Scott Colom", 970.0, "colom_victory", "Scott Colom Victory Speech (Nov 2026)"),
            ("abdul_el_sayed", "Abdul El-Sayed", 1210.0, "abdul_victory", "Abdul El-Sayed Victory Speech (Nov 2026)"),
        ]:
            d = parse_single_rev(
                raw.get(cand, {}).get("paragraphs", []),
                raw.get(cand, {}).get("url", ""),
                cand,
                speaker_prefix,
                known_dur_sec,
                lbl,
            )
            rev_victory[cand] = d
            rev_all[key] = d

    extra_path = DATA_DIR / "rev_extra_transcripts.json"
    if extra_path.exists():
        ext = json.loads(extra_path.read_text())
        if "abdul_detroit_forum" in ext:
            item = ext["abdul_detroit_forum"]
            rev_all["abdul_detroit_forum"] = parse_single_rev(
                item["paragraphs"], item["url"], "abdul_el_sayed", "Abdul El-Sayed", None,
                "Detroit Economic Club Q&A — Abdul El-Sayed (Oct 21)",
            )
            rev_all["rogers_detroit_forum"] = parse_single_rev(
                item["paragraphs"], item["url"], "abdul_el_sayed", "Mike Rogers", None,
                "Detroit Economic Club Q&A — Mike Rogers (Oct 21)",
            )
        if "abdul_primary_presser" in ext:
            item = ext["abdul_primary_presser"]
            rev_all["abdul_primary_presser"] = parse_single_rev(
                item["paragraphs"], item["url"], "abdul_el_sayed", "Abdul El-Sayed", None,
                "MI Primary Victory Press Conf — Abdul El-Sayed (Aug 6)",
            )
    return rev_victory, rev_all


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tau-colom", type=float, required=True)
    parser.add_argument("--tau-abdul", type=float, required=True)
    parser.add_argument("--adjudications", type=str, default=None)
    args = parser.parse_args()

    adjudications = {}
    if args.adjudications and Path(args.adjudications).exists():
        adjudications = json.loads(Path(args.adjudications).read_text())
        print(f"Loaded {len(adjudications)} manual mention adjudications from {args.adjudications}")

    taus = {"scott_colom": args.tau_colom, "abdul_el_sayed": args.tau_abdul}
    vps = np.load(DATA_DIR / "voiceprints.npz")
    centroids = {k: vps[k] for k in ["scott_colom", "abdul_el_sayed"]}

    fe = AutoFeatureExtractor.from_pretrained("microsoft/wavlm-base-plus-sv")
    sv = WavLMForXVector.from_pretrained("microsoft/wavlm-base-plus-sv").cuda().eval()

    manifest = json.loads((DATA_DIR / "rss_corpus_manifest.json").read_text())
    excluded_path = DATA_DIR / "excluded_episodes.json"
    excluded = json.loads(excluded_path.read_text()) if excluded_path.exists() else {}

    appearances = []
    all_mentions = []
    non_cand_mentions = []
    prefix_edge_cases = []

    for item in manifest:
        eid = item["episode_id"]
        cand = item["candidate"]
        if eid in EXPLICIT_EXCLUDED:
            excluded[eid] = {
                **item,
                "reason": EXPLICIT_EXCLUDED[eid],
            }
            print(f"  [EXPLICIT EXCLUDE] {eid}: {EXPLICIT_EXCLUDED[eid]}")
            continue
        tpath = TRANS_DIR / f"{eid}.json"
        if not tpath.exists():
            continue
        tdata = json.loads(tpath.read_text())
        audio, sr = sf.read(str(AUDIO_DIR / f"{eid}.wav"), dtype="float32")
        utts = split_utterances(tdata.get("segments", []), pause_thresh=0.35, sent_min_dur=1.8, q_min_dur=0.0, max_dur=6.0)

        # Score utterances without batch zero-padding
        chunks = []
        valid_idxs = []
        for idx, u in enumerate(utts):
            dur = u["end"] - u["start"]
            if dur < 0.30:
                continue
            if dur < 1.5:
                pad = (1.6 - dur) / 2.0
                s_i = max(0, int((u["start"] - pad) * sr))
                e_i = min(len(audio), int((u["end"] + pad) * sr))
            else:
                s_i = max(0, int(u["start"] * sr))
                e_i = min(len(audio), int(min(u["end"], u["start"] + 6.5) * sr))
            ch = audio[s_i:e_i]
            if len(ch) >= int(0.6 * sr) and float(np.sqrt(np.mean(ch * ch))) >= 0.003:
                chunks.append(ch)
                valid_idxs.append(idx)

        embs = embed_chunks_nopad(chunks, fe, sv, batch_size=24)
        sims = embs @ centroids[cand] if len(embs) else np.zeros((0,))
        for idx, sim in zip(valid_idxs, sims):
            utts[idx]["sim_raw"] = float(sim)

        scored_set = set(valid_idxs)
        tau = taus[cand]
        for idx, u in enumerate(utts):
            if idx not in scored_set:
                u["short_unscored"] = True
                u["sim_raw"] = 0.0

        # Monologue continuity smoothing for short (<2.5s) dips sandwiched within 1.2s between >=tau turns
        for idx, u in enumerate(utts):
            dur = u["end"] - u["start"]
            if dur < 2.5 and u["sim_raw"] < tau:
                p = next((k for k in range(idx - 1, -1, -1) if (utts[k]["end"] - utts[k]["start"]) >= 1.5), None)
                n = next((k for k in range(idx + 1, len(utts)) if (utts[k]["end"] - utts[k]["start"]) >= 1.5), None)
                if (
                    p is not None
                    and n is not None
                    and (u["start"] - utts[p]["end"]) <= 1.2
                    and (utts[n]["start"] - u["end"]) <= 1.2
                    and utts[p]["sim_raw"] >= tau
                    and utts[n]["sim_raw"] >= tau
                ):
                    u["sim"] = max(u["sim_raw"], 0.5 * (utts[p]["sim_raw"] + utts[n]["sim_raw"]))
                else:
                    u["sim"] = u["sim_raw"]
            else:
                u["sim"] = u["sim_raw"]

        # Filter positive candidate turns to kept (>=30s speech) interview clusters
        cand_utts, active_sec, cluster_info, kept_idxs = filter_to_kept_clusters(utts, tau)
        for idx, u in enumerate(utts):
            in_kept = idx in kept_idxs
            u["is_candidate"] = in_kept
            u["outside_kept_cluster"] = bool(u["sim"] >= tau and not in_kept)

        cand_speech_sec = sum(u["end"] - u["start"] for u in cand_utts)

        if cand_speech_sec < 60.0:
            excluded[eid] = {
                **item,
                "reason": "verified_candidate_speech_under_60s",
                "verified_cand_speech_sec": round(cand_speech_sec, 2),
                "max_utt_sim": round(max((u["sim"] for u in utts), default=0.0), 4),
            }
            print(f"  [AUTO-PRUNE <60s] {eid}: cand_speech={cand_speech_sec:.1f}s (max_sim={excluded[eid]['max_utt_sim']})")
            continue
        excluded.pop(eid, None)

        # Flatten all words across utterances for context and mention detection
        flat_words = []
        for u_idx, u in enumerate(utts):
            for w in u["words"]:
                flat_words.append({
                    "norm": norm_token(w["word"]),
                    "raw": w["word"].strip(),
                    "start": float(w["start"]),
                    "end": float(w["end"]),
                    "u_idx": u_idx,
                    "u_sim": u["sim"],
                    "is_candidate": u["is_candidate"],
                    "outside_kept_cluster": u["outside_kept_cluster"],
                })

        # Compute local exact-3.0s (48000-sample) embedding for EVERY state-name mention
        mention_indices = []
        for wi, fw in enumerate(flat_words):
            tok = fw["norm"]
            is_strict = bool(STRICT_PATTERNS[cand].match(tok))
            is_broad = bool(BROAD_PATTERNS[cand].match(tok))
            if PREFIX_CHECK[cand].match(tok) and not is_broad:
                prefix_edge_cases.append({"episode_id": eid, "token": tok, "raw": fw["raw"], "ts": fmt_mmss(fw["start"])})
            if is_broad:
                mention_indices.append((wi, is_strict, is_broad))

        WIN = 3 * sr
        local_chunks = []
        for wi, _, _ in mention_indices:
            fw = flat_words[wi]
            mid_sample = int(0.5 * (fw["start"] + fw["end"]) * sr)
            if len(audio) <= WIN:
                s_i, e_i = 0, len(audio)
            else:
                s_i = mid_sample - WIN // 2
                if s_i < 0:
                    s_i = 0
                elif s_i + WIN > len(audio):
                    s_i = len(audio) - WIN
                e_i = s_i + WIN
            local_chunks.append(audio[s_i:e_i])
        local_embs = embed_chunks_nopad(local_chunks, fe, sv, batch_size=24)
        local_sims = local_embs @ centroids[cand] if len(local_embs) else np.zeros((0,))

        raw_ep_strict_cand = 0
        raw_ep_broad_cand = 0
        ep_strict_cand = 0
        ep_broad_cand = 0
        ep_strict_noncand = 0
        ep_broad_noncand = 0

        for (wi, is_strict, is_broad), lsim in zip(mention_indices, local_sims):
            fw = flat_words[wi]
            lsim = float(lsim)
            ctx_words = [flat_words[k]["raw"] for k in range(max(0, wi - 12), min(len(flat_words), wi + 13))]
            ctx = " ".join(ctx_words)
            raw_is_cand = bool(fw["is_candidate"])
            if raw_is_cand:
                if is_strict:
                    raw_ep_strict_cand += 1
                raw_ep_broad_cand += 1

            ts_r = round(fw["start"], 2)
            adj_key = f"{eid}|{ts_r:.2f}|{fw['norm']}"
            adj_entry = adjudications.get(adj_key)
            final_is_cand = raw_is_cand
            adjudicated = False
            adj_reason = ""
            if adj_entry:
                dec = adj_entry.get("decision")
                if dec == "flip_to_candidate" and not raw_is_cand:
                    final_is_cand = True
                    adjudicated = True
                    adj_reason = adj_entry.get("reason", "")
                elif dec == "flip_to_non_candidate" and raw_is_cand:
                    final_is_cand = False
                    adjudicated = True
                    adj_reason = adj_entry.get("reason", "")

            disagree = raw_is_cand != (lsim >= tau)
            borderline = abs(fw["u_sim"] - tau) <= 0.03 or abs(lsim - tau) <= 0.03
            rec = {
                "episode_id": eid,
                "candidate": cand,
                "show": item["show"],
                "title": item["title"],
                "pub_date": item["pub_date"],
                "category": item["category"],
                "period": item["period"],
                "timestamp_sec": ts_r,
                "timestamp_mmss": fmt_mmss(fw["start"]),
                "matched_term": fw["norm"],
                "is_strict": is_strict,
                "is_broad": is_broad,
                "sim_utterance": round(fw["u_sim"], 4),
                "sim_local": round(lsim, 4),
                "tau": tau,
                "raw_acoustic_is_candidate": raw_is_cand,
                "is_candidate": final_is_cand,
                "adjudicated": adjudicated,
                "adjudication_reason": adj_reason,
                "outside_kept_cluster": fw["outside_kept_cluster"],
                "borderline_or_disagree": bool(borderline or disagree),
                "context": ctx,
            }
            if final_is_cand:
                if is_strict:
                    ep_strict_cand += 1
                ep_broad_cand += 1
                all_mentions.append(rec)
            else:
                if is_strict:
                    ep_strict_noncand += 1
                ep_broad_noncand += 1
                non_cand_mentions.append(rec)

        # Sensitivity thresholds (tau - 0.03, tau + 0.03) with kept-cluster filtering
        sens_counts = {}
        for tag, delta in [("lo", -0.03), ("mid", 0.0), ("hi", 0.03)]:
            t_val = tau + delta
            min_sp = 30.0 if tag == "hi" else 55.0
            sub_utts, _, _, _ = filter_to_kept_clusters(utts, t_val, min_speech_sec=min_sp)
            sub_sec = sum(u["end"] - u["start"] for u in sub_utts)
            sub_words = [norm_token(w["word"]) for u in sub_utts for w in u["words"]]
            sub_words = [w for w in sub_words if w]
            s_hits = sum(1 for w in sub_words if STRICT_PATTERNS[cand].match(w))
            b_hits = sum(1 for w in sub_words if BROAD_PATTERNS[cand].match(w))
            sens_counts[tag] = {
                "speech_sec": round(sub_sec, 2),
                "words": len(sub_words),
                "strict_mentions": s_hits,
                "broad_mentions": b_hits,
            }

        # Candidate word count, benchmark words, and sub-state geography at primary tau
        cand_tokens = [norm_token(w["word"]) for u in cand_utts for w in u["words"]]
        cand_tokens = [w for w in cand_tokens if w]
        hc_hits = sum(1 for w in cand_tokens if BENCH_PATTERNS["healthcare_medicare"].match(w))
        hc_hits += sum(1 for i in range(len(cand_tokens) - 1) if cand_tokens[i] == "health" and cand_tokens[i + 1] == "care")
        sub_geo_hits, sub_geo_bd = count_substate_geo(cand_tokens, cand)

        all_tokens = [fw["norm"] for fw in flat_words if fw["norm"]]

        appearances.append({
            "episode_id": eid,
            "candidate": cand,
            "show": item["show"],
            "title": item["title"],
            "pub_date": item["pub_date"],
            "category": item["category"],
            "period": item["period"],
            "is_full_broadcast": item["is_full_broadcast"],
            "matched_venue": item.get("matched_venue", ""),
            "audio_duration_sec": tdata["audio_duration_sec"],
            "transcribed_duration_sec": tdata["transcribed_duration_sec"],
            "active_appearance_sec": round(active_sec, 2),
            "cand_speaking_sec": round(cand_speech_sec, 2),
            "cand_words": len(cand_tokens),
            "total_window_words": len(all_tokens),
            "raw_acoustic_strict_mentions": raw_ep_strict_cand,
            "raw_acoustic_broad_mentions": raw_ep_broad_cand,
            "strict_mentions": ep_strict_cand,
            "broad_mentions": ep_broad_cand,
            "noncand_strict_mentions": ep_strict_noncand,
            "noncand_broad_mentions": ep_broad_noncand,
            "substate_geo_mentions": sub_geo_hits,
            "substate_geo_breakdown": sub_geo_bd,
            "rate_per_speaking_hr_strict": round(ep_strict_cand / (cand_speech_sec / 3600.0), 2),
            "rate_per_active_hr_strict": round(ep_strict_cand / (active_sec / 3600.0), 2) if active_sec > 0 else 0.0,
            "rate_per_1k_words_strict": round(1000.0 * ep_strict_cand / len(cand_tokens), 2) if cand_tokens else 0.0,
            "rate_per_speaking_hr_substate_geo": round(sub_geo_hits / (cand_speech_sec / 3600.0), 2),
            "rate_per_speaking_hr_combined_local": round((ep_strict_cand + sub_geo_hits) / (cand_speech_sec / 3600.0), 2),
            "bench_america": sum(1 for w in cand_tokens if BENCH_PATTERNS["america"].match(w)),
            "bench_trump": sum(1 for w in cand_tokens if BENCH_PATTERNS["trump"].match(w)),
            "bench_healthcare_medicare": hc_hits,
            "bench_senate_senator": sum(1 for w in cand_tokens if BENCH_PATTERNS["senate_senator"].match(w)),
            "sensitivity": sens_counts,
            "cluster_info": cluster_info,
        })

    excluded_path.write_text(json.dumps(excluded, indent=2))
    rev_speeches, rev_all = parse_rev_transcripts()

    analysis = {
        "taus": taus,
        "adjudications_applied": len(adjudications),
        "appearances": appearances,
        "candidate_mentions": all_mentions,
        "non_candidate_mentions": non_cand_mentions,
        "prefix_edge_cases": prefix_edge_cases,
        "rev_victory_speeches": rev_speeches,
        "rev_all_transcripts": rev_all,
    }
    (DATA_DIR / "analysis_results.json").write_text(json.dumps(analysis, indent=2))

    # Print summary & borderline audit log
    for cand in ["scott_colom", "abdul_el_sayed"]:
        sub = [a for a in appearances if a["candidate"] == cand]
        hrs = sum(a["cand_speaking_sec"] for a in sub) / 3600.0
        act_hrs = sum(a["active_appearance_sec"] for a in sub) / 3600.0
        sm = sum(a["strict_mentions"] for a in sub)
        bm = sum(a["broad_mentions"] for a in sub)
        nc = sum(a["noncand_strict_mentions"] for a in sub)
        print(f"SUMMARY {cand}: N={len(sub)} eps | speak_hrs={hrs:.2f} | active_hrs={act_hrs:.2f} | strict={sm} ({sm/hrs:.1f}/hr) | broad={bm} ({bm/hrs:.1f}/hr) | filtered_noncand_strict={nc}")

    print(f"\nPrefix edge cases (missis*/michig* not matched): {prefix_edge_cases}")
    border_all = [m for m in all_mentions + non_cand_mentions if m["borderline_or_disagree"] and m["is_strict"]]
    print(f"Borderline/disagree strict mentions ({len(border_all)} total):")
    for m in border_all[:40]:
        tag = "CAND" if m["is_candidate"] else "NON "
        print(f"  [{tag}] {m['episode_id']} {m['timestamp_mmss']} utt={m['sim_utterance']:.3f} loc={m['sim_local']:.3f} | {m['context']}")


if __name__ == "__main__":
    main()
