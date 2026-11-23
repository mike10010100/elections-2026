#!/usr/bin/env python3
"""Step 4: Cohort-centered WavLM-SV + Resemblyzer turn attribution, homophone guard, and mention audit."""

import argparse
import json
import re
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torch.nn.functional as F
from resemblyzer import VoiceEncoder
from transformers import AutoFeatureExtractor, WavLMForXVector

PF_DIR = Path("/home/mike10010100/state-name-analysis/platner_fetterman")
DATA_DIR = PF_DIR / "data"
AUDIO_DIR = PF_DIR / "audio"
TRANS_DIR = PF_DIR / "transcripts"
OUT_DIR = PF_DIR / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

EXPLICIT_EXCLUDED: dict[str, str] = {
    "gp_11th_hour_velshi_20260605": "duplicate_replay_of_gp_all_in_hayes_20260605_jaccard_0.652",
}

STRICT_ME_RE = re.compile(r"^Maine(?:'s)?$")
BROAD_MAINER_RE = re.compile(r"^Maine+rs?(?:'s|')?$", re.IGNORECASE)
MAINE_HOMOPHONE_NEXT = {"street", "st", "thing", "reason", "point", "idea", "issue", "question", "event", "stream", "line", "frame", "stay"}
MAIN_PREV_CUES = {
    "in", "from", "of", "across", "rural", "coastal", "eastern", "northern",
    "southern", "western", "central", "senator", "state", "people", "governor",
    "vote", "for", "to", "leave", "leaving", "save", "throughout",
}
MAIN_TRAP_RE = re.compile(r"^main(?:'s|s)?$")
MANOR_TRAP_RE = re.compile(r"^(?:manor|manner)s?(?:'s)?$")

STRICT_PA_RE = re.compile(r"^pennsylvania(?:'s)?$")
BROAD_PA_RE = re.compile(r"^(?:pennsylvania|pennsylvanian)s?(?:'s|')?$")
PA_ABBR_RE = re.compile(r"^(?:PA|P\.A\.)(?:'s)?$")

PREFIX_CHECKS = {
    "graham_platner": re.compile(r"^maine"),
    "john_fetterman": re.compile(r"^pennsyl"),
}

BENCH_PATTERNS = {
    "america": re.compile(r"^americans?(?:'s)?$|^america(?:'s)?$"),
    "trump": re.compile(r"^trump(?:'s)?$"),
    "healthcare_medicare": re.compile(r"^(?:healthcare|medicare)$"),
    "senate_senator": re.compile(r"^senators?(?:'s)?$|^senate(?:'s)?$"),
}

SUBSTATE_PHRASES = {
    "graham_platner": {
        ("bar", "harbor"): "bar harbor",
        ("mount", "desert"): "mount desert",
        ("down", "east"): "downeast",
        ("mid", "coast"): "midcoast",
        ("old", "town"): "old town",
        ("blue", "hill"): "blue hill",
        ("hancock", "county"): "hancock county",
        ("aroostook", "county"): "aroostook county",
        ("penobscot", "county"): "penobscot county",
        ("cumberland", "county"): "cumberland county",
        ("york", "county"): "york county",
        ("kennebec", "county"): "kennebec county",
        ("androscoggin", "county"): "androscoggin county",
        ("washington", "county"): "washington county",
        ("waldo", "county"): "waldo county",
        ("knox", "county"): "knox county",
        ("oxford", "county"): "oxford county",
        ("somerset", "county"): "somerset county",
        ("piscataquis", "county"): "piscataquis county",
        ("south", "portland"): "south portland",
        ("presque", "isle"): "presque isle",
        ("deer", "isle"): "deer isle",
        ("boothbay", "harbor"): "boothbay harbor",
        ("bath", "iron"): "bath iron works",
        ("casco", "bay"): "casco bay",
    },
    "john_fetterman": {
        ("lehigh", "valley"): "lehigh valley",
        ("allegheny", "county"): "allegheny county",
        ("bucks", "county"): "bucks county",
        ("montgomery", "county"): "montgomery county",
        ("delaware", "county"): "delaware county",
        ("chester", "county"): "chester county",
        ("lancaster", "county"): "lancaster county",
        ("york", "county"): "york county",
        ("berks", "county"): "berks county",
        ("luzerne", "county"): "luzerne county",
        ("lackawanna", "county"): "lackawanna county",
        ("erie", "county"): "erie county",
        ("westmoreland", "county"): "westmoreland county",
        ("beaver", "county"): "beaver county",
        ("butler", "county"): "butler county",
        ("washington", "county"): "washington county",
        ("centre", "county"): "centre county",
        ("state", "college"): "state college",
        ("penn", "state"): "penn state",
        ("central", "pa"): "central pa",
        ("western", "pa"): "western pa",
        ("eastern", "pa"): "eastern pa",
        ("steel", "city"): "steel city",
        ("independence", "hall"): "independence hall",
        ("mon", "valley"): "mon valley",
    },
}

SUBSTATE_UNIGRAMS = {
    "graham_platner": {
        "portland": "portland",
        "bangor": "bangor",
        "lewiston": "lewiston",
        "augusta": "augusta",
        "aroostook": "aroostook",
        "downeast": "downeast",
        "midcoast": "midcoast",
        "sullivan": "sullivan",
        "ellsworth": "ellsworth",
        "rockland": "rockland",
        "brunswick": "brunswick",
        "biddeford": "biddeford",
        "saco": "saco",
        "sanford": "sanford",
        "waterville": "waterville",
        "caribou": "caribou",
        "houlton": "houlton",
        "machias": "machias",
        "calais": "calais",
        "eastport": "eastport",
        "belfast": "belfast",
        "camden": "camden",
        "kittery": "kittery",
        "kennebunk": "kennebunk",
        "kennebunkport": "kennebunkport",
        "ogunquit": "ogunquit",
        "skowhegan": "skowhegan",
        "farmington": "farmington",
        "rumford": "rumford",
        "millinocket": "millinocket",
        "penobscot": "penobscot",
        "kennebec": "kennebec",
        "androscoggin": "androscoggin",
        "hancock": "hancock",
    },
    "john_fetterman": {
        "philadelphia": "philadelphia",
        "philadelphia's": "philadelphia",
        "philly": "philadelphia",
        "philly's": "philadelphia",
        "pittsburgh": "pittsburgh",
        "pittsburgh's": "pittsburgh",
        "pittsburgher": "pittsburgh",
        "pittsburghers": "pittsburgh",
        "braddock": "braddock",
        "braddock's": "braddock",
        "allentown": "allentown",
        "scranton": "scranton",
        "harrisburg": "harrisburg",
        "erie": "erie",
        "lancaster": "lancaster",
        "bethlehem": "bethlehem",
        "wilkes-barre": "wilkes-barre",
        "altoona": "altoona",
        "johnstown": "johnstown",
        "hazleton": "hazleton",
        "gettysburg": "gettysburg",
        "hershey": "hershey",
        "poconos": "poconos",
        "pocono": "poconos",
        "allegheny": "allegheny",
        "lehigh": "lehigh",
        "susquehanna": "susquehanna",
        "delco": "delco",
        "montco": "montco",
        "chesco": "chesco",
        "yinz": "yinz",
        "yinzer": "yinz",
        "yinzers": "yinz",
        "mckeesport": "mckeesport",
        "duquesne": "duquesne",
        "homestead": "homestead",
        "clairton": "clairton",
        "monongahela": "monongahela",
        "reading": "reading",
    },
}


def clean_raw_preserve_case(raw: str) -> str:
    s = raw.strip().replace("\u2019", "'").replace("\u2018", "'")
    s = re.sub(r"^[^\w']+|[^\w']+$", "", s)
    return s


def norm_token(raw: str) -> str:
    s = raw.strip().lower().replace("\u2019", "'").replace("\u2018", "'")
    s = re.sub(r"^[^a-z0-9'-]+|[^a-z0-9'-]+$", "", s)
    return s


def fmt_mmss(sec: float) -> str:
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m:02d}:{s:02d}"


def count_substate_geo(
    tokens: list[str],
    raw_tokens: list[str],
    cand_key: str,
    eid: str,
    substate_audit: list[dict],
) -> tuple[int, dict[str, int]]:
    phrases = SUBSTATE_PHRASES[cand_key]
    unigrams = SUBSTATE_UNIGRAMS[cand_key]
    counts: dict[str, int] = {}
    i = 0
    n = len(tokens)
    while i < n:
        matched = None
        step = 1
        if i + 2 <= n:
            bi = (tokens[i], tokens[i + 1])
            if bi in phrases:
                matched = phrases[bi]
                step = 2
        if matched is None:
            uni = tokens[i]
            if uni in unigrams:
                prev_t = tokens[i - 1] if i > 0 else ""
                next_t = tokens[i + 1] if i + 1 < n else ""
                raw_t = raw_tokens[i] if i < len(raw_tokens) else ""
                if cand_key == "graham_platner":
                    if uni == "portland" and next_t in {"oregon", "or"}:
                        matched = None
                    elif uni == "augusta" and next_t in {"georgia", "ga", "masters", "national"}:
                        matched = None
                    elif uni == "sullivan" and prev_t in {"jake", "andrew", "dan", "ed", "louie"}:
                        matched = None
                    elif uni in {"york", "washington"} and next_t != "county":
                        matched = None
                    else:
                        matched = unigrams[uni]
                    if uni in {"portland", "augusta", "sullivan", "hancock", "oxford", "camden", "farmington", "brunswick", "belfast"}:
                        ctx = " ".join(raw_tokens[max(0, i - 6) : min(n, i + 7)])
                        substate_audit.append({"episode_id": eid, "cand": cand_key, "term": raw_t, "counted": matched is not None, "ctx": ctx})
                else:
                    if uni == "reading":
                        # Only match capitalized Reading not preceded by verbal cues
                        verb_prev = {"i'm", "am", "is", "are", "was", "were", "been", "started", "start", "kept", "keep", "enjoy", "love", "hate", "done", "finish", "finished", "by"}
                        if raw_t == "Reading" and prev_t not in verb_prev:
                            matched = "reading"
                        else:
                            matched = None
                        ctx = " ".join(raw_tokens[max(0, i - 6) : min(n, i + 7)])
                        substate_audit.append({"episode_id": eid, "cand": cand_key, "term": raw_t, "counted": matched is not None, "ctx": ctx})
                    elif uni in {"york", "washington", "lancaster", "erie"}:
                        if uni == "washington" and next_t != "county":
                            matched = None
                        else:
                            matched = unigrams[uni]
                        if uni in {"york", "lancaster", "erie", "bethlehem", "homestead", "reading"}:
                            ctx = " ".join(raw_tokens[max(0, i - 6) : min(n, i + 7)])
                            substate_audit.append({"episode_id": eid, "cand": cand_key, "term": raw_t, "counted": matched is not None, "ctx": ctx})
                    else:
                        matched = unigrams[uni]
                step = 1
        if matched is not None:
            counts[matched] = counts.get(matched, 0) + 1
        i += step
    return sum(counts.values()), counts


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


def center_norm(arr: np.ndarray, mu_bg: np.ndarray) -> np.ndarray:
    if len(arr) == 0:
        return arr
    x = arr - mu_bg
    norms = np.linalg.norm(x, axis=-1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return x / norms


def compute_active_appearance_sec(
    cand_utts: list[dict],
    min_speech_sec: float = 55.0,
    multi_cluster_min_density: float = 0.25,
) -> tuple[float, list[dict]]:
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


def extract_3s_window(audio: np.ndarray, sr: int, mid_sample: int) -> np.ndarray:
    WIN = 3 * sr
    if len(audio) <= WIN:
        return audio
    s_i = mid_sample - WIN // 2
    if s_i < 0:
        s_i = 0
    elif s_i + WIN > len(audio):
        s_i = len(audio) - WIN
    return audio[s_i : s_i + WIN]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tau-platner", type=float, default=0.68)
    parser.add_argument("--tau-fetterman", type=float, default=0.72)
    parser.add_argument("--tau-res-platner", type=float, default=0.77)
    parser.add_argument("--tau-res-fetterman", type=float, default=0.79)
    parser.add_argument("--adjudications", type=str, default=None)
    args = parser.parse_args()

    adjudications = {}
    if args.adjudications and Path(args.adjudications).exists():
        adjudications = json.loads(Path(args.adjudications).read_text())
        print(f"Loaded {len(adjudications)} manual mention adjudications from {args.adjudications}")

    taus = {"graham_platner": args.tau_platner, "john_fetterman": args.tau_fetterman}
    tau_res = {"graham_platner": args.tau_res_platner, "john_fetterman": args.tau_res_fetterman}

    vps = np.load(DATA_DIR / "voiceprints_pf.npz")
    mu_bg = vps["mu_bg"]
    centroids_cen = {"graham_platner": vps["graham_platner_cen"], "john_fetterman": vps["john_fetterman_cen"]}
    centroids_res = {"graham_platner": vps["graham_platner_res"], "john_fetterman": vps["john_fetterman_res"]}

    fe = AutoFeatureExtractor.from_pretrained("microsoft/wavlm-base-plus-sv")
    sv = WavLMForXVector.from_pretrained("microsoft/wavlm-base-plus-sv").cuda().eval()
    res_enc = VoiceEncoder(device="cuda")

    manifest = json.loads((DATA_DIR / "rss_manifest_pf.json").read_text())
    excluded_path = DATA_DIR / "excluded_episodes.json"
    excluded = json.loads(excluded_path.read_text()) if excluded_path.exists() else {}

    appearances = []
    all_mentions = []
    non_cand_mentions = []
    prefix_edge_cases = []
    homophone_traps = []
    pa_abbr_audit = []
    substate_audit = []

    for item in manifest:
        eid = item["episode_id"]
        cand = item["candidate"]
        if eid in EXPLICIT_EXCLUDED:
            excluded[eid] = {**item, "reason": EXPLICIT_EXCLUDED[eid]}
            print(f"  [EXPLICIT EXCLUDE] {eid}: {EXPLICIT_EXCLUDED[eid]}")
            continue
        tpath = TRANS_DIR / f"{eid}.json"
        if not tpath.exists():
            continue
        tdata = json.loads(tpath.read_text())
        audio, sr = sf.read(str(AUDIO_DIR / f"{eid}.wav"), dtype="float32")
        utts = split_utterances(tdata.get("segments", []), pause_thresh=0.35, sent_min_dur=1.8, q_min_dur=0.0, max_dur=6.0)

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
        sims = center_norm(embs, mu_bg) @ centroids_cen[cand] if len(embs) else np.zeros((0,))
        for idx, sim in zip(valid_idxs, sims):
            utts[idx]["sim_raw"] = float(sim)

        scored_set = set(valid_idxs)
        tau = taus[cand]
        tr = tau_res[cand]
        for idx, u in enumerate(utts):
            if idx not in scored_set:
                u["short_unscored"] = True
                u["sim_raw"] = -1.0

        # Monologue continuity smoothing
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
                "max_utt_sim": round(max((u["sim"] for u in utts), default=-1.0), 4),
            }
            print(f"  [AUTO-PRUNE <60s] {eid}: cand_speech={cand_speech_sec:.1f}s (max_sim={excluded[eid]['max_utt_sim']})")
            continue
        excluded.pop(eid, None)

        flat_words = []
        for u_idx, u in enumerate(utts):
            for w in u["words"]:
                flat_words.append({
                    "norm": norm_token(w["word"]),
                    "clean_raw": clean_raw_preserve_case(w["word"]),
                    "raw": w["word"].strip(),
                    "start": float(w["start"]),
                    "end": float(w["end"]),
                    "u_idx": u_idx,
                    "u_sim": u["sim"],
                    "is_candidate": u["is_candidate"],
                    "outside_kept_cluster": u["outside_kept_cluster"],
                })

        mention_items = []  # (wi, is_strict, is_broad, is_trap_only, trap_reason)
        n_fw = len(flat_words)
        for wi, fw in enumerate(flat_words):
            tok = fw["norm"]
            craw = fw["clean_raw"]
            prev_tok = flat_words[wi - 1]["norm"] if wi > 0 else ""
            next_tok = flat_words[wi + 1]["norm"] if wi + 1 < n_fw else ""

            if cand == "graham_platner":
                is_strict = bool(STRICT_ME_RE.match(craw))
                is_mainer = bool(BROAD_MAINER_RE.match(craw))
                is_broad = is_strict or is_mainer
                if PREFIX_CHECKS[cand].match(tok) and not is_broad:
                    prefix_edge_cases.append({"episode_id": eid, "token": tok, "raw": fw["raw"], "ts": fmt_mmss(fw["start"])})

                if is_strict and next_tok in MAINE_HOMOPHONE_NEXT:
                    mention_items.append((wi, True, True, False, f"Maine+{next_tok}_check"))
                elif is_broad:
                    mention_items.append((wi, is_strict, is_broad, False, ""))
                elif MAIN_TRAP_RE.match(tok):
                    mention_items.append((wi, False, False, True, f"lowercase_{prev_tok}+{tok}"))
                elif MANOR_TRAP_RE.match(tok):
                    mention_items.append((wi, False, False, True, f"manor_manner_trap:{tok}"))
            else:
                is_strict = bool(STRICT_PA_RE.match(tok))
                is_broad = bool(BROAD_PA_RE.match(tok))
                if PREFIX_CHECKS[cand].match(tok) and not is_broad:
                    prefix_edge_cases.append({"episode_id": eid, "token": tok, "raw": fw["raw"], "ts": fmt_mmss(fw["start"])})
                if PA_ABBR_RE.match(craw) or tok in {"pa", "p.a", "p.a.", "pa's"}:
                    ctx_pa = " ".join(flat_words[k]["raw"] for k in range(max(0, wi - 8), min(n_fw, wi + 9)))
                    pa_abbr_audit.append({
                        "episode_id": eid,
                        "ts": fmt_mmss(fw["start"]),
                        "ts_sec": round(fw["start"], 2),
                        "clean_raw": craw,
                        "is_candidate": fw["is_candidate"],
                        "is_upper_pa": bool(PA_ABBR_RE.match(craw)),
                        "context": ctx_pa,
                    })
                if is_broad:
                    mention_items.append((wi, is_strict, is_broad, False, ""))

        local_chunks = []
        for wi, _, _, _, _ in mention_items:
            fw = flat_words[wi]
            mid_sample = int(0.5 * (fw["start"] + fw["end"]) * sr)
            local_chunks.append(extract_3s_window(audio, sr, mid_sample))

        local_embs = embed_chunks_nopad(local_chunks, fe, sv, batch_size=24)
        local_sims = center_norm(local_embs, mu_bg) @ centroids_cen[cand] if len(local_embs) else np.zeros((0,))
        local_res_sims = (
            np.array([float(res_enc.embed_utterance(ch) @ centroids_res[cand]) for ch in local_chunks])
            if local_chunks else np.zeros((0,))
        )

        raw_ep_strict_cand = 0
        raw_ep_broad_cand = 0
        ep_strict_cand = 0
        ep_broad_cand = 0
        ep_strict_noncand = 0
        ep_broad_noncand = 0

        for (wi, is_strict, is_broad, is_trap_only, trap_reason), lsim, lrsim in zip(mention_items, local_sims, local_res_sims):
            fw = flat_words[wi]
            lsim = float(lsim)
            lrsim = float(lrsim)
            ctx_words = [flat_words[k]["raw"] for k in range(max(0, wi - 12), min(n_fw, wi + 13))]
            ctx = " ".join(ctx_words)
            ts_r = round(fw["start"], 2)
            adj_key = f"{eid}|{ts_r:.2f}|{fw['norm']}"
            adj_entry = adjudications.get(adj_key)

            raw_is_cand = bool(fw["is_candidate"])
            final_strict = is_strict
            final_broad = is_broad
            final_is_cand = raw_is_cand
            adjudicated = False
            adj_reason = ""
            excluded_homophone = False

            if is_trap_only:
                if adj_entry and adj_entry.get("decision") == "include_homophone":
                    is_strict_promo = bool(MAIN_TRAP_RE.match(fw["norm"]))
                    final_strict = is_strict_promo
                    final_broad = True
                    adjudicated = True
                    adj_reason = adj_entry.get("reason", "")
                    final_is_cand = adj_entry.get("force_candidate", raw_is_cand)
                else:
                    homophone_traps.append({
                        "episode_id": eid,
                        "candidate": cand,
                        "timestamp_sec": ts_r,
                        "timestamp_mmss": fmt_mmss(fw["start"]),
                        "token": fw["norm"],
                        "clean_raw": fw["clean_raw"],
                        "trap_reason": trap_reason,
                        "sim_utterance": round(fw["u_sim"], 4),
                        "sim_local": round(lsim, 4),
                        "sim_res_local": round(lrsim, 4),
                        "is_candidate": raw_is_cand,
                        "adj_key": adj_key,
                        "context": ctx,
                    })
                    continue

            if not is_trap_only and raw_is_cand:
                if is_strict:
                    raw_ep_strict_cand += 1
                if is_broad:
                    raw_ep_broad_cand += 1

            if adj_entry and not is_trap_only:
                dec = adj_entry.get("decision")
                if dec == "flip_to_candidate" and not final_is_cand:
                    final_is_cand = True
                    adjudicated = True
                    adj_reason = adj_entry.get("reason", "")
                elif dec == "flip_to_non_candidate" and final_is_cand:
                    final_is_cand = False
                    adjudicated = True
                    adj_reason = adj_entry.get("reason", "")
                elif dec == "exclude_homophone":
                    excluded_homophone = True
                    adjudicated = True
                    adj_reason = adj_entry.get("reason", "")

            if excluded_homophone:
                homophone_traps.append({
                    "episode_id": eid,
                    "candidate": cand,
                    "timestamp_sec": ts_r,
                    "timestamp_mmss": fmt_mmss(fw["start"]),
                    "token": fw["norm"],
                    "clean_raw": fw["clean_raw"],
                    "trap_reason": "excluded_homophone",
                    "sim_utterance": round(fw["u_sim"], 4),
                    "sim_local": round(lsim, 4),
                    "sim_res_local": round(lrsim, 4),
                    "is_candidate": False,
                    "adj_key": adj_key,
                    "context": ctx,
                })
                continue

            disagree = (raw_is_cand != (lsim >= tau)) or (raw_is_cand != (lrsim >= tr))
            borderline = abs(fw["u_sim"] - tau) <= 0.08 or abs(lsim - tau) <= 0.08 or bool(trap_reason)
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
                "clean_raw": fw["clean_raw"],
                "adj_key": adj_key,
                "is_strict": final_strict,
                "is_broad": final_broad,
                "sim_utterance": round(fw["u_sim"], 4),
                "sim_local": round(lsim, 4),
                "sim_res_local": round(lrsim, 4),
                "tau": tau,
                "tau_res": tr,
                "raw_acoustic_is_candidate": raw_is_cand,
                "is_candidate": final_is_cand,
                "adjudicated": adjudicated,
                "adjudication_reason": adj_reason,
                "outside_kept_cluster": fw["outside_kept_cluster"],
                "borderline_or_disagree": bool(borderline or disagree),
                "context": ctx,
            }
            if trap_reason:
                homophone_traps.append({
                    "episode_id": eid,
                    "candidate": cand,
                    "timestamp_sec": ts_r,
                    "timestamp_mmss": fmt_mmss(fw["start"]),
                    "token": fw["norm"],
                    "clean_raw": fw["clean_raw"],
                    "trap_reason": trap_reason,
                    "sim_utterance": round(fw["u_sim"], 4),
                    "sim_local": round(lsim, 4),
                    "sim_res_local": round(lrsim, 4),
                    "is_candidate": final_is_cand,
                    "adj_key": adj_key,
                    "context": ctx,
                })

            if final_is_cand:
                if final_strict:
                    ep_strict_cand += 1
                if final_broad:
                    ep_broad_cand += 1
                all_mentions.append(rec)
            else:
                if final_strict:
                    ep_strict_noncand += 1
                if final_broad:
                    ep_broad_noncand += 1
                non_cand_mentions.append(rec)

        # Sensitivity thresholds (tau - 0.05, tau, tau + 0.05) on centered WavLM-SV
        sens_counts = {}
        for tag, delta in [("lo", -0.05), ("mid", 0.0), ("hi", 0.05)]:
            t_val = tau + delta
            min_sp = 30.0 if tag == "hi" else 55.0
            sub_utts, _, _, _ = filter_to_kept_clusters(utts, t_val, min_speech_sec=min_sp)
            sub_sec = sum(u["end"] - u["start"] for u in sub_utts)
            sub_craw = [clean_raw_preserve_case(w["word"]) for u in sub_utts for w in u["words"]]
            sub_norm = [norm_token(w["word"]) for u in sub_utts for w in u["words"]]
            sub_norm = [w for w in sub_norm if w]
            if cand == "graham_platner":
                s_hits = sum(1 for r in sub_craw if STRICT_ME_RE.match(r))
                b_hits = sum(1 for r in sub_craw if STRICT_ME_RE.match(r) or BROAD_MAINER_RE.match(r))
            else:
                s_hits = sum(1 for w in sub_norm if STRICT_PA_RE.match(w))
                b_hits = sum(1 for w in sub_norm if BROAD_PA_RE.match(w))
            sens_counts[tag] = {
                "speech_sec": round(sub_sec, 2),
                "words": len(sub_norm),
                "strict_mentions": s_hits,
                "broad_mentions": b_hits,
            }

        cand_tokens = [norm_token(w["word"]) for u in cand_utts for w in u["words"]]
        cand_raw_clean = [clean_raw_preserve_case(w["word"]) for u in cand_utts for w in u["words"]]
        paired = [(n, r) for n, r in zip(cand_tokens, cand_raw_clean) if n]
        cand_tokens = [n for n, _ in paired]
        cand_raw_clean = [r for _, r in paired]

        hc_hits = sum(1 for w in cand_tokens if BENCH_PATTERNS["healthcare_medicare"].match(w))
        hc_hits += sum(1 for i in range(len(cand_tokens) - 1) if cand_tokens[i] == "health" and cand_tokens[i + 1] == "care")
        sub_geo_hits, sub_geo_bd = count_substate_geo(cand_tokens, cand_raw_clean, cand, eid, substate_audit)
        pa_abbr_cand = sum(1 for r in cand_raw_clean if PA_ABBR_RE.match(r)) if cand == "john_fetterman" else 0
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
            "pa_abbr_mentions": pa_abbr_cand,
            "noncand_strict_mentions": ep_strict_noncand,
            "noncand_broad_mentions": ep_broad_noncand,
            "substate_geo_mentions": sub_geo_hits,
            "substate_geo_breakdown": sub_geo_bd,
            "rate_per_speaking_hr_strict": round(ep_strict_cand / (cand_speech_sec / 3600.0), 2),
            "rate_per_speaking_hr_broad": round(ep_broad_cand / (cand_speech_sec / 3600.0), 2),
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
    analysis = {
        "taus_cen": taus,
        "taus_res": tau_res,
        "adjudications_applied": len(adjudications),
        "appearances": appearances,
        "candidate_mentions": all_mentions,
        "non_candidate_mentions": non_cand_mentions,
        "homophone_traps": homophone_traps,
        "pa_abbr_audit": pa_abbr_audit,
        "substate_audit": substate_audit,
        "prefix_edge_cases": prefix_edge_cases,
    }
    (DATA_DIR / "analysis_pf_results.json").write_text(json.dumps(analysis, indent=2))

    # Write full audit log
    audit_lines = []
    for cand in ["graham_platner", "john_fetterman"]:
        sub = [a for a in appearances if a["candidate"] == cand]
        hrs = sum(a["cand_speaking_sec"] for a in sub) / 3600.0
        act_hrs = sum(a["active_appearance_sec"] for a in sub) / 3600.0
        sm = sum(a["strict_mentions"] for a in sub)
        bm = sum(a["broad_mentions"] for a in sub)
        pa_ab = sum(a["pa_abbr_mentions"] for a in sub)
        nc = sum(a["noncand_strict_mentions"] for a in sub)
        line = (
            f"SUMMARY {cand}: N={len(sub)} eps | speak_hrs={hrs:.2f} | active_hrs={act_hrs:.2f} | "
            f"strict={sm} ({sm/hrs:.2f}/hr) | broad={bm} ({bm/hrs:.2f}/hr) | "
            f"pa_abbr={pa_ab} | filtered_noncand_strict={nc}"
        )
        print(line)
        audit_lines.append(line)

    border_all = [m for m in all_mentions + non_cand_mentions if m["borderline_or_disagree"]]
    audit_lines.append(f"\n=== BORDERLINE OR DISAGREE MENTIONS ({len(border_all)}) ===")
    for m in border_all:
        tag = "CAND" if m["is_candidate"] else "NON "
        audit_lines.append(
            f"  [{tag}] {m['adj_key']} | {m['clean_raw']} ({'S' if m['is_strict'] else 'B'}) | "
            f"cen_utt={m['sim_utterance']:.3f} cen_loc={m['sim_local']:.3f} res_loc={m['sim_res_local']:.3f} | {m['context']}"
        )

    audit_lines.append(f"\n=== HOMOPHONE / MANOR / MAINE+NEXT TRAPS ({len(homophone_traps)}) ===")
    for h in homophone_traps:
        tag = "CAND" if h["is_candidate"] else "NON "
        audit_lines.append(
            f"  [{tag}] {h['adj_key']} | {h['trap_reason']} | raw={h['clean_raw']} | "
            f"cen_utt={h['sim_utterance']:.3f} cen_loc={h['sim_local']:.3f} res={h['sim_res_local']:.3f} | {h['context']}"
        )

    audit_lines.append(f"\n=== FETTERMAN 'PA' / 'P.A.' AUDIT ({len(pa_abbr_audit)}) ===")
    for p in pa_abbr_audit:
        tag = "CAND" if p["is_candidate"] else "NON "
        audit_lines.append(f"  [{tag}] {p['episode_id']} {p['ts']} | raw={p['clean_raw']} upper={p['is_upper_pa']} | {p['context']}")

    audit_lines.append(f"\n=== AMBIGUOUS SUBSTATE PLACE AUDIT ({len(substate_audit)}) ===")
    for s in substate_audit:
        audit_lines.append(f"  [{'HIT ' if s['counted'] else 'SKIP'}] {s['episode_id']} ({s['cand']}) term={s['term']} | {s['ctx']}")

    audit_lines.append(f"\n=== PREFIX EDGE CASES ({len(prefix_edge_cases)}) ===")
    for pe in prefix_edge_cases:
        audit_lines.append(f"  {pe}")

    audit_path = DATA_DIR / "_borderline_and_homophone_audit.txt"
    audit_path.write_text("\n".join(audit_lines))
    print(f"Saved audit log -> {audit_path} (borderline={len(border_all)}, traps={len(homophone_traps)}, pa_abbr={len(pa_abbr_audit)}, substate={len(substate_audit)})")


if __name__ == "__main__":
    main()
