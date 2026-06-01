#!/usr/bin/env python3
import json, re, sys
from http.client import HTTPSConnection
from typing import Optional
from urllib.parse import quote

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
LIMIT = 50
API_PATH = "/youtubei/v1/search"

def clean_str(s: str) -> str:
    return " ".join(s.replace("|||", " ").split()) if s else ""

def fmt_views(s: str) -> str:
    if not s: return ""
    digits = re.sub(r"[^0-9]", "", s)
    if not digits: return clean_str(s)
    n, suffix = int(digits), (" views" if "view" in s.lower() else "")
    if n >= 1e9: return f"{n/1e9:.1f}".rstrip("0").rstrip(".") + f"B{suffix}"
    if n >= 1e6: return f"{n/1e6:.1f}".rstrip("0").rstrip(".") + f"M{suffix}"
    if n >= 1e3: return f"{n/1e3:.1f}".rstrip("0").rstrip(".") + f"K{suffix}"
    return f"{n}{suffix}"

def parse_video_renderer(vr: dict) -> Optional[str]:
    vid = vr.get("videoId")
    if not vid: return None
    title = "".join(r.get("text", "") for r in vr.get("title", {}).get("runs", []))
    channel = (vr.get("ownerText", {}).get("runs") or [{}])[0].get("text", "")
    date = (vr.get("publishedTimeText") or {}).get("simpleText", "")
    views = fmt_views((vr.get("viewCountText") or {}).get("simpleText", ""))
    return f"video|||{vid}|||{clean_str(title)}|||{clean_str(channel)}|||{clean_str(date)}|||{views}"

def parse_playlist_renderer(pr: dict) -> Optional[str]:
    plid = pr.get("playlistId")
    if not plid: return None
    title = "".join(r.get("text", "") for r in pr.get("title", {}).get("runs", []))
    channel = (pr.get("longBylineText", {}).get("runs") or [{}])[0].get("text", "")
    video_count = pr.get("videoCount", "")
    ch_suffix = f"{channel} [PLAYLIST]" if channel else "[PLAYLIST]"
    extra = f"{video_count} videos" if video_count else ""
    return f"playlist|||{plid}|||{clean_str(title)}|||{clean_str(ch_suffix)}||||||{clean_str(extra)}"

def parse_lockup_view_model(lvm: dict) -> Optional[str]:
    ct, cid = lvm.get("contentType"), lvm.get("contentId")
    if not ct or not cid: return None
    rtype = "playlist" if ct == "LOCKUP_CONTENT_TYPE_PLAYLIST" else "video"
    title, ch, views, date = "", "", "", ""
    meta = lvm.get("metadata", {}).get("lockupMetadataViewModel", {})
    if meta:
        title = meta.get("title", {}).get("content", "")
        rows = meta.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", [])
        for row in rows:
            for part in row.get("metadataParts", []):
                content = part.get("text", {}).get("content", "")
                if not content: continue
                if "view" in content.lower(): views = fmt_views(content)
                elif "ago" in content.lower() or content in ["Today", "Yesterday"]: date = content
                elif not ch: ch = content.replace(" | Playlist", "")
    if rtype == "playlist":
        return f"playlist|||{cid}|||{clean_str(title)}|||{clean_str(ch + ' [PLAYLIST]' if ch else '[PLAYLIST]')}||||||{clean_str(views)}"
    return f"video|||{cid}|||{clean_str(title)}|||{clean_str(ch)}|||{clean_str(date)}|||{clean_str(views)}"

def process_item(item: dict, seen: set):
    if "videoRenderer" in item:
        vr = item["videoRenderer"]
        if vr.get("videoId") not in seen:
            line = parse_video_renderer(vr)
            if line: seen.add(vr["videoId"]); print(line)
    elif "playlistRenderer" in item:
        pr = item["playlistRenderer"]
        if pr.get("playlistId") not in seen:
            line = parse_playlist_renderer(pr)
            if line: seen.add(pr["playlistId"]); print(line)
    elif "lockupViewModel" in item:
        lvm = item["lockupViewModel"]
        if lvm.get("contentId") not in seen:
            line = parse_lockup_view_model(lvm)
            if line: seen.add(lvm["contentId"]); print(line)
    elif "shelfRenderer" in item or "relevanceShelfRenderer" in item:
        shelf = item.get("shelfRenderer") or item.get("relevanceShelfRenderer")
        for ci in shelf.get("content", {}).get("verticalListRenderer", {}).get("items", []):
            process_item(ci, seen)

def search(query: str, use_continuation: bool = True):
    conn = HTTPSConnection("www.youtube.com")
    conn.request("GET", f"/results?search_query={quote(query)}", headers={"User-Agent": UA})
    html = conn.getresponse().read().decode("utf-8", errors="replace")
    
    api_key = re.search(r'INNERTUBE_API_KEY"\s*:\s*"([^"]+)', html)
    api_key = api_key.group(1) if api_key else None
    
    m = re.search(r'ytInitialData\s*=\s*({.*?});', html)
    if not m:
        conn.close()
        return

    seen, token = set(), None
    try:
        sections = json.loads(m.group(1))["contents"]["twoColumnSearchResultsRenderer"]["primaryContents"]["sectionListRenderer"]["contents"]
    except KeyError:
        conn.close()
        return

    for sec in sections:
        ir = sec.get("itemSectionRenderer")
        if ir:
            for item in ir.get("contents", []): process_item(item, seen)
        cr = sec.get("continuationItemRenderer")
        if cr:
            try: token = cr["continuationEndpoint"]["continuationCommand"]["token"]
            except (KeyError, IndexError): pass

    if use_continuation and api_key and token and len(seen) < LIMIT:
        while token and len(seen) < LIMIT:
            body = json.dumps({
                "context": {"client": {"hl": "en", "gl": "US", "clientName": "WEB", "clientVersion": "2.20260501.00.00"}},
                "continuation": token
            })
            conn.request("POST", f"{API_PATH}?key={api_key}", body=body, headers={"Content-Type": "application/json", "User-Agent": UA})
            try:
                data = json.loads(conn.getresponse().read().decode("utf-8", errors="replace"))
                actions = data.get("onResponseReceivedCommands") or data.get("onResponseReceivedActions") or []
            except Exception:
                break
                
            token, added = None, 0
            if actions:
                items = actions[0].get("appendContinuationItemsAction", {}).get("continuationItems", [])
                for item in items:
                    ir = item.get("itemSectionRenderer")
                    if ir:
                        for ci in ir.get("contents", []):
                            old_len = len(seen)
                            process_item(ci, seen)
                            if len(seen) > old_len: added += 1
                            if len(seen) >= LIMIT: break
                    elif "lockupViewModel" in item or "videoRenderer" in item or "playlistRenderer" in item:
                        old_len = len(seen)
                        process_item(item, seen)
                        if len(seen) > old_len: added += 1
                        if len(seen) >= LIMIT: break
                    
                    cr = item.get("continuationItemRenderer")
                    if cr and len(seen) < LIMIT:
                        try: token = cr["continuationEndpoint"]["continuationCommand"]["token"]
                        except (KeyError, IndexError): pass
            if added == 0 or len(seen) >= LIMIT: break
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--no-continuation":
            search(" ".join(sys.argv[2:]), use_continuation=False)
        else:
            search(" ".join(sys.argv[1:]), use_continuation=True)
