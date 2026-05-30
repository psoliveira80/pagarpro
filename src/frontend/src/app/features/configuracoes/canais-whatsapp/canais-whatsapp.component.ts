import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import { DatePipe } from '@angular/common';

import { RouterLink } from '@angular/router';

import {
  CanaisWhatsappService,
  NumeroWhatsApp,
} from '../../../core/services/canais-whatsapp.service';
import {
  OpcaoProvedor,
  ProvedorConfig,
  WhatsappProvedorService,
} from '../../../core/services/whatsapp-provedor.service';
import { AdminService } from '../../../core/services/admin.service';
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
  imports: [UiIconComponent, DatePipe, RouterLink, ModalComponent, ToastComponent],
  templateUrl: './canais-whatsapp.component.html',
  styleUrl: './canais-whatsapp.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CanaisWhatsappComponent implements OnInit {
  private readonly service = inject(CanaisWhatsappService);
  private readonly provedorService = inject(WhatsappProvedorService);
  private readonly adminService = inject(AdminService);
  private readonly toast = inject(ToastService);
  private readonly confirm = inject(ConfirmService);

  readonly numeros = signal<NumeroWhatsApp[]>([]);
  readonly provedorConfig = signal<ProvedorConfig | null>(null);
  readonly opcoesProvedor = signal<OpcaoProvedor[]>([]);
  readonly isLoading = signal(true);
  readonly limitePorNumero = signal(150);
  readonly testandoId = signal<string | null>(null);
  readonly migrandoId = signal<string | null>(null);

  readonly mostrarFormNovo = signal(false);
  readonly novoApelido = signal('');
  readonly novoNumeroE164 = signal('');
  readonly novoPrincipal = signal(false);
  readonly novoConfig = signal<Record<string, string>>({});
  readonly salvandoNovo = signal(false);

  // ─── Menu de ações, edição, mover, excluir ───
  readonly menuAbertoId = signal<string | null>(null);

  readonly editandoNumero = signal<NumeroWhatsApp | null>(null);
  readonly editApelido = signal('');
  readonly editNumeroE164 = signal('');
  readonly editConfig = signal<Record<string, string>>({});
  readonly salvandoEdicao = signal(false);

  readonly movendoNumero = signal<NumeroWhatsApp | null>(null);
  readonly destinoMover = signal<string>('');
  readonly motivoMover = signal('');
  readonly salvandoMover = signal(false);

  readonly destinosDisponiveis = computed(() => {
    const origem = this.movendoNumero();
    if (!origem) return [];
    return this.numeros().filter(
      (n) =>
        n.credencial_id !== origem.credencial_id &&
        n.status_whatsapp === 'ativo',
    );
  });

  readonly opcaoProvedorAtivo = computed<OpcaoProvedor | null>(() => {
    const cfg = this.provedorConfig();
    if (!cfg) return null;
    return this.opcoesProvedor().find((o) => o.id === cfg.provedor) ?? null;
  });

  readonly labelProvedorAtivo = computed<string>(() => {
    const op = this.opcaoProvedorAtivo();
    return op ? op.label : '—';
  });

  readonly temProvedorConfigurado = computed(() => this.provedorConfig() !== null);

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
    await Promise.all([this.carregar(), this.carregarProvedorConfig()]);
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

  async carregarProvedorConfig(): Promise<void> {
    try {
      const r = await this.provedorService.obter();
      this.provedorConfig.set(r.config);
      this.opcoesProvedor.set(r.opcoes);
    } catch {
      // Silencioso — empty state vai mostrar a falta de provedor
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
    return n.apelido?.trim() || n.instance_id || '(sem nome)';
  }

  numeroOuPlaceholder(n: NumeroWhatsApp): string {
    return n.numero_e164?.trim() || '(número não informado)';
  }

  toggleMenu(id: string): void {
    this.menuAbertoId.update((cur) => (cur === id ? null : id));
  }

  fecharMenu(): void {
    this.menuAbertoId.set(null);
  }

  // ─── Editar ───
  abrirEdicao(n: NumeroWhatsApp): void {
    this.fecharMenu();
    this.editandoNumero.set(n);
    this.editApelido.set(n.apelido ?? '');
    this.editNumeroE164.set(n.numero_e164 ?? '');
    const op = this.opcaoProvedorAtivo();
    const cfg: Record<string, string> = {};
    if (op) {
      for (const f of op.campos_instancia) {
        if (f.key === 'instance_id' && n.instance_id) cfg[f.key] = n.instance_id;
      }
    }
    this.editConfig.set(cfg);
  }

  fecharEdicao(): void {
    this.editandoNumero.set(null);
  }

  setEditConfig(key: string, value: string): void {
    this.editConfig.update((c) => ({ ...c, [key]: value }));
  }

  getEditConfig(key: string): string {
    return this.editConfig()[key] ?? '';
  }

  async salvarEdicao(): Promise<void> {
    const n = this.editandoNumero();
    if (!n) return;
    this.salvandoEdicao.set(true);
    try {
      const cfg = this.editConfig();
      const payload = {
        apelido: this.editApelido().trim() || null,
        numero_e164: this.editNumeroE164().trim() || null,
        config: Object.keys(cfg).length > 0 ? cfg : undefined,
      };
      await this.service.editar(n.credencial_id, payload);
      this.toast.show({ message: 'Número atualizado', type: 'success' });
      this.fecharEdicao();
      await this.carregar();
    } catch (err) {
      const detalhe =
        (err as { error?: { detail?: string } })?.error?.detail ?? 'Erro ao salvar';
      this.toast.show({ message: detalhe, type: 'error' });
    } finally {
      this.salvandoEdicao.set(false);
    }
  }

  // ─── Excluir ───
  async excluir(n: NumeroWhatsApp): Promise<void> {
    this.fecharMenu();
    if (n.clientes_atribuidos > 0) {
      this.toast.show({
        message: `Este número tem ${n.clientes_atribuidos} cliente(s) atribuído(s). Mova ou banir antes de excluir.`,
        type: 'warning',
      });
      return;
    }
    const ok = await this.confirm.confirm({
      text: `Excluir ${this.apelidoOuPlaceholder(n)}? Esta ação é permanente.`,
      type: 'danger',
    });
    if (!ok) return;
    try {
      await this.service.excluir(n.credencial_id);
      this.toast.show({ message: 'Número excluído', type: 'success' });
      await this.carregar();
    } catch (err) {
      const detalhe =
        (err as { error?: { detail?: { message?: string } | string } })?.error?.detail;
      const msg = typeof detalhe === 'string' ? detalhe : detalhe?.message ?? 'Erro ao excluir';
      this.toast.show({ message: msg, type: 'error' });
    }
  }

  // ─── Mover clientes ───
  abrirMover(n: NumeroWhatsApp): void {
    this.fecharMenu();
    if (n.clientes_atribuidos === 0) {
      this.toast.show({
        message: 'Este número não tem clientes para mover.',
        type: 'info',
      });
      return;
    }
    this.movendoNumero.set(n);
    this.destinoMover.set('');
    this.motivoMover.set('');
  }

  fecharMover(): void {
    this.movendoNumero.set(null);
  }

  async confirmarMover(): Promise<void> {
    const origem = this.movendoNumero();
    const destinoId = this.destinoMover();
    if (!origem || !destinoId) return;
    this.salvandoMover.set(true);
    try {
      const r = await this.service.moverClientes(
        origem.credencial_id,
        destinoId,
        this.motivoMover().trim() || undefined,
      );
      this.toast.show({
        message: `${r.clientes_migrados} cliente(s) migrado(s).`,
        type: 'success',
      });
      this.fecharMover();
      await this.carregar();
    } catch (err) {
      const detalhe =
        (err as { error?: { detail?: string } })?.error?.detail ?? 'Erro ao mover clientes';
      this.toast.show({ message: detalhe, type: 'error' });
    } finally {
      this.salvandoMover.set(false);
    }
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

  setNovoConfig(key: string, value: string): void {
    this.novoConfig.update((c) => ({ ...c, [key]: value }));
  }

  getNovoConfig(key: string): string {
    return this.novoConfig()[key] ?? '';
  }

  get podeSalvarNovo(): boolean {
    const op = this.opcaoProvedorAtivo();
    if (!op || !op.disponivel) return false;
    if (this.novoNumeroE164().trim().length === 0) return false;
    return op.campos_instancia
      .filter((f) => f.required)
      .every((f) => this.getNovoConfig(f.key).trim().length > 0);
  }

  async salvarNovoNumero(): Promise<void> {
    if (!this.podeSalvarNovo) return;
    const op = this.opcaoProvedorAtivo();
    if (!op) return;
    this.salvandoNovo.set(true);
    try {
      const config: Record<string, string> = {};
      for (const f of op.campos_instancia) {
        const v = this.getNovoConfig(f.key).trim();
        if (v.length > 0) config[f.key] = v;
      }
      await this.service.cadastrar({
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
        (err as { error?: { detail?: string | { message?: string } } })?.error?.detail;
      const msg = typeof detalhe === 'string'
        ? detalhe
        : detalhe?.message ?? 'Erro ao adicionar número';
      this.toast.show({ message: msg, type: 'error' });
    } finally {
      this.salvandoNovo.set(false);
    }
  }
}
