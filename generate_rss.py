import re
import time
import hmac
import hashlib
import requests
from email.utils import formatdate
from xml.sax.saxutils import escape

CHANNEL_ID = "287342"
CHANNEL_URL = f"https://www.qtfm.cn/channels/{CHANNEL_ID}/"
OUTPUT_FILE = "podcast.xml"

FEED_TITLE = "晓声长谈（蜻蜓FM频道287342）"
FEED_LINK = CHANNEL_URL
FEED_DESCRIPTION = "《晓声长谈》栏目是吉林新闻综合广播2008年7月创办的一档情感服务类栏目,节目的内容是“婚姻、家庭、情感”主持人钟晓用“唠实嗑”的方式为广大群众指点迷津，节目的口号是“和谐情感、和谐家庭、和谐生活” 蜻蜓FM频道287342自动生成 RSS 订阅源，仅用于个人订阅收听。"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": CHANNEL_URL,
}


def get_version():
    r = requests.get(CHANNEL_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()

    patterns = [
        r'"version"\s*:\s*"([^"]+)"',
        r'programs/([^/?"]+)\?curpage',
        r'programs/([A-Za-z0-9_=-]+)',
    ]

    for p in patterns:
        m = re.search(p, r.text)
        if m:
            return m.group(1)

    raise RuntimeError("没有从页面中找到 version，可能是蜻蜓 FM 页面结构变化。")


def get_programs(version, page=1, pagesize=30):
    url = (
        f"https://i.qingting.fm/capi/channel/{CHANNEL_ID}/programs/{version}"
        f"?curpage={page}&pagesize={pagesize}&order=desc"
    )

    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()

    data = r.json()
    return data.get("data", {}).get("programs", [])


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


def program_pubdate(program):
    for key in ["update_time", "created_time", "publish_time", "ctime"]:
        value = program.get(key)

        if isinstance(value, int):
            if value > 10_000_000_000:
                value = value / 1000
            return formatdate(value, localtime=False)

    return formatdate(time.time(), localtime=False)


def build_rss(programs):
    now = formatdate(time.time(), localtime=False)

    items = []

    for p in programs:
        program_id = p.get("id") or p.get("program_id")
        if not program_id:
            continue

        title = p.get("title", f"节目 {program_id}")
        desc = p.get("desc") or p.get("description") or title
        duration = p.get("duration") or p.get("duration_str") or ""
        program_url = f"https://www.qtfm.cn/channels/{CHANNEL_ID}/programs/{program_id}/"
        audio_url = make_audio_url(program_id)
        pubdate = program_pubdate(p)

        item = f"""
    <item>
      <title>{safe_text(title)}</title>
      <link>{safe_text(program_url)}</link>
      <guid isPermaLink="false">qtfm-{CHANNEL_ID}-{safe_text(program_id)}</guid>
      <pubDate>{safe_text(pubdate)}</pubDate>
      <description>{safe_text(desc)}</description>
      <enclosure url="{safe_text(audio_url)}" type="audio/mpeg" length="0" />
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
    version = get_version()
    programs = get_programs(version, page=1, pagesize=30)

    if not programs:
        raise RuntimeError("没有获取到节目列表。")

    rss = build_rss(programs)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(rss)

    print(f"已生成 {OUTPUT_FILE}，节目数量：{len(programs)}")


if __name__ == "__main__":
    main()
