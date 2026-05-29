import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import { DatePipe } from '@angular/common';

import {
  CanaisWhatsappService,
  NumeroWhatsApp,
} from '../../../core/services/canais-whatsapp.service';
import { AdminService, IntegrationCreate } from '../../../core/services/admin.service';
import { UiIconComponent } from '../../../shared/components/icon/icon.component';
import { ModalComponent } from '../../../shared/components/modal/modal.component';
import { ToastComponent } from '../../../shared/components/toast/toast.component';
import { ToastService } from '../../../shared/components/toast/toast.service';
import { ConfirmService } from '../../../shared/services/confirm.service';

interface ResumoStatus {
  conectados: number;
  desconectados: number;
  banidos: number;
  total: number;
}

@Component({
  selector: 'app-canais-whatsapp',
  standalone: true,
  imports: [UiIconComponent, DatePipe, ModalComponent, ToastComponent],
  templateUrl: './canais-whatsapp.component.html',
  styleUrl: './canais-whatsapp.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CanaisWhatsappComponent implements OnInit {
  private readonly service = inject(CanaisWhatsappService);
  private readonly adminService = inject(AdminService);
  private readonly toast = inject(ToastService);
  private readonly confirm = inject(ConfirmService);

  readonly numeros = signal<NumeroWhatsApp[]>([]);
  readonly isLoading = signal(true);
  readonly limitePorNumero = signal(150);
  readonly testandoId = signal<string | null>(null);
  readonly migrandoId = signal<string | null>(null);

  readonly mostrarFormNovo = signal(false);
  readonly novoApelido = signal('');
  readonly novoInstanceId = signal('');
  readonly novoInstanceToken = signal('');
  readonly novoNumeroE164 = signal('');
  readonly novoPrincipal = signal(false);
  readonly salvandoNovo = signal(false);

  readonly resumoStatus = computed<ResumoStatus>(() => {
    const list = this.numeros();
    return {
      conectados: list.filter((n) => n.status_whatsapp === 'ativo').length,
      desconectados: list.filter((n) => n.status_whatsapp === 'desconectado').length,
      banidos: list.filter((n) => n.status_whatsapp === 'banido').length,
      total: list.length,
    };
  });

  readonly capacidadeTotal = computed(() => {
    return this.numeros()
      .filter((n) => n.status_whatsapp === 'ativo')
      .reduce((acc) => acc + this.limitePorNumero(), 0);
  });

  readonly clientesAtribuidosAtivos = computed(() =>
    this.numeros()
      .filter((n) => n.status_whatsapp === 'ativo')
      .reduce((acc, n) => acc + n.clientes_atribuidos, 0),
  );

  readonly capacidadePctGlobal = computed(() => {
    const total = this.capacidadeTotal();
    return total === 0 ? 0 : Math.round((this.clientesAtribuidosAtivos() / total) * 100);
  });

  readonly capacidadeEsgotada = computed(
    () => this.capacidadeTotal() > 0 && this.clientesAtribuidosAtivos() >= this.capacidadeTotal(),
  );

  readonly capacidadeAlerta = computed(
    () => this.capacidadePctGlobal() >= 80 && !this.capacidadeEsgotada(),
  );

  async ngOnInit(): Promise<void> {
    await this.carregar();
  }

  async carregar(): Promise<void> {
    this.isLoading.set(true);
    try {
      this.numeros.set(await this.service.listar());
    } catch {
      this.toast.show({ message: 'Erro ao carregar números WhatsApp', type: 'error' });
    } finally {
      this.isLoading.set(false);
    }
  }

  ocupacaoPct(n: NumeroWhatsApp): number {
    const limite = this.limitePorNumero();
    return limite === 0 ? 0 : Math.min(100, Math.round((n.clientes_atribuidos / limite) * 100));
  }

  ocupacaoCorClasse(n: NumeroWhatsApp): string {
    const pct = this.ocupacaoPct(n);
    if (pct >= 100) return 'bg-[var(--danger)]';
    if (pct >= 80) return 'bg-[var(--warning)]';
    if (pct >= 60) return 'bg-yellow-500';
    return 'bg-[var(--success)]';
  }

  statusBadgeClasse(status: string): string {
    switch (status) {
      case 'ativo':
        return 'bg-[var(--success)]/15 text-[var(--success)]';
      case 'banido':
        return 'bg-[var(--danger)]/15 text-[var(--danger)]';
      case 'desconectado':
        return 'bg-[var(--warning)]/15 text-[var(--warning)]';
      default:
        return 'bg-[var(--text-muted)]/15 text-[var(--text-muted)]';
    }
  }

  statusLabel(status: string): string {
    switch (status) {
      case 'ativo':
        return 'Conectado';
      case 'banido':
        return 'Banido';
      case 'desconectado':
        return 'Desconectado';
      case 'inativo':
        return 'Inativo';
      default:
        return status;
    }
  }

  apelidoOuPlaceholder(n: NumeroWhatsApp): string {
    return n.instance_id ?? '(sem nome)';
  }

  async testarConexao(n: NumeroWhatsApp): Promise<void> {
    this.testandoId.set(n.credencial_id);
    try {
      const result = await this.adminService.testIntegration(n.credencial_id);
      const ok = result.status === 'healthy';
      this.toast.show({
        message: ok
          ? `Conexão OK (${result.latency_ms ?? 0} ms)`
          : `Falha: ${result.error ?? result.status}`,
        type: ok ? 'success' : 'error',
      });
      await this.carregar();
    } catch {
      this.toast.show({ message: 'Erro ao testar conexão', type: 'error' });
    } finally {
      this.testandoId.set(null);
    }
  }

  async marcarPrincipal(n: NumeroWhatsApp): Promise<void> {
    if (n.eh_principal) return;
    try {
      await this.service.marcarPrincipal(n.credencial_id);
      this.toast.show({ message: 'Número definido como padrão', type: 'success' });
      await this.carregar();
    } catch {
      this.toast.show({ message: 'Erro ao marcar como padrão', type: 'error' });
    }
  }

  async marcarAtivo(n: NumeroWhatsApp): Promise<void> {
    const ok = await this.confirm.confirm({
      text: `Reativar ${this.apelidoOuPlaceholder(n)}? Confirme que a sessão foi restabelecida no Evolution Go antes.`,
      type: 'info',
    });
    if (!ok) return;
    try {
      await this.service.marcarAtivo(n.credencial_id);
      this.toast.show({ message: 'Número reativado', type: 'success' });
      await this.carregar();
    } catch {
      this.toast.show({ message: 'Erro ao reativar número', type: 'error' });
    }
  }

  async marcarBanido(n: NumeroWhatsApp): Promise<void> {
    const ok = await this.confirm.confirm({
      text: `Banir ${this.apelidoOuPlaceholder(n)}? Os ${n.clientes_atribuidos} clientes vinculados serão migrados para outros números ativos.`,
      type: 'danger',
    });
    if (!ok) return;
    const motivo = window.prompt('Motivo do banimento (mín. 3 caracteres):', 'Banido manualmente pelo gestor');
    if (!motivo || motivo.trim().length < 3) {
      this.toast.show({ message: 'Motivo obrigatório', type: 'warning' });
      return;
    }
    this.migrandoId.set(n.credencial_id);
    try {
      const r = await this.service.marcarBanido(n.credencial_id, motivo.trim());
      this.toast.show({
        message: `${r.clientes_migrados} cliente(s) migrado(s) para outros números`,
        type: 'success',
      });
      await this.carregar();
    } catch {
      this.toast.show({ message: 'Erro ao banir número', type: 'error' });
    } finally {
      this.migrandoId.set(null);
    }
  }

  abrirFormNovoNumero(): void {
    this.novoApelido.set('');
    this.novoInstanceId.set('');
    this.novoInstanceToken.set('');
    this.novoNumeroE164.set('');
    this.novoPrincipal.set(false);
    this.mostrarFormNovo.set(true);
  }

  fecharFormNovoNumero(): void {
    this.mostrarFormNovo.set(false);
  }

  get podeSalvarNovo(): boolean {
    return (
      this.novoInstanceId().trim().length > 0 &&
      this.novoInstanceToken().trim().length > 0 &&
      this.novoNumeroE164().trim().length > 0
    );
  }

  async salvarNovoNumero(): Promise<void> {
    if (!this.podeSalvarNovo) return;
    const payload: IntegrationCreate = {
      category: 'whatsapp',
      provider: 'evolution_go',
      is_active: true,
      config: {
        instance_id: this.novoInstanceId().trim(),
        instance_token: this.novoInstanceToken().trim(),
        numero_e164: this.novoNumeroE164().trim(),
        apelido: this.novoApelido().trim() || null,
        eh_principal: this.novoPrincipal(),
        status_whatsapp: 'ativo',
      },
    };
    this.salvandoNovo.set(true);
    try {
      await this.adminService.createIntegration(payload);
      this.toast.show({ message: 'Número adicionado', type: 'success' });
      this.fecharFormNovoNumero();
      await this.carregar();
    } catch {
      this.toast.show({ message: 'Erro ao adicionar número', type: 'error' });
    } finally {
      this.salvandoNovo.set(false);
    }
  }
}
