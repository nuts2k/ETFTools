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
}
