// 简单的 API 客户端封装
const getApiBaseUrl = () => {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  // 客户端：自动推断主机名 (用于局域网调试)
  if (typeof window !== 'undefined') {
    return `http://${window.location.hostname}:8000/api/v1`;
  }
  // 服务端：默认 localhost
  return 'http://localhost:8000/api/v1';
};

export const API_BASE_URL = getApiBaseUrl();

export async function fetchClient<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `API Error: ${res.status}`);
  }

  return res.json();
}

// 类型定义
export interface ETFItem {
  code: string;
  name: string;
  price: number;
  change_pct: number;
  volume: number;
  atr?: number | null;
  current_drawdown?: number | null;
  // 首页展示所需的摘要字段
  temperature_score?: number | null;
  temperature_level?: "freezing" | "cool" | "warm" | "hot" | null;
  weekly_direction?: "up" | "down" | "flat" | null;
  consecutive_weeks?: number | null;
}

export interface ETFDetail extends ETFItem {
  update_time: string;
  market?: string; // 交易状态: "交易中" | "已收盘"
}

export interface ETFHistoryItem {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
}

export interface ETFValuation {
  pe: number;
  pe_percentile: number;
  dist_view: string;
  index_code: string;
  index_name: string;
  data_date: string;
  history_start: string;
  history_years: number;
}

// 周线趋势
export interface WeeklyTrend {
  consecutive_weeks: number;  // 正数=连涨，负数=连跌
  direction: "up" | "down" | "flat";
  ma_status: "bullish" | "bearish" | "mixed";
}

// 日线趋势
export interface DailyTrend {
  ma5_position: "above" | "below" | "crossing_up" | "crossing_down";
  ma20_position: "above" | "below" | "crossing_up" | "crossing_down";
  ma60_position: "above" | "below" | "crossing_up" | "crossing_down";
  ma_alignment: "bullish" | "bearish" | "mixed";
  latest_signal: string | null;  // e.g., "break_above_ma20"
  ma_values: {
    ma5: number;
    ma20: number;
    ma60: number;
  };
}

// 温度计
export interface Temperature {
  score: number;  // 0-100
  level: "freezing" | "cool" | "warm" | "hot";
  factors: {
    drawdown_score: number;
    rsi_score: number;
    percentile_score: number;
    volatility_score: number;
    trend_score: number;
  };
  rsi_value: number;
  percentile_value: number;
  percentile_years: number;
  percentile_note?: string;  // 不足10年时显示
}

// 网格交易建议
export interface GridSuggestion {
  upper: number;           // 网格上界
  lower: number;           // 网格下界
  spacing_pct: number;     // 网格间距百分比
  grid_count: number;      // 网格数量
  range_start: string;     // 分析区间起始日期
  range_end: string;       // 分析区间结束日期
  is_out_of_range: boolean; // 当前价格是否超出区间
  reason?: string;         // 不适合网格交易的原因（可选）
}

export interface ETFMetrics {
  period: string;
  total_return: number;
  cagr: number;
  max_drawdown: number;
  mdd_date: string;
  mdd_start?: string; // Peak Date
  mdd_trough?: string; // Trough Date (same as mdd_date)
  mdd_end?: string | null; // Recovery Date (null if not recovered)
  volatility: number;
  risk_level: string;
  actual_years?: number; // 实际计算所用的年数
  valuation?: ETFValuation | null;
  atr?: number | null;
  current_drawdown?: number | null;
  drawdown_days?: number;
  effective_drawdown_days?: number;
  current_drawdown_peak_date?: string | null;
  days_since_peak?: number;
  // 新增趋势和温度字段
  weekly_trend?: WeeklyTrend | null;
  daily_trend?: DailyTrend | null;
  temperature?: Temperature | null;
}

// Telegram 配置类型
export interface TelegramConfig {
  enabled: boolean;
  botToken: string;
  chatId: string;
  verified?: boolean;
  lastTestAt?: string | null;
}

// 告警配置类型
export interface AlertConfig {
  enabled: boolean;
  temperature_change: boolean;
  extreme_temperature: boolean;
  rsi_signal: boolean;
  ma_crossover: boolean;
  ma_alignment: boolean;
  weekly_signal: boolean;
  max_alerts_per_day: number;
}

// Telegram 配置相关 API
export async function getTelegramConfig(token: string) {
  const response = await fetch(`${API_BASE_URL}/notifications/telegram/config`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '获取配置失败' }));
    throw new Error(error.detail || '获取配置失败');
  }
  return response.json();
}

export async function saveTelegramConfig(
  token: string,
  config: { enabled: boolean; botToken: string; chatId: string }
) {
  const response = await fetch(`${API_BASE_URL}/notifications/telegram/config`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(config)
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '保存配置失败' }));
    throw new Error(error.detail || '保存配置失败');
  }
  return response.json();
}

export async function testTelegramConfig(token: string) {
  const response = await fetch(`${API_BASE_URL}/notifications/telegram/test`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '测试失败' }));
    throw new Error(error.detail || '测试失败');
  }
  return response.json();
}

export async function deleteTelegramConfig(token: string) {
  const response = await fetch(`${API_BASE_URL}/notifications/telegram/config`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '删除配置失败' }));
    throw new Error(error.detail || '删除配置失败');
  }
  return response.json();
}

// 告警配置相关 API
export async function getAlertConfig(token: string): Promise<AlertConfig> {
  const response = await fetch(`${API_BASE_URL}/alerts/config`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '获取配置失败' }));
    throw new Error(error.detail || '获取配置失败');
  }
  return response.json();
}

export async function saveAlertConfig(
  token: string,
  config: AlertConfig
): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE_URL}/alerts/config`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(config)
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '保存配置失败' }));
    throw new Error(error.detail || '保存配置失败');
  }
  return response.json();
}

export async function triggerAlertCheck(
  token: string
): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${API_BASE_URL}/alerts/trigger`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '触发检查失败' }));
    throw new Error(error.detail || '触发检查失败');
  }
  return response.json();
}

// Health 响应类型
export interface HealthResponse {
  status: string;
  version: string;
  data_ready: boolean;
  environment: string;
}

// 获取应用版本
export async function getVersion(): Promise<string> {
  try {
    // 构建 health 端点 URL（更健壮的方式）
    const baseUrl = API_BASE_URL.endsWith('/api/v1')
      ? API_BASE_URL.slice(0, -7)  // 移除 '/api/v1'
      : API_BASE_URL;
    const healthUrl = `${baseUrl}/api/v1/health`;

    const response = await fetch(healthUrl);
    if (!response.ok) {
      throw new Error('Failed to fetch health status');
    }
    const data: HealthResponse = await response.json();
    return data.version || 'unknown';
  } catch (error) {
    console.error('Failed to fetch version:', error);
    // 回退到构建时注入的版本
    return process.env.NEXT_PUBLIC_APP_VERSION || 'unknown';
  }
}
