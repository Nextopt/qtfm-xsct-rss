import re
import time
import hmac
import hashlib
import requests
from email.utils import formatdate
from xml.sax.saxutils import escape
from html import unescape

CHANNEL_ID = "287342"
CHANNEL_URL = f"https://www.qtfm.cn/channels/{CHANNEL_ID}/"
OUTPUT_FILE = "podcast.xml"

FEED_TITLE = "《晓声长谈》持续更"
FEED_LINK = CHANNEL_URL
FEED_DESCRIPTION = "根据蜻蜓FM“《晓声长谈》持续更新”频道自动生成 RSS 订阅源，仅用于个人订阅收听。"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": CHANNEL_URL,
}


def clean_html(text):
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def make_audio_url(program_id):
    timestamp = str(round(time.time() * 1000))

    access_token = ""
    qingting_id = ""
    device_id = "MOBILESITE"

    path = (
        f"/audiostream/redirect/{CHANNEL_ID}/{program_id}"
        f"?access_token={access_token}"
        f"&device_id={device_id}"
        f"&qingting_id={qingting_id}"
        f"&t={timestamp}"
    )

    key = b"fpMn12&38f_2e"
    sign = hmac.new(key, path.encode("utf-8"), hashlib.md5).hexdigest()

    return f"https://audio.qtfm.cn{path}&sign={sign}"


def safe_text(value):
    if value is None:
        return ""
    return escape(str(value))


def get_programs_from_channel_page():
    r = requests.get(CHANNEL_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    html_text = r.text

    pattern = re.compile(
        rf'<a[^>]+href="(/channels/{CHANNEL_ID}/programs/(\d+)/?)"[^>]*>(.*?)</a>',
        re.S,
    )

    programs = []
    seen = set()

    for match in pattern.finditer(html_text):
        href, program_id, raw_title = match.groups()

        if program_id in seen:
            continue
        seen.add(program_id)

        title = clean_html(raw_title)

        if not title:
            continue

        # 在链接后面的一小段 HTML 里找时长和日期
        tail = html_text[match.end(): match.end() + 500]

        duration_match = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?)", clean_html(tail))
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", clean_html(tail))

        duration = duration_match.group(1) if duration_match else ""
        date_text = date_match.group(1) if date_match else ""

        if date_text:
            try:
                year, month, day = map(int, date_text.split("-"))
                pub_ts = time.mktime((year, month, day, 0, 0, 0, 0, 0, -1))
                pub_date = formatdate(pub_ts, localtime=False)
            except Exception:
                pub_date = formatdate(time.time(), localtime=False)
        else:
            pub_date = formatdate(time.time(), localtime=False)

        programs.append({
            "id": program_id,
            "title": title,
            "duration": duration,
            "pubDate": pub_date,
            "program_url": f"https://www.qtfm.cn{href if href.endswith('/') else href + '/'}",
        })

    if not programs:
        raise RuntimeError("没有从频道网页中解析到节目列表，可能是蜻蜓 FM 页面结构变化。")

    return programs[:30]


def build_rss(programs):
    now = formatdate(time.time(), localtime=False)

    items = []

    for p in programs:
        program_id = p["id"]
        title = p["title"]
        desc = title
        duration = p.get("duration", "")
        program_url = p["program_url"]
        audio_url = make_audio_url(program_id)
        pubdate = p["pubDate"]

        item = f"""
    <item>
      <title>{safe_text(title)}</title>
      <link>{safe_text(program_url)}</link>
      <guid isPermaLink="false">qtfm-{CHANNEL_ID}-{safe_text(program_id)}</guid>
      <pubDate>{safe_text(pubdate)}</pubDate>
      <description>{safe_text(desc)}</description>
      <enclosure url="{safe_text(audio_url)}" type="audio/mpeg" length="1" />
      <itunes:duration>{safe_text(duration)}</itunes:duration>
    </item>
"""
        items.append(item)

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{safe_text(FEED_TITLE)}</title>
    <link>{safe_text(FEED_LINK)}</link>
    <description>{safe_text(FEED_DESCRIPTION)}</description>
    <language>zh-CN</language>
    <lastBuildDate>{safe_text(now)}</lastBuildDate>
    <ttl>15</ttl>
    <itunes:author>蜻蜓 FM</itunes:author>
    <itunes:summary>{safe_text(FEED_DESCRIPTION)}</itunes:summary>
    <itunes:explicit>false</itunes:explicit>
{''.join(items)}
  </channel>
</rss>
"""
    return rss


def main():
    programs = get_programs_from_channel_page()

    rss = build_rss(programs)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(rss)

    print(f"已生成 {OUTPUT_FILE}，节目数量：{len(programs)}")
    print("前 5 个节目：")
    for p in programs[:5]:
        print("-", p["title"])


if __name__ == "__main__":
    main()
