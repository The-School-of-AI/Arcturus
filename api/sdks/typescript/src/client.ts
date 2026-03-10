export type GatewayMetadata = {
  idempotencyStatus?: string;
  idempotencyKey?: string;
  usageHeaders: Record<string, string>;
  rateLimitHeaders: Record<string, string>;
};

export type GatewayResult<T = unknown> = {
  statusCode: number;
  body: T;
  metadata: GatewayMetadata;
};

export class GatewayApiError extends Error {
  statusCode: number;
  body: unknown;

  constructor(statusCode: number, body: unknown) {
    super(`Gateway API error (${statusCode})`);
    this.statusCode = statusCode;
    this.body = body;
  }
}

export type GatewayClientOptions = {
  baseUrl: string;
  apiKey?: string;
  adminKey?: string;
  idempotencyKeyFactory?: () => string;
};

export class GatewayClient {
  private readonly baseUrl: string;
  private readonly apiKey?: string;
  private readonly adminKey?: string;
  private readonly idempotencyKeyFactory: () => string;

  constructor(options: GatewayClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.apiKey = options.apiKey;
    this.adminKey = options.adminKey;
    this.idempotencyKeyFactory =
      options.idempotencyKeyFactory ?? (() => `sdk-${crypto.randomUUID()}`);
  }

  private buildHeaders(params: {
    authMode: "api" | "admin" | "none";
    mutating: boolean;
    idempotencyKey?: string;
    extraHeaders?: Record<string, string>;
  }): Record<string, string> {
    const headers: Record<string, string> = {
      "content-type": "application/json",
    };

    if (params.authMode === "api") {
      if (!this.apiKey) {
        throw new Error("apiKey is required for this request");
      }
      headers["x-api-key"] = this.apiKey;
    } else if (params.authMode === "admin") {
      if (!this.adminKey) {
        throw new Error("adminKey is required for this request");
      }
      headers["x-gateway-admin-key"] = this.adminKey;
    }

    if (params.mutating) {
      headers["Idempotency-Key"] =
        params.idempotencyKey ?? this.idempotencyKeyFactory();
    }

    if (params.extraHeaders) {
      Object.assign(headers, params.extraHeaders);
    }

    return headers;
  }

  private extractMetadata(response: Response): GatewayMetadata {
    const usageHeaders: Record<string, string> = {};
    const rateLimitHeaders: Record<string, string> = {};

    response.headers.forEach((value, key) => {
      if (key.startsWith("x-usage-")) usageHeaders[key] = value;
      if (key.startsWith("x-ratelimit-")) rateLimitHeaders[key] = value;
    });

    return {
      idempotencyStatus: response.headers.get("x-idempotency-status") ?? undefined,
      idempotencyKey: response.headers.get("x-idempotency-key") ?? undefined,
      usageHeaders,
      rateLimitHeaders,
    };
  }

  private async request<T = unknown>(params: {
    method: string;
    path: string;
    authMode: "api" | "admin" | "none";
    mutating?: boolean;
    idempotencyKey?: string;
    body?: unknown;
    query?: URLSearchParams;
    extraHeaders?: Record<string, string>;
  }): Promise<GatewayResult<T>> {
    const queryString = params.query ? `?${params.query.toString()}` : "";
    const response = await fetch(`${this.baseUrl}${params.path}${queryString}`, {
      method: params.method,
      headers: this.buildHeaders({
        authMode: params.authMode,
        mutating: Boolean(params.mutating),
        idempotencyKey: params.idempotencyKey,
        extraHeaders: params.extraHeaders,
      }),
      body: params.body === undefined ? undefined : JSON.stringify(params.body),
    });

    const contentType = response.headers.get("content-type") ?? "";
    const body = contentType.includes("application/json")
      ? ((await response.json()) as T)
      : ((await response.text()) as unknown as T);

    if (response.status >= 400) {
      throw new GatewayApiError(response.status, body);
    }

    return {
      statusCode: response.status,
      body,
      metadata: this.extractMetadata(response),
    };
  }

  search(query: string, limit = 5) {
    return this.request({
      method: "POST",
      path: "/api/v1/search",
      authMode: "api",
      body: { query, limit },
    });
  }

  pagesGenerate(query: string, template?: string, idempotencyKey?: string) {
    return this.request({
      method: "POST",
      path: "/api/v1/pages/generate",
      authMode: "api",
      mutating: true,
      idempotencyKey,
      body: { query, template },
    });
  }

  studioGenerate(kind: "slides" | "docs" | "sheets", prompt: string, template?: string, idempotencyKey?: string) {
    return this.request({
      method: "POST",
      path: `/api/v1/studio/${kind}`,
      authMode: "api",
      mutating: true,
      idempotencyKey,
      body: { prompt, template },
    });
  }

  cronListJobs() {
    return this.request({ method: "GET", path: "/api/v1/cron/jobs", authMode: "api" });
  }

  cronCreateJob(payload: Record<string, unknown>, idempotencyKey?: string) {
    return this.request({
      method: "POST",
      path: "/api/v1/cron/jobs",
      authMode: "api",
      mutating: true,
      idempotencyKey,
      body: payload,
    });
  }

  webhooksConnectors() {
    return this.request({ method: "GET", path: "/api/v1/webhooks/connectors", authMode: "api" });
  }

  webhooksInbound(source: string, payload: Record<string, unknown>, extraHeaders?: Record<string, string>) {
    return this.request({
      method: "POST",
      path: `/api/v1/webhooks/inbound/${source}`,
      authMode: "none",
      body: payload,
      extraHeaders,
    });
  }

  usageMe(month?: string) {
    const query = new URLSearchParams();
    if (month) query.set("month", month);
    return this.request({ method: "GET", path: "/api/v1/usage", authMode: "api", query });
  }
}
