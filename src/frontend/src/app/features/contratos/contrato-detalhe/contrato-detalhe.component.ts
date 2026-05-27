import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  OnInit,
} from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { UiIconComponent } from '../../../shared/components/icon/icon.component';
import {
  ContractService,
  Contrato,
  TituloReceberContrato,
  EventoContrato,
  LoteGeracao,
} from '../../../core/services/contract.service';
import { EdicaoLoteModalComponent } from '../edicao-lote-modal/edicao-lote-modal.component';
import { ConfirmService } from '../../../shared/services/confirm.service';

@Component({
  selector: 'app-contrato-detalhe',
  standalone: true,
  imports: [FormsModule, UiIconComponent, EdicaoLoteModalComponent],
  templateUrl: './contrato-detalhe.component.html',
  styleUrl: './contrato-detalhe.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ContratoDetalheComponent implements OnInit {
  private readonly contractService = inject(ContractService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly confirmService = inject(ConfirmService);

  readonly contract = signal<Contrato | null>(null);
  readonly installments = signal<TituloReceberContrato[]>([]);
  readonly events = signal<EventoContrato[]>([]);
  readonly generations = signal<LoteGeracao[]>([]);
  readonly isLoading = signal(false);
  readonly activeTab = signal<'parcelas' | 'historico' | 'geracoes'>('parcelas');
  readonly selectedInstallments = signal<Set<string>>(new Set());
  readonly bulkEditOpen = signal(false);

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) this.loadContract(id);
  }

  async loadContract(id: string): Promise<void> {
    this.isLoading.set(true);
    try {
      const contract = await this.contractService.getById(id);
      this.contract.set(contract);
      await this.loadTabData();
    } catch {
      // Error handled by interceptor
    } finally {
      this.isLoading.set(false);
    }
  }

  async loadTabData(): Promise<void> {
    const c = this.contract();
    if (!c) return;

    switch (this.activeTab()) {
      case 'parcelas':
        this.installments.set(c.titulos ?? []);
        break;
      case 'historico':
        try {
          const evts = await this.contractService.getEvents(c.id);
          this.events.set(evts.items);
        } catch {
          this.events.set([]);
        }
        break;
      case 'geracoes':
        try {
          const gens = await this.contractService.getGenerations(c.id);
          this.generations.set(gens);
        } catch {
          this.generations.set([]);
        }
        break;
    }
  }

  setTab(tab: 'parcelas' | 'historico' | 'geracoes'): void {
    this.activeTab.set(tab);
    this.loadTabData();
  }

  toggleInstallment(id: string): void {
    this.selectedInstallments.update((set) => {
      const newSet = new Set(set);
      if (newSet.has(id)) newSet.delete(id);
      else newSet.add(id);
      return newSet;
    });
  }

  isSelected(id: string): boolean {
    return this.selectedInstallments().has(id);
  }

  hasSelection(): boolean {
    return this.selectedInstallments().size > 0;
  }

  openBulkEdit(): void {
    this.bulkEditOpen.set(true);
  }

  closeBulkEdit(): void {
    this.bulkEditOpen.set(false);
  }

  async onBulkEditSaved(): Promise<void> {
    this.closeBulkEdit();
    this.selectedInstallments.set(new Set());
    const c = this.contract();
    if (c) await this.loadContract(c.id);
  }

  async activate(): Promise<void> {
    const c = this.contract();
    if (!c) return;
    try {
      await this.contractService.activate(c.id);
      await this.loadContract(c.id);
    } catch {
      // Error handled
    }
  }

  async terminate(): Promise<void> {
    const c = this.contract();
    if (!c) return;
    const okTerminate = await this.confirmService.confirm({ text: 'Tem certeza que deseja encerrar este contrato?', type: 'danger' });
    if (!okTerminate) return;
    try {
      await this.contractService.terminate(c.id, {
        motivo: 'Rescisão via detalhe do contrato',
        data_efetiva: new Date().toISOString().split('T')[0],
      });
      await this.loadContract(c.id);
    } catch {
      // Error handled
    }
  }

  async downloadPdf(): Promise<void> {
    const c = this.contract();
    if (!c) return;
    try {
      const blob = await this.contractService.getPdf(c.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `contrato-${c.numero}.pdf`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      // Error handled
    }
  }

  async rollbackGeneration(genId: string): Promise<void> {
    const c = this.contract();
    if (!c) return;
    const okRollback = await this.confirmService.confirm({ text: 'Tem certeza que deseja reverter para esta geração?', type: 'danger' });
    if (!okRollback) return;
    try {
      await this.contractService.rollbackGeneration(c.id, genId);
      await this.loadContract(c.id);
    } catch {
      // Error handled
    }
  }

  editContract(): void {
    // Navigate to edit or open inline edit
    const c = this.contract();
    if (c) this.router.navigate(['/sistema/contratos/novo'], { queryParams: { edit: c.id } });
  }

  goBack(): void {
    this.router.navigate(['/sistema/contratos']);
  }

  statusLabel(status: string): string {
    const map: Record<string, string> = {
      rascunho: 'Rascunho',
      ativo: 'Ativo',
      encerrado: 'Encerrado',
      pendente: 'Pendente',
      pago: 'Pago',
      vencido: 'Vencido',
      cancelado: 'Cancelado',
    };
    return map[status] ?? status;
  }

  statusClass(status: string): string {
    const map: Record<string, string> = {
      rascunho: 'bg-yellow-500/20 text-yellow-400',
      ativo: 'bg-green-500/20 text-green-400',
      encerrado: 'bg-gray-500/20 text-gray-400',
      pendente: 'bg-yellow-500/20 text-yellow-400',
      pago: 'bg-green-500/20 text-green-400',
      vencido: 'bg-red-500/20 text-red-400',
      cancelado: 'bg-gray-500/20 text-gray-400',
    };
    return map[status] ?? 'bg-gray-500/20 text-gray-400';
  }

  formatCurrency(value: number | null | undefined): string {
    const v = typeof value === 'number' && !isNaN(value) ? value : 0;
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v);
  }

  formatDate(date: string): string {
    return new Date(date).toLocaleDateString('pt-BR');
  }

  formatDateTime(date: string): string {
    return new Date(date).toLocaleString('pt-BR');
  }
}
