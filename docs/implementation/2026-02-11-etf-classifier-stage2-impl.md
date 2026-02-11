# ETF 分类器阶段2：搜索页标签筛选功能 - 实施计划

> 创建时间: 2026-02-11
> 状态: 待实施
> 关联设计文档: [ETF 自动分类标签设计](../design/2026-02-10-etf-auto-classification-design.md) 第 7.2 节

---

## 1. 背景

阶段0+1 已完成：分类器独立验证通过，搜索/批量价格/详情接口均已返回 `tags` 字段，`StockCard` 已支持标签展示。

阶段2 目标：在搜索页添加标签筛选能力，让用户通过点击标签快速浏览同类 ETF。

## 2. 交互方案（已确认）

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 选择模式 | **单选** | 点一个标签看结果，再点切换，最简洁 |
| 展示方式 | **单行热门标签** | 横向滚动，混合展示 ~14 个最常用标签 |
| 与搜索关系 | **互斥模式** | 搜索框为空时显示标签，输入文字后隐藏标签 |

**三态状态机**：

```
idle（空闲）──点击标签──→ tag-filtering（标签筛选）
  ↑                          │
  │←──再次点击同一标签────────┘
  │                          │
  └──输入文字──→ text-searching（文本搜索）──清空输入──→ idle
```

| 状态 | 条件 | UI |
|------|------|----|
| idle | `query===""` 且 `selectedTag===null` | 显示标签行，无结果 |
| tag-filtering | `query===""` 且 `selectedTag!==null` | 标签行（高亮选中）+ 筛选结果 |
| text-searching | `query!==""` | 隐藏标签行，显示文本搜索结果（现有行为） |

---

## 3. 后端变更

### 3.1 `backend/app/core/cache.py` — 新增 `filter_by_tag` 方法

在 `ETFCacheManager` 类中新增方法，对内存中的 `etf_list` 按标签 label 线性扫描：

```python
def filter_by_tag(self, tag_label: str, limit: int = 50) -> List[Dict]:
    """按标签筛选 ETF"""
    results = []
    for item in self.etf_list:
        for t in item.get("tags", []):
            if t.get("label") == tag_label:
                results.append(item)
                break
        if len(results) >= limit:
            break
    return results
```

### 3.2 `backend/app/api/v1/endpoints/etf.py` — 新增端点 + 修改搜索

**a) 新增 `GET /tags/popular`**

> ⚠️ 必须放在 `/{code}/info`（第 103 行）之前，否则 FastAPI 会把 `"tags"` 当作 `{code}` 路径参数。

返回硬编码的热门标签列表（顺序精心排列）：

```python
POPULAR_TAGS = [
    {"label": "宽基", "group": "type"},
    {"label": "半导体", "group": "industry"},
    {"label": "医药", "group": "industry"},
    {"label": "红利", "group": "strategy"},
    {"label": "跨境", "group": "type"},
    {"label": "新能源", "group": "industry"},
    {"label": "人工智能", "group": "industry"},
    {"label": "券商", "group": "industry"},
    {"label": "消费", "group": "industry"},
    {"label": "军工", "group": "industry"},
    {"label": "黄金", "group": "industry"},
    {"label": "银行", "group": "industry"},
    {"label": "商品", "group": "type"},
    {"label": "债券", "group": "type"},
]

@router.get("/tags/popular")
async def get_popular_tags():
    """返回搜索页热门标签列表"""
    return POPULAR_TAGS
```

**b) 修改 `GET /search`**

`q` 从必选改为可选，新增可选 `tag` 参数：

```python
@router.get("/search", response_model=List[Dict])
@limiter.limit("30/minute")
async def search_etf(
    request: Request,
    q: Optional[str] = Query(None, min_length=1, description="ETF代码或名称关键字"),
    tag: Optional[str] = Query(None, min_length=1, max_length=20, description="按标签筛选"),
):
    """搜索 ETF（支持文本搜索或标签筛选）"""
    if tag:
        return etf_cache.filter_by_tag(tag)
    if q:
        return etf_cache.search(q)
    return []
```

---

## 4. 前端变更

### 4.1 `frontend/app/search/page.tsx` — 主要 UI 变更

**新增导入**：
- `TAG_COLORS` from `@/lib/tag-colors`

**新增状态变量**（复用现有 `results` / `loading`，仅新增 2 个）：
```typescript
const [selectedTag, setSelectedTag] = useState<string | null>(null);
const [popularTags, setPopularTags] = useState<Array<{label: string; group: string}>>([]);

// 请求取消 ref（防止标签快速切换时的竞态条件）
const abortRef = useRef<AbortController | null>(null);
```

**新增 useEffect — 加载热门标签**：
```typescript
useEffect(() => {
  fetchClient<Array<{label: string; group: string}>>("/etf/tags/popular")
    .then(setPopularTags)
    .catch(() => {}); // 静默失败，标签行不显示即可
}, []);
```

**统一搜索 useEffect**（替换现有文本搜索 effect，同时处理文本搜索和标签筛选）：
```typescript
useEffect(() => {
  async function doSearch() {
    if (!debouncedQuery && !selectedTag) {
      setResults([]);
      return;
    }

    // 取消上一个请求，防止竞态
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    try {
      const url = selectedTag
        ? `/etf/search?tag=${encodeURIComponent(selectedTag)}`
        : `/etf/search?q=${encodeURIComponent(debouncedQuery)}`;
      const data = await fetchClient<ETFItem[]>(url, { signal: controller.signal });
      setResults(data);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      console.error("Search failed", err);
    } finally {
      setLoading(false);
    }
  }
  doSearch();
}, [debouncedQuery, selectedTag]);
```

> 💡 `fetchClient` 已支持 `options?: RequestInit`（`frontend/lib/api.ts:16`），`signal` 可直接传入。

**标签行 UI**（header 和 results section 之间）：
- 仅在 `query === ""` 且 `popularTags.length > 0` 时显示
- 横向滚动 `overflow-x-auto`，使用已有 `no-scrollbar` 样式（`globals.css` 第 119-125 行）
- 标签 chip 使用 `TAG_COLORS`（`frontend/lib/tag-colors.ts`）着色
- 选中态：`bg-primary text-primary-foreground`
- 最小触摸高度 36px
- **无障碍**：容器 `role="radiogroup"` + `aria-label="按标签筛选 ETF"`，每个标签 `role="radio"` + `aria-checked`

```tsx
{query === "" && popularTags.length > 0 && (
  <div
    role="radiogroup"
    aria-label="按标签筛选 ETF"
    className="flex gap-2 overflow-x-auto no-scrollbar px-4 py-3"
  >
    {popularTags.map((tag) => (
      <button
        key={tag.label}
        role="radio"
        aria-checked={selectedTag === tag.label}
        onClick={() => handleTagClick(tag.label)}
        className={cn(
          "shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors min-h-[36px]",
          selectedTag === tag.label
            ? "bg-primary text-primary-foreground"
            : TAG_COLORS[tag.group] || TAG_COLORS.special
        )}
      >
        {tag.label}
      </button>
    ))}
  </div>
)}
```

**交互逻辑**：
- 点击标签 → toggle `selectedTag`（统一 useEffect 自动触发请求）
- 再次点击同一标签 → 取消选中（`selectedTag` 置 null，results 清空）
- 点击不同标签 → 切换选中
- 用户输入文字 → `onChange` 中清空 `selectedTag`
- `isSearchActive` 更新：`query.length > 0 || inputFocused || selectedTag !== null`

```typescript
const handleTagClick = (label: string) => {
  setSelectedTag(prev => prev === label ? null : label);
};

// 输入框 onChange
onChange={(e) => {
  setQuery(e.target.value);
  if (e.target.value) setSelectedTag(null); // 输入文字时清除标签选中
}}
```

**结果展示**（直接使用 `results`，无需 `displayResults` 中间变量）：
- 结果头部：标签筛选显示 `「{tag}」相关`，文本搜索显示"搜索结果"
- 空状态文案：标签筛选显示 `未找到「{tag}」相关的 ETF`，文本搜索显示"未找到相关结果"
- 复用现有 `StockCard` + `showTags={true}`

```tsx
{/* 结果标题 */}
{(query || selectedTag) && (
  <div className="flex items-center justify-between pb-3 pt-1">
    <h3 className="text-lg font-bold leading-tight tracking-tight">
      {selectedTag ? `「${selectedTag}」相关` : "搜索结果"}
    </h3>
    <span className="...">QFQ</span>
  </div>
)}

{/* 空状态 */}
{!loading && (query || selectedTag) && results.length === 0 && (
  <div className="text-center py-10 text-muted-foreground">
    {selectedTag ? `未找到「${selectedTag}」相关的 ETF` : "未找到相关结果"}
  </div>
)}
```

---

## 5. 边界情况处理

| 场景 | 处理方式 |
|------|---------|
| 缓存未初始化（冷启动） | `filter_by_tag` 返回空列表，前端显示 `未找到「{tag}」相关的 ETF` |
| 标签无匹配 ETF | 返回空列表，前端显示带标签名的空状态文案 |
| 点击标签后立即输入文字 | `onChange` 清空 `selectedTag`，统一 useEffect 自动切换到文本搜索 |
| 快速切换标签（竞态条件） | AbortController 取消上一个请求，catch 中忽略 AbortError |
| `tag` 和 `q` 同时提供 | `tag` 优先（if/elif 链中先检查） |
| 热门标签端点在缓存就绪前调用 | 返回硬编码列表，不依赖缓存 |
| 热门标签加载失败 | 静默失败（`.catch(() => {})`），标签行不显示 |

---

## 6. 测试计划

### 后端测试

- `filter_by_tag` 方法：匹配/不匹配/limit 参数/空缓存/无 tags 字段的 item
- `GET /etf/tags/popular`：返回格式正确（list of dict with label/group）
- `GET /etf/search?tag=宽基`：返回筛选结果
- `GET /etf/search` 无参数：返回空列表
- `GET /etf/search?q=300`：向后兼容
- `GET /etf/search?tag=宽基&q=300`：tag 优先

### 前端测试

- 标签行渲染：正确显示热门标签
- 标签点击交互：选中/取消状态切换
- 与文本搜索互斥：输入文字时标签行隐藏
- 无障碍属性：`role="radiogroup"` 和 `aria-checked` 正确设置

---

## 7. 文档更新

按 AGENTS.md 4.7 节要求，同一 commit 中更新：

| 文档 | 更新内容 |
|------|---------|
| `AGENTS.md` 第 6 节 | API 速查表新增 `/etf/tags/popular`，更新 `/etf/search` 描述 |
| 设计文档 | 更新阶段2状态和更新日志 |

---

## 8. 涉及文件清单

| 文件 | 操作 |
|------|------|
| `backend/app/core/cache.py` | 修改：新增 `filter_by_tag` 方法 |
| `backend/app/api/v1/endpoints/etf.py` | 修改：新增 `/tags/popular`，修改 `/search` |
| `frontend/app/search/page.tsx` | 修改：标签状态、标签行 UI、统一结果展示 |
| `frontend/lib/tag-colors.ts` | 引用（无需修改） |
| `backend/tests/` | 新增：后端测试 |
| `frontend/__tests__/` | 新增：前端测试 |
| `AGENTS.md` | 修改：API 速查表 |
| 设计文档 | 修改：阶段2状态 |

---

## 9. 验证方式

1. 启动后端：`cd backend && uvicorn app.main:app --reload --port 8000`
2. 测试 API：
   - `curl localhost:8000/api/v1/etf/tags/popular` → 返回标签列表
   - `curl localhost:8000/api/v1/etf/search?tag=半导体` → 返回半导体 ETF
   - `curl localhost:8000/api/v1/etf/search?q=300` → 向后兼容
3. 运行后端测试：`cd backend && pytest tests/ -v`
4. 启动前端验证 UI 交互
5. 运行前端测试：`cd frontend && npx vitest run`

---

**最后更新**: 2026-02-11
