import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../../environments/environment';

export interface NumeroWhatsApp {
  credencial_id: string;
  provedor: string;
  instance_id: string | null;
  numero_e164: string | null;
  status_whatsapp: string;
  eh_principal: boolean;
  clientes_atribuidos: number;
  ultimo_health_check: string | null;
  motivo_banimento: string | null;
}

export type StatusWhatsApp = 'ativo' | 'inativo' | 'banido' | 'desconectado';

@Injectable({ providedIn: 'root' })
export class CanaisWhatsappService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/numeros-cobranca`;

  async listar(): Promise<NumeroWhatsApp[]> {
    return firstValueFrom(this.http.get<NumeroWhatsApp[]>(this.baseUrl));
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
}
