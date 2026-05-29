import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface ConversationMessage {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  metadata: Record<string, unknown> | null;
  criado_em: string;
}

export interface ConversationCustomer {
  id: string;
  nome_completo: string;
  cpf_cnpj: string;
  telefone: string | null;
  score: number;
  status: string;
}

export interface Conversation {
  id: string;
  customer_id: string;
  customer: ConversationCustomer | null;
  channel: string;
  status: 'active' | 'waiting' | 'closed' | 'manual';
  agent_mode: 'auto' | 'manual';
  last_message_at: string;
  unread_count: number;
  last_message_preview: string | null;
  criado_em: string;
  updated_at: string;
}

export interface ConversationListResponse {
  items: Conversation[];
  total: number;
  page: number;
  size: number;
}

export interface SendMessagePayload {
  content: string;
  role?: 'user' | 'assistant';
}

export interface Broadcast {
  id: string;
  name: string;
  template: string;
  audience_filter: Record<string, unknown> | null;
  status: 'draft' | 'scheduled' | 'sending' | 'sent' | 'failed';
  scheduled_at: string | null;
  sent_count: number;
  total_recipients: number;
  criado_em: string;
}

export interface BroadcastListResponse {
  items: Broadcast[];
  total: number;
  page: number;
  size: number;
}

export interface BroadcastCreatePayload {
  name: string;
  template: string;
  audience_filter?: Record<string, unknown>;
  scheduled_at?: string;
}

@Injectable({ providedIn: 'root' })
export class ConversationService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = `${environment.apiBaseUrl}/conversations`;
  private readonly broadcastUrl = `${environment.apiBaseUrl}/broadcasts`;

  async list(params: {
    status?: string;
    page?: number;
    size?: number;
  } = {}): Promise<ConversationListResponse> {
    let httpParams = new HttpParams();
    if (params.status) httpParams = httpParams.set('status', params.status);
    if (params.page !== undefined) httpParams = httpParams.set('page', params.page.toString());
    if (params.size !== undefined) httpParams = httpParams.set('page_size', params.size.toString());

    const raw = await firstValueFrom(
      this.http.get<{ items: any[]; total: number; page: number; page_size: number }>(
        this.apiUrl,
        { params: httpParams },
      ),
    );
    // Backend retorna shape ligeiramente diferente — normaliza pro front.
    return {
      items: raw.items.map((c) => this.normalizeConversation(c)),
      total: raw.total,
      page: raw.page,
      size: raw.page_size,
    };
  }

  private normalizeConversation(c: any): Conversation {
    const agentMode: 'auto' | 'manual' = c.agent_active === false ? 'manual' : 'auto';
    const status =
      c.status === 'ativa' ? 'active'
      : c.status === 'pausada' ? 'waiting'
      : c.status === 'encerrada' ? 'closed'
      : (c.status as Conversation['status']);
    return {
      id: c.id,
      customer_id: c.customer_id ?? '',
      customer: c.customer ?? null,
      channel: c.channel,
      status,
      agent_mode: agentMode,
      last_message_at: c.last_message_at ?? c.created_at,
      unread_count: c.unread_count ?? 0,
      last_message_preview: c.last_message_preview ?? null,
      criado_em: c.created_at,
      updated_at: c.updated_at ?? c.created_at,
    };
  }

  async getMessages(conversationId: string): Promise<ConversationMessage[]> {
    const raw = await firstValueFrom(
      this.http.get<any[]>(`${this.apiUrl}/${conversationId}/messages`),
    );
    // Backend retorna msgs em ordem desc; mostra ascendente (mais antigas em cima).
    return raw
      .map((m) => this.normalizeMessage(m, conversationId))
      .sort((a, b) => a.criado_em.localeCompare(b.criado_em));
  }

  async sendMessage(conversationId: string, payload: SendMessagePayload): Promise<ConversationMessage> {
    const raw = await firstValueFrom(
      this.http.post<any>(`${this.apiUrl}/${conversationId}/messages`, {
        content_text: payload.content,
      }),
    );
    return this.normalizeMessage(raw, conversationId);
  }

  private normalizeMessage(m: any, conversationId: string): ConversationMessage {
    const role: 'user' | 'assistant' | 'system' =
      m.sent_by === 'customer' ? 'user'
      : m.sent_by === 'agent' ? 'assistant'
      : (m.role ?? 'system');
    return {
      id: m.id,
      conversation_id: m.conversation_id ?? conversationId,
      role,
      content: m.content_text ?? m.content ?? '',
      metadata: m.metadata ?? null,
      criado_em: m.sent_at ?? m.created_at,
    };
  }

  async takeover(conversationId: string): Promise<Conversation> {
    return firstValueFrom(
      this.http.post<Conversation>(`${this.apiUrl}/${conversationId}/takeover`, {}),
    );
  }

  async resumeAgent(conversationId: string): Promise<Conversation> {
    return firstValueFrom(
      this.http.post<Conversation>(`${this.apiUrl}/${conversationId}/resume-agent`, {}),
    );
  }

  async listBroadcasts(params: {
    page?: number;
    size?: number;
  } = {}): Promise<Broadcast[]> {
    let httpParams = new HttpParams();
    if (params.page !== undefined) httpParams = httpParams.set('page', params.page.toString());
    if (params.size !== undefined) httpParams = httpParams.set('size', params.size.toString());

    return firstValueFrom(
      this.http.get<Broadcast[]>(this.broadcastUrl, { params: httpParams }),
    );
  }

  async createBroadcast(payload: BroadcastCreatePayload): Promise<Broadcast> {
    return firstValueFrom(
      this.http.post<Broadcast>(this.broadcastUrl, payload),
    );
  }

  async sendBroadcast(broadcastId: string): Promise<unknown> {
    return firstValueFrom(
      this.http.post(`${this.broadcastUrl}/${broadcastId}/send`, {}),
    );
  }

  async getChannelStatus(): Promise<{ configured: boolean; healthy: boolean; provider: string | null; message: string }> {
    return firstValueFrom(
      this.http.get<{ configured: boolean; healthy: boolean; provider: string | null; message: string }>(
        `${this.broadcastUrl}/channel-status`,
      ),
    );
  }

  async listChannels(): Promise<Record<string, unknown>[]> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>[]>(`${this.broadcastUrl}/channels`),
    );
  }
}
