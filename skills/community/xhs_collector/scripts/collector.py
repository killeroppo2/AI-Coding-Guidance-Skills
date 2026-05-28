#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书爆款笔记采集器
通过 Coze API 工作流按关键词搜索小红书热门笔记，提取正文+评论+互动数据，
生成 Markdown 文件归档到 01-内容生产/爆款参考库/ 目录下。
"""

import json
import time
from datetime import datetime
from pathlib import Path

import requests

# ─── 路径配置 ───────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR / "config.json"
KEYWORDS_PATH = SCRIPT_DIR / "keywords.json"
OUTPUT_BASE_DIR = SCRIPT_DIR.parent.parent / "01-内容生产" / "爆款参考库"

# ─── Coze API 配置 ──────────────────────────────────────────
COZE_API_URL = "https://api.coze.cn/v1/workflow/run"


def load_config():
    """加载配置文件"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_keywords():
    """加载关键词列表"""
    with open(KEYWORDS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def call_coze_workflow(api_token, workflow_id, parameters):
    """
    调用 Coze API 工作流
    :param api_token: Bearer Token
    :param workflow_id: 工作流 ID
    :param parameters: 工作流输入参数 dict
    :return: 解析后的响应数据
    """
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "workflow_id": workflow_id,
        "parameters": parameters,
    }

    try:
        resp = requests.post(COZE_API_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        result = resp.json()

        if result.get("code") != 0:
            print(f"  [错误] API 返回错误: {result.get('msg', '未知错误')}")
            return None

        # data 字段是 JSON 字符串，需要二次解析
        data_str = result.get("data", "")
        if data_str:
            return json.loads(data_str)
        return None

    except requests.exceptions.RequestException as e:
        print(f"  [错误] 请求失败: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"  [错误] JSON 解析失败: {e}")
        return None


def search_notes(api_token, workflow_id, keyword, sort="2", time_scope="2"):
    """
    工作流①：搜索笔记
    :param keyword: 搜索关键词
    :param sort: 排序方式 2=最多点赞, 3=最多评论
    :param time_scope: 时间范围 1=一天内, 2=一周内, 3=半年内
    :return: 笔记列表
    """
    parameters = {
        "input": keyword,
        "sort": sort,
        "timeScope": time_scope,
    }

    print(f"  🔍 搜索关键词: {keyword} (排序={sort}, 时间范围={time_scope})")
    data = call_coze_workflow(api_token, workflow_id, parameters)

    if not data:
        return []

    # 解析返回的笔记列表
    output = data.get("output", {})
    items = output.get("items", [])
    print(f"  ✅ 找到 {len(items)} 条笔记")
    return items


def extract_note_detail(api_token, workflow_id, note_url, cookie):
    """
    工作流②：提取笔记详情
    :param note_url: 笔记链接
    :param cookie: 小红书 Cookie
    :return: 笔记详情数据
    """
    parameters = {
        "url": note_url,
        "cookie": cookie,
    }

    print(f"  📄 提取详情: {note_url[:60]}...")
    data = call_coze_workflow(api_token, workflow_id, parameters)

    if not data:
        return None

    return data


def parse_note_detail(detail_data):
    """
    解析工作流②返回的笔记详情
    :return: dict with title, author, content, images, comments, stats
    """
    result = {
        "title": "",
        "author": "",
        "content": "",
        "image_content": "",
        "image_url": "",
        "video_url": "",
        "link": "",
        "liked_count": "0",
        "collected_count": "0",
        "comment_count": "0",
        "comments": [],
    }

    try:
        data_str = detail_data.get("data", "")
        if not data_str:
            return result

        # data 可能包含两段 JSON（笔记详情 + 评论），用换行分隔
        parts = data_str.strip().split("\n")

        # 解析笔记信息
        if len(parts) >= 1:
            note_list = json.loads(parts[0])
            if note_list and len(note_list) > 0:
                fields = note_list[0].get("fields", {})
                result["title"] = fields.get("标题", "无标题")
                result["author"] = fields.get("作者", "未知")
                result["content"] = fields.get("内容", "")
                result["image_content"] = fields.get("图片内容", "")
                result["image_url"] = fields.get("图片地址", "")
                result["video_url"] = fields.get("视频地址", "")
                result["link"] = fields.get("笔记链接", "")
                result["liked_count"] = fields.get("点赞数", "0")
                result["collected_count"] = fields.get("收藏数", "0")
                result["comment_count"] = fields.get("评论数", "0")

        # 解析评论信息
        if len(parts) >= 2:
            comments_data = json.loads(parts[1])
            comments_list = comments_data.get("comments", [])
            for c in comments_list:
                result["comments"].append(
                    {
                        "content": c.get("content", ""),
                        "like_count": c.get("like_count", "0"),
                        "nickname": c.get("user_info", {}).get("nickname", "匿名"),
                    }
                )

    except (json.JSONDecodeError, IndexError, KeyError) as e:
        print(f"  [警告] 解析详情失败: {e}")

    return result


def generate_markdown(keyword, notes_data, date_str):
    """
    生成 Markdown 文件内容
    :param keyword: 搜索关键词
    :param notes_data: 已解析的笔记列表
    :param date_str: 日期字符串
    :return: Markdown 文本
    """
    lines = []
    lines.append(f"# 小红书爆款采集 - {keyword} - {date_str}\n")
    lines.append(f"> 采集时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"> 关键词: {keyword}")
    lines.append(f"> 笔记数量: {len(notes_data)}\n")
    lines.append("---\n")

    for i, note in enumerate(notes_data, 1):
        lines.append(f"## 笔记 {i}: {note['title']}\n")
        lines.append("| 指标 | 数据 |")
        lines.append("|------|------|")
        lines.append(f"| 作者 | {note['author']} |")
        lines.append(f"| 点赞 | {note['liked_count']} |")
        lines.append(f"| 收藏 | {note['collected_count']} |")
        lines.append(f"| 评论 | {note['comment_count']} |")
        lines.append(f"| 链接 | [查看原文]({note['link']}) |")
        lines.append("")

        if note["content"]:
            lines.append("### 正文\n")
            lines.append(note["content"])
            lines.append("")

        if note["image_content"]:
            lines.append("### 图片文字内容\n")
            lines.append(note["image_content"])
            lines.append("")

        if note["comments"]:
            lines.append("### 热门评论\n")
            for j, comment in enumerate(note["comments"], 1):
                lines.append(
                    f"{j}. **{comment['nickname']}**: {comment['content']} "
                    f"(👍 {comment['like_count']})"
                )
            lines.append("")

        lines.append("---\n")

    return "\n".join(lines)


def save_markdown(content, keyword, date_str):
    """保存 Markdown 文件"""
    OUTPUT_BASE_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{date_str}_{keyword}.md"
    filepath = OUTPUT_BASE_DIR / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"  💾 已保存: {filepath}")
    return filepath


def main():
    """主流程"""
    print("=" * 60)
    print("🌟 小红书爆款笔记采集器 启动")
    print("=" * 60)

    # 加载配置
    config = load_config()
    keywords_config = load_keywords()

    api_token = config["coze_api_token"]
    cookie = config["xhs_cookie"]
    search_workflow_id = config["workflow_search_id"]
    detail_workflow_id = config["workflow_detail_id"]
    sort = config.get("sort", "2")
    time_scope = config.get("time_scope", "2")
    max_notes_per_keyword = config.get("max_notes_per_keyword", 5)

    keywords = keywords_config.get("keywords", [])
    date_str = datetime.now().strftime("%Y-%m-%d")

    print(f"\n📋 待采集关键词: {len(keywords)} 个")
    print(f"📅 日期: {date_str}")
    print(f"🔢 每关键词最多采集: {max_notes_per_keyword} 条")
    print("-" * 60)

    for kw_index, keyword in enumerate(keywords, 1):
        print(f"\n[{kw_index}/{len(keywords)}] 🏷️  关键词: {keyword}")
        print("-" * 40)

        # Step 1: 搜索笔记
        items = search_notes(api_token, search_workflow_id, keyword, sort, time_scope)

        if not items:
            print("  ⚠️ 未找到笔记，跳过")
            continue

        # 限制数量
        items = items[:max_notes_per_keyword]

        # Step 2: 逐条提取详情
        notes_data = []
        for note_index, item in enumerate(items, 1):
            note_card = item.get("note_card", {})
            note_url = item.get("url", "")
            title = note_card.get("display_title", "无标题") or "无标题"
            interact = note_card.get("interact_info", {})

            print(f"\n  [{note_index}/{len(items)}] {title}")

            if note_url:
                # 调用工作流②提取详情
                detail_raw = extract_note_detail(api_token, detail_workflow_id, note_url, cookie)

                if detail_raw:
                    detail = parse_note_detail(detail_raw)
                    # 如果详情解析失败，用搜索结果中的基础数据兜底
                    if not detail["title"] or detail["title"] == "无标题":
                        detail["title"] = title
                    if detail["liked_count"] == "0":
                        detail["liked_count"] = interact.get("liked_count", "0")
                    if detail["collected_count"] == "0":
                        detail["collected_count"] = interact.get("collected_count", "0")
                    if detail["comment_count"] == "0":
                        detail["comment_count"] = interact.get("comment_count", "0")
                    if not detail["link"]:
                        detail["link"] = note_url
                    if not detail["author"]:
                        detail["author"] = note_card.get("user", {}).get("nickname", "未知")
                else:
                    # 工作流②失败，使用搜索结果数据
                    detail = {
                        "title": title,
                        "author": note_card.get("user", {}).get("nickname", "未知"),
                        "content": "",
                        "image_content": "",
                        "image_url": "",
                        "video_url": "",
                        "link": note_url,
                        "liked_count": interact.get("liked_count", "0"),
                        "collected_count": interact.get("collected_count", "0"),
                        "comment_count": interact.get("comment_count", "0"),
                        "comments": [],
                    }

                notes_data.append(detail)
            else:
                print("  ⚠️ 无链接，跳过")

            # 请求间隔，避免频率限制
            time.sleep(1)

        # Step 3: 生成 Markdown
        if notes_data:
            md_content = generate_markdown(keyword, notes_data, date_str)
            save_markdown(md_content, keyword, date_str)
        else:
            print("  ⚠️ 无有效笔记数据，跳过生成")

        # 关键词间隔
        time.sleep(2)

    print("\n" + "=" * 60)
    print("✅ 采集完成！")
    print(f"📂 文件保存目录: {OUTPUT_BASE_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
