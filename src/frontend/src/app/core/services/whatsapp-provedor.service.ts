import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../../environments/environment';

export interface CampoProvedor {
  key: string;
  label: string;
  type: 'text' | 'password' | 'url';
  required: boolean;
}

export interface OpcaoProvedor {
  id: string;
  label: string;
  help: string;
  campos_provedor: CampoProvedor[];
  campos_instancia: CampoProvedor[];
  disponivel: boolean;
  multi_numero: boolean;
}

export interface ProvedorConfig {
  id: string;
  empresa_id: string;
  provedor: string;
  config: Record<string, string>;
  ativo: boolean;
  atualizado_em: string | null;
}

export interface ProvedorEOpcoes {
  config: ProvedorConfig | null;
  opcoes: OpcaoProvedor[];
}

export interface SalvarPayload {
  provedor: string;
  config: Record<string, string>;
  forcar?: boolean;
}

export interface ConflitoInstanciasError {
  message: string;
  instancias_afetadas: number;
  instancia_ids: string[];
  como_resolver: string;
}

/** Lançado quando o backend responde 409 (trocando de provider com instâncias). */
export class WhatsappProvedorConflitoError extends Error {
  constructor(public readonly detalhe: ConflitoInstanciasError) {
    super(detalhe.message);
  }
}

@Injectable({ providedIn: 'root' })
export class WhatsappProvedorService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/admin/whatsapp-provedor`;

  async obter(): Promise<ProvedorEOpcoes> {
    return firstValueFrom(this.http.get<ProvedorEOpcoes>(this.baseUrl));
  }

  async salvar(payload: SalvarPayload): Promise<ProvedorConfig> {
    try {
      return await firstValueFrom(this.http.put<ProvedorConfig>(this.baseUrl, payload));
    } catch (err) {
      if (err instanceof HttpErrorResponse && err.status === 409) {
        const detalhe = (err.error?.detail ?? err.error) as ConflitoInstanciasError;
        throw new WhatsappProvedorConflitoError(detalhe);
      }
      throw err;
    }
  }
}
