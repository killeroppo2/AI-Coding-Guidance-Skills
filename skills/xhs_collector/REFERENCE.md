# 小红书爆款采集器 - API 参考文档

## Coze API 调用规范

### 接口地址

```
POST https://api.coze.cn/v1/workflow/run
```

### 鉴权方式

```
Header: Authorization: Bearer {API Token}
Content-Type: application/json
```

---

## 工作流① - 搜索笔记

### 基本信息

| 项目 | 值 |
|------|------|
| workflow_id | `7641028939528503305` |
| 功能 | 按关键词搜索小红书热门笔记列表 |

### 输入参数

```json
{
  "workflow_id": "7641028939528503305",
  "parameters": {
    "input": "搜索关键词",
    "sort": "2",
    "timeScope": "2"
  }
}
```

| 参数 | 类型 | 说明 |
|------|------|------|
| input | string | 搜索关键词 |
| sort | string | 排序方式：`2`=最多点赞, `3`=最多评论 |
| timeScope | string | 时间范围：`1`=一天内, `2`=一周内, `3`=半年内 |

### 返回结构

```json
{
  "code": 0,
  "msg": "",
  "data": "{\"output\":{\"has_more\":true,\"items\":[...]}}"
}
```

`data` 字段为 JSON 字符串，解析后结构如下：

```json
{
  "output": {
    "has_more": true,
    "items": [
      {
        "id": "笔记ID",
        "model_type": "note",
        "url": "笔记链接（含 xsec_token）",
        "xsec_token": "访问令牌",
        "note_card": {
          "display_title": "笔记标题",
          "type": "video | normal",
          "corner_tag_info": [
            {"text": "发布时间描述", "type": "publish_time"}
          ],
          "cover": {
            "height": 1920,
            "width": 1080,
            "url_default": "封面图链接"
          },
          "interact_info": {
            "liked_count": "点赞数",
            "collected_count": "收藏数",
            "comment_count": "评论数",
            "shared_count": "分享数"
          },
          "user": {
            "user_id": "用户ID",
            "nickname": "用户昵称",
            "avatar": "头像链接"
          }
        }
      }
    ]
  }
}
```

---

## 工作流② - 提取笔记详情

### 基本信息

| 项目 | 值 |
|------|------|
| workflow_id | `7641029124206854170` |
| 功能 | 提取单条笔记的正文、图片内容、评论 |

### 输入参数

```json
{
  "workflow_id": "7641029124206854170",
  "parameters": {
    "url": "笔记链接",
    "cookie": "小红书 Cookie"
  }
}
```

| 参数 | 类型 | 说明 |
|------|------|------|
| url | string | 笔记完整链接（含 xsec_token） |
| cookie | string | 小红书登录 Cookie |

### 返回结构

```json
{
  "code": 0,
  "msg": "",
  "data": "{\"content_type\":1,\"data\":\"...\",\"type_for_model\":2}"
}
```

`data` 字段解析后，其内部 `data` 字段包含两段 JSON（用换行分隔）：

**第一段 - 笔记内容：**

```json
[{
  "fields": {
    "标题": "笔记标题",
    "作者": "作者昵称",
    "内容": "正文内容（含话题标签）",
    "图片内容": "图片中的文字识别内容",
    "图片地址": "图片 URL",
    "视频地址": "视频 URL（如有）",
    "笔记链接": "原始链接",
    "点赞数": "4",
    "收藏数": "3",
    "评论数": "1"
  }
}]
```

**第二段 - 评论数据：**

```json
{
  "comments": [
    {
      "id": "评论ID",
      "content": "评论内容",
      "like_count": "1",
      "note_id": "所属笔记ID",
      "sub_comment_count": "0",
      "user_info": {
        "nickname": "评论者昵称",
        "user_id": "评论者ID",
        "image": "评论者头像"
      }
    }
  ],
  "has_more": false,
  "cursor": "分页游标"
}
```

---

## 配置文件说明

### config.json

| 字段 | 说明 |
|------|------|
| coze_api_token | Coze 平台 API Token |
| xhs_cookie | 小红书登录 Cookie（需定期更新） |
| workflow_search_id | 搜索笔记工作流 ID |
| workflow_detail_id | 提取详情工作流 ID |
| sort | 默认排序方式 |
| time_scope | 默认时间范围 |
| max_notes_per_keyword | 每个关键词最多采集笔记数 |

### keywords.json

```json
{
  "keywords": ["关键词1", "关键词2", "..."]
}
```

---

## 注意事项

1. **Cookie 有效期**：小红书 Cookie 有时效，失效后需重新获取并更新 `config.json`
2. **频率限制**：脚本已内置请求间隔（1~2秒），避免触发 API 限流
3. **数据完整性**：如工作流②失败，脚本会使用工作流①的基础数据兜底
4. **输出目录**：文件自动保存至 `01-内容生产/爆款参考库/`，目录不存在时自动创建
