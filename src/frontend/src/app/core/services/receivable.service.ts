import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';

// Story 12-8 — interfaces PT-BR puras, alinhadas com Pydantic backend (12-3c).
// URL path PT-BR (alias mapeado para /receivables via middleware story 12-3e).

export type TituloReceberStatus =
  | 'em_aberto'
  | 'pago_aguardando_verificacao'
  | 'pago'
  | 'pago_parcial'
  | 'vencido'
  | 'cancelado'
  | 'renegociado';

export interface TituloReceber {
  id: string;
  empresa_id: string;
  contrato_id: string;
  sequencia: number;
  data_vencimento: string;
  valor: number;
  valor_pago: number;
  status: TituloReceberStatus;
  pago_em: string | null;
  forma_pagamento: string | null;
  comprovante_url: string | null;
  observacoes: string | null;
  criado_em: string;
  atualizado_em: string;
}

export interface TituloReceberAgregados {
  total_em_aberto: number;
  total_vencido: number;
  total_pago: number;
}

export interface TituloReceberListResponse {
  items: TituloReceber[];
  total: number;
  page: number;
  size: number;
  pages: number;
  agregados: TituloReceberAgregados;
}

export interface ValorAtualizado {
  original: number;
  juros: number;
  multa: number;
  desconto: number;
  total: number;
}

export interface BaixaPayload {
  valor: number;
  pago_em: string;
  forma_pagamento: string;
  comprovante_arquivo?: string; // base64
}

export interface BaixaResponse {
  id: string;
  status: string;
  valor_pago: number;
  mensagem: string;
}

export interface BaixaParcialPayload {
  valor: number;
  pago_em: string;
  forma_pagamento: string;
}

export interface BaixaParcialResponse {
  id: string;
  status: string;
  valor_pago: number;
  titulo_remanescente_id: string;
  valor_remanescente: number;
  mensagem: string;
}

export interface NovaPlanilhaParams {
  valor_total: number;
  quantidade_parcelas: number;
  data_inicio: string;
  periodicidade: string;
  metodo: string;
}

export interface RenegociacaoPayload {
  titulos_ids: string[];
  nova_planilha: NovaPlanilhaParams;
}

export interface RenegociacaoResponse {
  quantidade_original: number;
  novos_titulos: TituloReceber[];
  mensagem: string;
}

export interface PixQrResponse {
  qr_imagem_base64: string;
  brcode: string;
}

export interface BaixaLotePayload {
  titulos_ids: string[];
  valor_total: number;
  pago_em: string;
  forma_pagamento: string;
}

@Injectable({ providedIn: 'root' })
export class ReceivableService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = `${environment.apiBaseUrl}/titulos-receber`;

  async list(params: {
    search?: string;
    status?: string;
    customer_id?: string;
    date_from?: string;
    date_to?: string;
    page?: number;
    size?: number;
  }): Promise<TituloReceberListResponse> {
    let httpParams = new HttpParams();
    if (params.search) httpParams = httpParams.set('search', params.search);
    if (params.status && params.status !== 'todos')
      httpParams = httpParams.set('status', params.status);
    if (params.customer_id) httpParams = httpParams.set('customer_id', params.customer_id);
    if (params.date_from) httpParams = httpParams.set('date_from', params.date_from);
    if (params.date_to) httpParams = httpParams.set('date_to', params.date_to);
    if (params.page !== undefined) httpParams = httpParams.set('page', params.page.toString());
    if (params.size !== undefined) httpParams = httpParams.set('size', params.size.toString());

    return firstValueFrom(
      this.http.get<TituloReceberListResponse>(this.apiUrl, { params: httpParams }),
    );
  }

  async getValorAtualizado(id: string, onDate?: string): Promise<ValorAtualizado> {
    let httpParams = new HttpParams();
    if (onDate) httpParams = httpParams.set('on_date', onDate);
    return firstValueFrom(
      this.http.get<ValorAtualizado>(`${this.apiUrl}/${id}/updated-value`, {
        params: httpParams,
      }),
    );
  }

  async baixar(id: string, payload: BaixaPayload): Promise<BaixaResponse> {
    return firstValueFrom(
      this.http.post<BaixaResponse>(`${this.apiUrl}/${id}/write-off`, payload),
    );
  }

  async baixarParcial(id: string, payload: BaixaParcialPayload): Promise<BaixaParcialResponse> {
    return firstValueFrom(
      this.http.post<BaixaParcialResponse>(`${this.apiUrl}/${id}/partial-write-off`, payload),
    );
  }

  async baixarLote(payload: BaixaLotePayload): Promise<unknown> {
    return firstValueFrom(
      this.http.post(`${this.apiUrl}/bulk-write-off`, payload),
    );
  }

  async getFilaValidacao(): Promise<{ items: TituloReceber[]; total: number; page: number; size: number; pages: number }> {
    return firstValueFrom(
      this.http.get<{ items: TituloReceber[]; total: number; page: number; size: number; pages: number }>(
        `${this.apiUrl}/validation-queue`,
      ),
    );
  }

  async validar(id: string, payload: { aprovado: boolean; observacoes?: string }): Promise<void> {
    return firstValueFrom(
      this.http.post<void>(`${this.apiUrl}/${id}/validate`, payload),
    );
  }

  async solicitarReenvio(id: string, observacoes: string): Promise<void> {
    return firstValueFrom(
      this.http.post<void>(`${this.apiUrl}/${id}/request-resubmission`, { observacoes }),
    );
  }

  async getPixQr(id: string): Promise<PixQrResponse> {
    return firstValueFrom(
      this.http.get<PixQrResponse>(`${this.apiUrl}/${id}/pix-qr`),
    );
  }

  async renegociar(payload: RenegociacaoPayload): Promise<RenegociacaoResponse> {
    return firstValueFrom(
      this.http.post<RenegociacaoResponse>(`${this.apiUrl}/renegotiate`, payload),
    );
  }

  async estornar(id: string, motivo: string, valor?: number): Promise<unknown> {
    return firstValueFrom(
      this.http.post(`${this.apiUrl}/${id}/reverse`, { motivo, valor }),
    );
  }
}
