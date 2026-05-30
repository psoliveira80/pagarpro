import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../../environments/environment';

export interface NumeroWhatsApp {
  credencial_id: string;
  provedor: string;
  apelido: string | null;
  instance_id: string | null;
  numero_e164: string | null;
  status_whatsapp: string;
  eh_principal: boolean;
  clientes_atribuidos: number;
  ultimo_health_check: string | null;
  motivo_banimento: string | null;
}

export interface EditarNumeroPayload {
  apelido?: string | null;
  numero_e164?: string | null;
  config?: Record<string, string>;
}

export interface NovoNumeroPayload {
  apelido?: string | null;
  numero_e164: string;
  eh_principal?: boolean;
  config: Record<string, string>;
}

export type StatusWhatsApp = 'ativo' | 'inativo' | 'banido' | 'desconectado';

@Injectable({ providedIn: 'root' })
export class CanaisWhatsappService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/numeros-cobranca`;

  async listar(): Promise<NumeroWhatsApp[]> {
    return firstValueFrom(this.http.get<NumeroWhatsApp[]>(this.baseUrl));
  }

  async cadastrar(payload: NovoNumeroPayload): Promise<NumeroWhatsApp> {
    return firstValueFrom(
      this.http.post<NumeroWhatsApp>(this.baseUrl, payload),
    );
  }

  async marcarBanido(credencialId: string, motivo: string): Promise<{ clientes_migrados: number }> {
    return firstValueFrom(
      this.http.put<{ clientes_migrados: number }>(
        `${this.baseUrl}/${credencialId}/marcar-banido`,
        { motivo },
      ),
    );
  }

  async marcarAtivo(credencialId: string): Promise<void> {
    return firstValueFrom(
      this.http.put<void>(`${this.baseUrl}/${credencialId}/marcar-ativo`, {}),
    );
  }

  async marcarPrincipal(credencialId: string): Promise<void> {
    return firstValueFrom(
      this.http.put<void>(`${this.baseUrl}/${credencialId}/marcar-principal`, {}),
    );
  }

  async editar(credencialId: string, payload: EditarNumeroPayload): Promise<NumeroWhatsApp> {
    return firstValueFrom(
      this.http.put<NumeroWhatsApp>(`${this.baseUrl}/${credencialId}`, payload),
    );
  }

  async excluir(credencialId: string): Promise<void> {
    return firstValueFrom(
      this.http.delete<void>(`${this.baseUrl}/${credencialId}`),
    );
  }

  async moverClientes(
    credencialId: string,
    destinoId: string,
    motivo?: string,
  ): Promise<{ clientes_migrados: number; destino: string }> {
    return firstValueFrom(
      this.http.post<{ clientes_migrados: number; destino: string }>(
        `${this.baseUrl}/${credencialId}/mover-clientes`,
        { destino_credencial_id: destinoId, motivo },
      ),
    );
  }
}
