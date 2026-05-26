import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';

// Story 12-8 — PT-BR puro alinhado com Pydantic (12-3c).

export interface Endereco {
  logradouro: string | null;
  numero: string | null;
  complemento: string | null;
  bairro: string | null;
  cidade: string | null;
  estado: string | null;
  cep: string | null;
}

export interface Cliente {
  id: string;
  nome_completo: string;
  cpf_cnpj: string;
  telefone: string | null;
  email: string | null;
  data_nascimento: string | null;
  foto_url: string | null;
  observacoes: string | null;
  score: number;
  status: string;
  endereco: Endereco | null;
  tags: string[] | null;
  metadata_extensoes: Record<string, unknown> | null;
  criado_em: string;
  atualizado_em: string;
}

export interface ClienteListResponse {
  items: Cliente[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface ClienteCreatePayload {
  nome_completo: string;
  cpf_cnpj: string;
  telefone?: string;
  email?: string;
  data_nascimento?: string;
  observacoes?: string;
  status?: string;
  endereco?: Partial<Endereco>;
  tags?: string[];
  metadata_extensoes?: Record<string, unknown>;
}

export interface AnexoCliente {
  id: string;
  cliente_id: string;
  tipo: string;
  url: string;
  mime: string | null;
  tamanho_bytes: number | null;
  criado_em: string;
}

@Injectable({ providedIn: 'root' })
export class CustomerService {
  private readonly http = inject(HttpClient);
  // Mantém path /customers (não está na lista de URL aliases do 12-3e ainda).
  private readonly apiUrl = `${environment.apiBaseUrl}/customers`;

  async list(params: {
    search?: string;
    status?: string;
    page?: number;
    size?: number;
  }): Promise<ClienteListResponse> {
    let httpParams = new HttpParams();
    if (params.search) httpParams = httpParams.set('search', params.search);
    if (params.status && params.status !== 'todos')
      httpParams = httpParams.set('status', params.status);
    if (params.page !== undefined) httpParams = httpParams.set('page', params.page.toString());
    if (params.size !== undefined) httpParams = httpParams.set('size', params.size.toString());

    return firstValueFrom(
      this.http.get<ClienteListResponse>(this.apiUrl, { params: httpParams }),
    );
  }

  async getById(id: string): Promise<Cliente> {
    return firstValueFrom(this.http.get<Cliente>(`${this.apiUrl}/${id}`));
  }

  async create(payload: ClienteCreatePayload): Promise<Cliente> {
    return firstValueFrom(this.http.post<Cliente>(this.apiUrl, payload));
  }

  async update(id: string, payload: Partial<ClienteCreatePayload>): Promise<Cliente> {
    return firstValueFrom(this.http.patch<Cliente>(`${this.apiUrl}/${id}`, payload));
  }

  async delete(id: string): Promise<void> {
    return firstValueFrom(this.http.delete<void>(`${this.apiUrl}/${id}`));
  }

  async uploadAttachment(id: string, file: File, tipo = 'documento'): Promise<AnexoCliente> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('tipo', tipo);
    return firstValueFrom(
      this.http.post<AnexoCliente>(`${this.apiUrl}/${id}/attachments`, formData),
    );
  }
}
