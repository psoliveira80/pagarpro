import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import { DatePipe } from '@angular/common';

import {
  CanaisWhatsappService,
  NumeroWhatsApp,
  ProvedorWhatsApp,
} from '../../../core/services/canais-whatsapp.service';
import { AdminService } from '../../../core/services/admin.service';
import { CustomSelectComponent, SelectOption } from '../../../shared/components/custom-select/custom-select.component';
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
  imports: [UiIconComponent, DatePipe, CustomSelectComponent, ModalComponent, ToastComponent],
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
  readonly provedores = signal<ProvedorWhatsApp[]>([]);
  readonly isLoading = signal(true);
  readonly limitePorNumero = signal(150);
  readonly testandoId = signal<string | null>(null);
  readonly migrandoId = signal<string | null>(null);

  readonly mostrarFormNovo = signal(false);
  readonly novoProvedorId = signal('evolution_go');
  readonly novoApelido = signal('');
  readonly novoNumeroE164 = signal('');
  readonly novoPrincipal = signal(false);
  readonly novoConfig = signal<Record<string, string>>({});
  readonly salvandoNovo = signal(false);

  readonly provedorOptions = computed<SelectOption[]>(() =>
    this.provedores().map((p) => ({
      value: p.id,
      label: p.disponivel ? p.label : `${p.label} — em breve`,
    })),
  );

  readonly provedorSelecionado = computed<ProvedorWhatsApp | null>(() =>
    this.provedores().find((p) => p.id === this.novoProvedorId()) ?? null,
  );

  readonly provedoresEmUso = computed<string[]>(() =>
    Array.from(new Set(this.numeros().map((n) => n.provedor))),
  );

  readonly labelProvedorPrincipal = computed<string>(() => {
    const usados = this.provedoresEmUso();
    if (usados.length === 0) return 'Nenhum configurado';
    const dicionario = new Map(this.provedores().map((p) => [p.id, p.label]));
    return usados.map((u) => dicionario.get(u) ?? u).join(' + ');
  });

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
    await Promise.all([this.carregar(), this.carregarProvedores()]);
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

  async carregarProvedores(): Promise<void> {
    try {
      const lista = await this.service.listarProvedores();
      this.provedores.set(lista);
      // Default do seletor = provedor já em uso (se houver) ou primeiro disponível
      const emUso = this.provedoresEmUso();
      const padrao = emUso[0] ?? lista.find((p) => p.disponivel)?.id ?? 'evolution_go';
      this.novoProvedorId.set(padrao);
    } catch {
      this.toast.show({ message: 'Erro ao carregar provedores disponíveis', type: 'error' });
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
    this.novoNumeroE164.set('');
    this.novoPrincipal.set(false);
    this.novoConfig.set({});
    // Mantém o provedor selecionado no header como default
    this.mostrarFormNovo.set(true);
  }

  fecharFormNovoNumero(): void {
    this.mostrarFormNovo.set(false);
  }

  onProvedorNovoChange(id: string): void {
    this.novoProvedorId.set(id);
    this.novoConfig.set({});
  }

  setNovoConfig(key: string, value: string): void {
    this.novoConfig.update((c) => ({ ...c, [key]: value }));
  }

  getNovoConfig(key: string): string {
    return this.novoConfig()[key] ?? '';
  }

  get podeSalvarNovo(): boolean {
    const prov = this.provedorSelecionado();
    if (!prov || !prov.disponivel) return false;
    if (this.novoNumeroE164().trim().length === 0) return false;
    return prov.campos
      .filter((f) => f.required)
      .every((f) => this.getNovoConfig(f.key).trim().length > 0);
  }

  async salvarNovoNumero(): Promise<void> {
    if (!this.podeSalvarNovo) return;
    const prov = this.provedorSelecionado();
    if (!prov) return;
    this.salvandoNovo.set(true);
    try {
      const config: Record<string, string> = {};
      for (const f of prov.campos) {
        const v = this.getNovoConfig(f.key).trim();
        if (v.length > 0) config[f.key] = v;
      }
      await this.service.cadastrar({
        provedor: prov.id,
        apelido: this.novoApelido().trim() || null,
        numero_e164: this.novoNumeroE164().trim(),
        eh_principal: this.novoPrincipal(),
        config,
      });
      this.toast.show({ message: 'Número adicionado', type: 'success' });
      this.fecharFormNovoNumero();
      await this.carregar();
    } catch (err: unknown) {
      const detalhe =
        (err as { error?: { detail?: string } })?.error?.detail ?? 'Erro ao adicionar número';
      this.toast.show({ message: detalhe, type: 'error' });
    } finally {
      this.salvandoNovo.set(false);
    }
  }
}
