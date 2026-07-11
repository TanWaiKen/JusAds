# Frontend Requirements — Research & Intelligence Layer

## API Endpoints Available

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/trends?platform=&market=&limit=` | Fetch trending content grouped by platform |
| GET | `/api/trends/events?market=&window_days=` | Fetch upcoming cultural events |
| POST | `/api/trends/refresh` | Trigger manual trend scrape (admin) |
| GET | `/api/statistics/posts?project_id=&platform=&date_from=&date_to=` | Fetch post performance stats |
| GET | `/api/statistics/posts/{post_id}` | Single post detailed stats |
| POST | `/api/projects/{project_id}/tasks/{task_id}/chat` | Generation chat (now emits `creative_plan` SSE event) |

---

## Page 1: Trends Intelligence Page (`/trends`)

### Data Sources
- `GET /api/trends` → `{ trends: {platform: [items]}, last_refresh: {platform: timestamp}, total_items }`
- `GET /api/trends/events` → `{ events: [{name, start_date, end_date, event_type, tags, impact_score}], count }`

### Response Shapes

```typescript
// GET /api/trends
interface TrendsResponse {
  trends: Record<string, TrendItem[]>;  // grouped by platform
  last_refresh: Record<string, string>; // platform → ISO timestamp
  total_items: number;
  message?: string;  // shown when empty
}

interface TrendItem {
  id: string;
  title: string;
  url: string;
  platform: "tiktok" | "instagram" | "youtube" | "facebook_ads";
  content_type: "video" | "image" | "carousel" | "ad";
  engagement_metrics: {
    views: number;
    likes: number;
    shares: number;
    comments: number;
  };
  hashtags: string[];
  categories: string[];
  cultural_event_tag: string | null;
  scraped_at: string;
}

// GET /api/trends/events
interface EventsResponse {
  events: CulturalEvent[];
  market: string;
  window_days: number;
  count: number;
}

interface CulturalEvent {
  id: string;
  name: string;
  market: string;
  start_date: string;    // YYYY-MM-DD
  end_date: string;
  event_type: "religious" | "festive" | "sports" | "national" | "global";
  tags: string[];
  impact_score: number;  // 0-100
}
```

### UI Requirements

1. **Hero Section** — Show AI-detected synergy headline (e.g., "CNY + FIFA overlap detected"). Action buttons: "Explore Spikes", "View Detailed Report"
2. **Contextual Event Calendar** — Display upcoming cultural events as cards. Each shows: name, date range, event_type tags, impact_score (X/100). Prev/Next navigation for date range.
3. **Trend Synergy Insight** — When a `cultural_event_tag` matches an upcoming event, highlight it as a synergy. Show velocity percentage, "Generate Idea" button linking to generation page.
4. **Audience Sentiment** (static mock for now) — Positive/Neutral/Critical bar chart + top keyphrase.
5. **Industry Intel Section** — Trending content cards grouped by platform. Each card: thumbnail (use `url` for link), title, hashtags, engagement metrics (views + velocity). Buttons: "Reference" (save as generation reference), "Campaign" (start generation with this trend).
6. **Filters** — Platform dropdown (All / TikTok / Instagram / YouTube / Facebook Ads). Time range (Last 24h / Last 7 Days).
7. **Last Refresh** — Show per-platform last refresh timestamp. "Refresh" button calls `POST /api/trends/refresh`.
8. **Empty State** — When `message` field present or `total_items === 0`, show "No trend data available" with refresh button.

### Design Reference
Use `figma/trends.html` as the visual reference for layout, colors, and component styles.

---

## Page 2: Post Statistics Page (`/statistics`)

### Data Sources
- `GET /api/statistics/posts?project_id=&platform=&date_from=&date_to=` → campaign stats
- `GET /api/statistics/posts/{post_id}` → single post detail

### Response Shapes

```typescript
// GET /api/statistics/posts
interface StatsResponse {
  posts: PostStats[];
  totals: MetricsTotals;
  post_count: number;
  is_stale: boolean;
  last_refresh: string | null;
}

interface PostStats {
  post_external_id: string;
  impressions: number;
  clicks: number;
  engagement_rate: number;
  reach: number;
  conversions: number;
  is_stale: boolean;
  fetched_at: string;
}

interface MetricsTotals {
  impressions: number;
  clicks: number;
  engagement_rate: number;
  reach: number;
  conversions: number;
}
```

### UI Requirements

1. **Summary Cards** — 5 top-level metric cards: Impressions, Clicks, Engagement Rate (%), Reach, Conversions. Show total values from `totals`.
2. **Trend Chart** — Recharts line chart showing daily impressions + clicks trend over the selected date range. (Use chart_data from the existing analytics endpoint as reference pattern.)
3. **Filters** — Date range picker (from/to). Platform dropdown (All / TikTok / Instagram / YouTube). Project/Campaign selector.
4. **Posts Table** — List each distributed post with: platform icon, post_id, impressions, clicks, engagement_rate, reach, conversions, fetched_at.
5. **Stale Data Indicator** — When `is_stale === true`, show a yellow banner: "Showing cached data — live metrics temporarily unavailable."
6. **Last Refresh** — Show `last_refresh` timestamp at top.
7. **Empty State** — When no distributed posts, show "No posts distributed yet" with link to generation page.
8. **Route** — Register at `/statistics` in App.tsx, add to dashboard sidebar navigation.

---

## Page 3: Creative Plan Approval (component in `/generate`)

### Data Source
- Part of the existing SSE stream from `POST /api/projects/{project_id}/tasks/{task_id}/chat`
- New SSE event type: `{ creative_plan: CreativePlan }`
- Approval/rejection sent as a follow-up chat message or a dedicated endpoint

### Response Shape

```typescript
interface CreativePlan {
  target_platforms: string[];
  media_types: string[];
  trend_references: TrendReference[];
  creative_direction: string;
  target_language: string;
  cultural_event_refs: EventRef[];
}

interface TrendReference {
  title: string;
  url: string;
  platform: string;
  relevance: string;
}

interface EventRef {
  name: string;
  dates: string;
  tags: string[];
}
```

### UI Requirements

1. **Plan Card** — Display the CreativePlan in a structured card format when received via SSE. Show: target platforms (as badges), media types (as icons), creative direction text, target language.
2. **Trend References Section** — List up to 5 trend references with title, platform badge, and relevance note. Link to original URL.
3. **Cultural Event References** — Show event names, dates, and tags if present.
4. **Action Buttons** — "Approve & Generate" (green) → sends approval, generation proceeds. "Request Changes" (outline) → opens a textarea for feedback, sends revision request.
5. **Revision Flow** — After feedback submitted, show loading state while Director Agent revises. When new plan arrives, replace the card content.
6. **Loading State** — Show skeleton/spinner while Director Agent is planning (before `creative_plan` SSE event).
7. **Integration** — This is NOT a separate page. It's a component within the existing generation page that appears between the assistant reply and the media generation nodes.

---

## Shared Requirements

- Use Tailwind CSS 4 utility classes (no inline styles)
- Use shadcn/ui components for buttons, cards, badges, selects, inputs
- Use Recharts for charts
- Use Lucide React for icons
- Use `@/services/` pattern for API clients
- Use `interface` over `type` for object shapes
- Named exports for components
- Fetch via `fetch` + `VITE_API_BASE` (fallback `http://localhost:8000`)
- Handle loading, error, and empty states for all data fetching
- Dark/light mode support via existing next-themes setup
