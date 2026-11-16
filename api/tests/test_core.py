import json

import pytest

from app import captions, exports, originality, urls
from app.acquire import VideoMeta, pick_caption_track
from app.errors import classify_message

YT = "dQw4w9WgXcQ"


@pytest.mark.parametrize("url,expected", [
    ("https://www.tiktok.com/@scout2015/video/6718335390845095173", ("tiktok", "6718335390845095173")),
    ("https://www.tiktok.com/@a.b_c/video/7301234567890123456?is_from_webapp=1&sender_device=pc", ("tiktok", "7301234567890123456")),
    ("https://m.tiktok.com/v/6718335390845095173.html", ("tiktok", "6718335390845095173")),
    ("https://www.tiktok.com/embed/v2/6718335390845095173", ("tiktok", "6718335390845095173")),
    ("https://www.instagram.com/reel/CyEhyJZsWBH/", ("instagram", "CyEhyJZsWBH")),
    ("https://www.instagram.com/reels/CyEhyJZsWBH/?igsh=abc", ("instagram", "CyEhyJZsWBH")),
    ("https://instagram.com/p/C-_x9aB/", ("instagram", "C-_x9aB")),
    ("https://www.instagram.com/someuser/reel/CyEhyJZsWBH/", ("instagram", "CyEhyJZsWBH")),
    (f"https://www.youtube.com/shorts/{YT}", ("youtube", YT)),
    (f"https://youtube.com/shorts/{YT}?feature=share", ("youtube", YT)),
    (f"https://www.youtube.com/watch?v={YT}&t=10s", ("youtube", YT)),
    (f"https://www.youtube.com/watch?app=desktop&v={YT}", ("youtube", YT)),
    (f"https://m.youtube.com/watch?v={YT}", ("youtube", YT)),
    (f"https://youtu.be/{YT}?si=xyz", ("youtube", YT)),
    (f"https://www.youtube.com/embed/{YT}", ("youtube", YT)),
])
def test_classify_single_videos(url, expected):
    assert urls.classify(url) == expected
    assert not urls.is_collection(url)


@pytest.mark.parametrize("url", [
    "https://vm.tiktok.com/ZMabcdef/", "https://vt.tiktok.com/ZSabc123/", "https://www.tiktok.com/t/ZTabc123/",
])
def test_short_links(url):
    assert urls.classify(url) is None
    assert urls.is_short_link(url)
    assert not urls.is_collection(url)


@pytest.mark.parametrize("url", [
    "https://www.tiktok.com/@scout2015", "https://www.tiktok.com/@scout2015/", "https://www.tiktok.com/@scout2015?lang=en",
    "https://www.youtube.com/playlist?list=PLabc", "https://www.youtube.com/@mkbhd", "https://www.youtube.com/@mkbhd/shorts",
    "https://www.youtube.com/channel/UCabc123/videos", "https://www.instagram.com/natgeo/", "https://www.instagram.com/natgeo/reels/",
])
def test_collections(url):
    assert urls.is_collection(url)


@pytest.mark.parametrize("url", ["https://example.com/video/123", "https://www.tiktok.com/@a/photo/123", "not a url"])
def test_unsupported(url):
    assert urls.classify(url) is None


def test_extract_urls_from_messy_paste():
    text = f"""check these:
    https://www.tiktok.com/@a/video/111, and https://youtu.be/{YT}.
    youtube.com/shorts/{YT}   (duplicate of the one above)
    www.instagram.com/reel/AbC123/ plus (https://vm.tiktok.com/ZMxyz/)"""
    assert urls.extract_urls(text) == [
        "https://www.tiktok.com/@a/video/111", f"https://youtu.be/{YT}",
        "https://www.instagram.com/reel/AbC123/", "https://vm.tiktok.com/ZMxyz/",
    ]


def test_canonical():
    assert urls.canonical("youtube", YT) == f"https://www.youtube.com/watch?v={YT}"
    assert urls.canonical("tiktok", "1", "@bob") == "https://www.tiktok.com/@bob/video/1"


ROLLING_VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.160 --> 00:00:02.230 align:start position:0%
 
so<00:00:00.320><c> today</c><00:00:00.640><c> we</c>

00:00:02.230 --> 00:00:02.240 align:start position:0%
so today we


00:00:02.240 --> 00:00:04.550 align:start position:0%
so today we
are<00:00:02.480><c> going</c><00:00:02.800><c> to</c> &amp; talk

00:00:04.550 --> 00:00:04.560 align:start position:0%
are going to &amp; talk
"""


def test_vtt_rolling_captions_are_deduped():
    segs = captions.parse_vtt(ROLLING_VTT)
    assert [s["text"] for s in segs] == ["so today we", "are going to & talk"]
    assert segs[0]["start"] == pytest.approx(0.16)
    assert segs[1]["start"] == pytest.approx(2.24)


def test_srt_and_short_timestamps_parse():
    body = "1\n00:00:01,000 --> 00:00:02,500\nHello there\n\n2\n00:03.000 --> 00:04.000\n<i>General</i> Kenobi\n"
    assert captions.parse_vtt(body) == [
        {"start": 1.0, "end": 2.5, "text": "Hello there"}, {"start": 3.0, "end": 4.0, "text": "General Kenobi"}]


def test_json3():
    body = json.dumps({"events": [
        {"tStartMs": 0, "dDurationMs": 4000, "segs": [{"utf8": "hello"}, {"utf8": " world"}]},
        {"tStartMs": 1500, "dDurationMs": 100, "aAppend": 1, "segs": [{"utf8": "\n"}]},
        {"tStartMs": 2000, "dDurationMs": 2000, "segs": [{"utf8": "again"}]},
        {"tStartMs": 9000, "id": 1},
    ]})
    assert captions.parse_caption("json3", body) == [
        {"start": 0.0, "end": 2.0, "text": "hello world"}, {"start": 2.0, "end": 4.0, "text": "again"}]


def test_prefix_segments_dropped():
    segs = [{"start": 0, "end": 1, "text": "I think"}, {"start": 1, "end": 2, "text": "I think that works"}]
    assert [s["text"] for s in captions.drop_rolling(segs)] == ["I think that works"]


def test_hallucinated_repeats_removed():
    seg = lambda t: {"start": 0, "end": 1, "text": t}
    segs = [seg("Real line")] + [seg("Thank you for watching.")] * 6 + [seg("Bye"), seg("Bye")]
    assert [s["text"] for s in captions.drop_repeats(segs)] == ["Real line", "Bye", "Bye"]


def test_has_speech():
    assert not captions.has_speech([])
    assert not captions.has_speech([{"start": 0, "end": 1, "text": "♪ ♪"}])
    assert captions.has_speech([{"start": 0, "end": 1, "text": "hey you"}])


def _meta(**kw):
    return VideoMeta(id="x", platform="youtube", url="u", **kw)


def test_caption_track_prefers_manual_then_original_auto():
    fmt = lambda lang: [{"ext": "srv1", "url": "x"}, {"ext": "vtt", "url": f"{lang}.vtt"}, {"ext": "json3", "url": f"{lang}.json3"}]
    auto = {"af": fmt("af"), "en": fmt("en-translated"), "vi-orig": fmt("vi-orig"), "vi": fmt("vi")}
    assert pick_caption_track(_meta(auto_captions=auto)) == {"lang": "vi", "ext": "json3", "url": "vi-orig.json3", "kind": "auto"}
    manual = pick_caption_track(_meta(auto_captions=auto, subtitles={"live_chat": fmt("c"), "en": fmt("en")}))
    assert manual["kind"] == "manual" and manual["url"] == "en.json3"
    assert pick_caption_track(_meta(auto_captions={"fr": fmt("fr")}, language="fr"))["lang"] == "fr"
    # Never silently pick an auto-translation in an unrelated language.
    assert pick_caption_track(_meta(auto_captions={"af": fmt("af"), "sq": fmt("sq")})) is None
    assert pick_caption_track(_meta()) is None


SEGS = [{"start": 0.0, "end": 1.5, "text": "Hello, world"}, {"start": 3661.25, "end": 3662.0, "text": "Later"}]


def test_srt_vtt_txt():
    assert exports.to_srt(SEGS) == "1\n00:00:00,000 --> 00:00:01,500\nHello, world\n\n2\n01:01:01,250 --> 01:01:02,000\nLater\n"
    assert exports.to_vtt(SEGS).startswith("WEBVTT\n\n00:00:00.000 --> 00:00:01.500\nHello, world\n")
    assert exports.to_txt(SEGS) == "Hello, world Later"
    assert exports.to_txt(SEGS, timestamps=True) == "[00:00] Hello, world\n[1:01:01] Later"


@pytest.mark.parametrize("render", [exports.to_srt, exports.to_vtt])
def test_subtitle_round_trip(render):
    assert captions.parse_vtt(render(SEGS)) == SEGS


def test_csv_quotes_commas_and_zip_has_every_file():
    assert exports.to_csv(SEGS).splitlines()[1] == '0.0,1.5,"Hello, world"'
    item = {"id": 7, "title": "A/B: test?", "author": "bob", "url": "u", "platform": "tiktok", "language": "en",
            "source": "asr", "duration_s": 5, "stats": {"view_count": 1000}, "segments": SEGS, "text": "Hello, world Later"}
    import io, zipfile
    names = zipfile.ZipFile(io.BytesIO(exports.to_zip([item], "srt"))).namelist()
    assert names == ["bob - AB test [7].srt", "_all_transcripts.csv"]
    assert json.loads(exports.render(item, "json"))["segments"] == SEGS
    assert "**Views:** 1,000" in exports.render(item, "md")


SOURCE = "stop scrolling if you want to learn the three habits that changed my mornings forever and saved me hours"


def test_originality():
    assert originality.check(SOURCE, SOURCE)["verdict"] == "too_similar"
    fresh = "here is a completely different take about cooking rice with butter and patience on a quiet sunday"
    assert originality.check(fresh, SOURCE) == {**originality.check(fresh, SOURCE), "overlap": 0.0, "verdict": "original"}
    mixed = fresh + " " + fresh.replace("rice", "beans") + " the three habits that changed my mornings forever okay then friends"
    result = originality.check(mixed, SOURCE)
    assert 0 < result["overlap"] < 0.2 and result["verdict"] == "borrowed"
    assert result["copied_phrases"] == ["the three habits that changed my mornings forever"]
    assert originality.check("too short", SOURCE)["overlap"] == 0.0


@pytest.mark.parametrize("message,code", [
    ("ERROR: [TikTok] 1: HTTP Error 429: Too Many Requests", "RATE_LIMITED"),
    ("ERROR: [Instagram] abc: Requested content is not available, rate-limit reached or login required. Use --cookies", "RATE_LIMITED"),
    ("ERROR: [youtube] x: Sign in to confirm you're not a bot. Use --cookies-from-browser", "LOGIN_REQUIRED"),
    ("ERROR: [youtube] x: Private video. Sign in if you've been granted access", "LOGIN_REQUIRED"),
    ("ERROR: [youtube] x: Video unavailable. This video has been removed by the uploader", "DELETED"),
    ("ERROR: [youtube] x: The uploader has not made this video available in your country", "GEO_BLOCKED"),
    ("ERROR: Unsupported URL: https://example.com", "UNSUPPORTED"),
    ("ERROR: [TikTok] 1: Unable to download webpage: HTTPSConnection(host='www.tiktok.com', port=443): Read timed out", "NETWORK"),
    ("ERROR: [TikTok] 1: Unable to download webpage: HTTP Error 403: Forbidden", "FORBIDDEN"),
    ("ERROR: [TikTok] 1: Your IP address is blocked from accessing this post", "GEO_BLOCKED"),
    ("ERROR: [TikTok] 1: Unable to extract webpage video data", "EXTRACTOR_BROKEN"),
])
def test_error_classification(message, code):
    assert classify_message(message) == code
