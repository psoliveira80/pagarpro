import { Injectable, inject, NgZone } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom, Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthService } from './auth.service';

export interface AgentTool {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
}

export interface AgentConfig {
  id: string;
  llm_provider: string;
  llm_model: string;
  whatsapp_provider: string;
  system_prompt: string;
  tools: AgentTool[];
  rate_limit_rpm: number;
  monthly_budget: number;
  temperature: number;
  created_at: string;
  updated_at: string;
}

export interface AgentConfigPayload {
  llm_provider: string;
  llm_model?: string;
  whatsapp_provider: string;
  system_prompt: string;
  tools?: { id: string; enabled: boolean }[];
  rate_limit_rpm?: number;
  monthly_budget?: number;
  temperature?: number;
}

export interface AgentChatRequest {
  message: string;
  context?: Record<string, unknown>;
}

export interface AgentChatChunk {
  type: 'token' | 'done' | 'error' | 'metadata';
  content?: string;
  confidence?: 'alta' | 'media' | 'baixa';
  actions?: AgentAction[];
  error?: string;
}

export interface AgentAction {
  label: string;
  route?: string;
  action?: string;
  data?: Record<string, unknown>;
}

@Injectable({ providedIn: 'root' })
export class AgentService {
  private readonly http = inject(HttpClient);
  private readonly authService = inject(AuthService);
  private readonly zone = inject(NgZone);
  private readonly apiUrl = `${environment.apiBaseUrl}/agent`;

  async getConfigs(): Promise<AgentConfig[]> {
    return firstValueFrom(
      this.http.get<AgentConfig[]>(`${this.apiUrl}/configs`),
    );
  }

  async createConfig(payload: AgentConfigPayload): Promise<AgentConfig> {
    return firstValueFrom(
      this.http.post<AgentConfig>(`${this.apiUrl}/configs`, payload),
    );
  }

  async updateConfig(id: string, payload: Partial<AgentConfigPayload>): Promise<AgentConfig> {
    return firstValueFrom(
      this.http.put<AgentConfig>(`${this.apiUrl}/configs/${id}`, payload),
    );
  }

  async listTools(): Promise<AgentTool[]> {
    return firstValueFrom(
      this.http.get<AgentTool[]>(`${this.apiUrl}/tools`),
    );
  }

  chat(request: AgentChatRequest): Observable<AgentChatChunk> {
    return new Observable<AgentChatChunk>((subscriber) => {
      const token = this.authService.getToken();
      const url = `${environment.apiBaseUrl}/agent/chat`;

      fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(request),
      })
        .then(async (response) => {
          if (!response.ok) {
            this.zone.run(() => {
              subscriber.next({ type: 'error', error: `HTTP ${response.status}` });
              subscriber.complete();
            });
            return;
          }

          const reader = response.body?.getReader();
          if (!reader) {
            this.zone.run(() => {
              subscriber.next({ type: 'error', error: 'No response body' });
              subscriber.complete();
            });
            return;
          }

          const decoder = new TextDecoder();
          let buffer = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() ?? '';

            for (const line of lines) {
              const trimmed = line.trim();
              if (!trimmed || !trimmed.startsWith('data: ')) continue;
              const data = trimmed.slice(6);
              if (data === '[DONE]') {
                this.zone.run(() => {
                  subscriber.next({ type: 'done' });
                  subscriber.complete();
                });
                return;
              }
              try {
                const chunk = JSON.parse(data) as AgentChatChunk;
                this.zone.run(() => subscriber.next(chunk));
              } catch {
                // Partial JSON, try next line
              }
            }
          }

          this.zone.run(() => {
            subscriber.next({ type: 'done' });
            subscriber.complete();
          });
        })
        .catch((err) => {
          this.zone.run(() => {
            subscriber.next({ type: 'error', error: err.message ?? 'Network error' });
            subscriber.complete();
          });
        });
    });
  }
}
