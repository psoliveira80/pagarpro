import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
  OnInit,
  OnDestroy,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import { UiIconComponent } from '../../shared/components/icon/icon.component';
import { CustomSelectComponent, SelectOption } from '../../shared/components/custom-select/custom-select.component';
import {
  ReceivableService,
  TituloReceber,
} from '../../core/services/receivable.service';
import { WriteOffModalComponent } from './write-off-modal.component';
import { PixQrModalComponent } from './pix-qr-modal.component';
import { RenegotiationModalComponent } from './renegotiation-modal.component';
import { ConfirmService } from '../../shared/services/confirm.service';

@Component({
  selector: 'app-receivables-list',
  standalone: true,
  imports: [FormsModule, UiIconComponent, WriteOffModalComponent, PixQrModalComponent, RenegotiationModalComponent, CustomSelectComponent],
  templateUrl: './receivables-list.component.html',
  styleUrl: './receivables-list.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ReceivablesListComponent implements OnInit, OnDestroy {
  private readonly receivableService = inject(ReceivableService);
  private readonly confirmService = inject(ConfirmService);
  private readonly searchSubject = new Subject<string>();
  private searchSub: { unsubscribe(): void } | null = null;

  readonly receivables = signal<TituloReceber[]>([]);
  readonly total = signal(0);
  readonly totalAmount = signal(0);
  readonly totalPaid = signal(0);
  readonly totalOverdue = signal(0);
  readonly page = signal(1);
  readonly size = signal(10);
  readonly search = signal('');
  readonly statusFilter = signal('todos');
  readonly statusOptions: SelectOption[] = [
    { value: 'todos', label: 'Todos os status' },
    { value: 'em_aberto', label: 'Em Aberto' },
    { value: 'pago', label: 'Pago' },
    { value: 'pago_parcial', label: 'Pago Parcial' },
    { value: 'pago_aguardando_verificacao', label: 'Aguardando Verificação' },
    { value: 'vencido', label: 'Vencido' },
    { value: 'cancelado', label: 'Cancelado' },
    { value: 'renegociado', label: 'Renegociado' },
  ];
  readonly dateFrom = signal('');
  readonly dateTo = signal('');
  readonly isLoading = signal(false);
  readonly error = signal('');
  readonly actionMenuId = signal<string | null>(null);

  // Modals
  readonly writeOffOpen = signal(false);
  readonly writeOffReceivable = signal<TituloReceber | null>(null);
  readonly pixQrOpen = signal(false);
  readonly pixQrReceivableId = signal('');
  readonly renegotiationOpen = signal(false);
  readonly selectedForRenegotiation = signal<TituloReceber[]>([]);

  readonly totalPages = computed(() => Math.ceil(this.total() / this.size()) || 1);
  readonly pages = computed(() => {
    const tp = this.totalPages();
    const current = this.page();
    const result: number[] = [];
    const start = Math.max(1, current - 2);
    const end = Math.min(tp, current + 2);
    for (let i = start; i <= end; i++) result.push(i);
    return result;
  });

  ngOnInit(): void {
    this.searchSub = this.searchSubject
      .pipe(debounceTime(300), distinctUntilChanged())
      .subscribe((term) => {
        this.search.set(term);
        this.page.set(1);
        this.loadReceivables();
      });
    this.loadReceivables();
  }

  ngOnDestroy(): void {
    this.searchSub?.unsubscribe();
  }

  onSearchInput(value: string): void {
    this.searchSubject.next(value);
  }

  onStatusChange(value: string): void {
    this.statusFilter.set(value);
    this.page.set(1);
    this.loadReceivables();
  }

  onDateFromChange(value: string): void {
    this.dateFrom.set(value);
    this.page.set(1);
    this.loadReceivables();
  }

  onDateToChange(value: string): void {
    this.dateTo.set(value);
    this.page.set(1);
    this.loadReceivables();
  }

  goToPage(p: number): void {
    if (p < 1 || p > this.totalPages()) return;
    this.page.set(p);
    this.loadReceivables();
  }

  toggleActionMenu(id: string): void {
    this.actionMenuId.set(this.actionMenuId() === id ? null : id);
  }

  // Write-off
  openWriteOff(receivable: TituloReceber): void {
    this.writeOffReceivable.set(receivable);
    this.writeOffOpen.set(true);
    this.actionMenuId.set(null);
  }

  closeWriteOff(): void {
    this.writeOffOpen.set(false);
    this.writeOffReceivable.set(null);
  }

  onWriteOffSaved(): void {
    this.closeWriteOff();
    this.loadReceivables();
  }

  // Pix QR
  openPixQr(receivable: TituloReceber): void {
    this.pixQrReceivableId.set(receivable.id);
    this.pixQrOpen.set(true);
    this.actionMenuId.set(null);
  }

  closePixQr(): void {
    this.pixQrOpen.set(false);
  }

  // Reverse
  async reverseReceivable(receivable: TituloReceber): Promise<void> {
    this.actionMenuId.set(null);
    const ok = await this.confirmService.confirm({ text: 'Tem certeza que deseja estornar este recebível?', type: 'danger' });
    if (!ok) return;
    try {
      await this.receivableService.estornar(receivable.id, 'Estorno via lista');
      this.loadReceivables();
    } catch {
      // Error handled
    }
  }

  // Renegotiation
  openRenegotiation(receivable: TituloReceber): void {
    this.selectedForRenegotiation.set([receivable]);
    this.renegotiationOpen.set(true);
    this.actionMenuId.set(null);
  }

  closeRenegotiation(): void {
    this.renegotiationOpen.set(false);
    this.selectedForRenegotiation.set([]);
  }

  onRenegotiationSaved(): void {
    this.closeRenegotiation();
    this.loadReceivables();
  }

  async loadReceivables(): Promise<void> {
    this.isLoading.set(true);
    this.error.set('');
    try {
      const response = await this.receivableService.list({
        search: this.search(),
        status: this.statusFilter(),
        date_from: this.dateFrom(),
        date_to: this.dateTo(),
        page: this.page(),
        size: this.size(),
      });
      this.receivables.set(response.items);
      this.total.set(response.total);
      this.totalAmount.set(response.agregados?.total_em_aberto ?? 0);
      this.totalPaid.set(response.agregados?.total_pago ?? 0);
      this.totalOverdue.set(response.agregados?.total_vencido ?? 0);
    } catch {
      this.receivables.set([]);
      this.total.set(0);
      this.error.set('Erro ao carregar recebíveis. Verifique sua conexão.');
    } finally {
      this.isLoading.set(false);
    }
  }

  statusLabel(status: string): string {
    const map: Record<string, string> = {
      em_aberto: 'Em Aberto',
      pago_aguardando_verificacao: 'Aguardando Verificação',
      pago: 'Pago',
      pago_parcial: 'Pago Parcial',
      vencido: 'Vencido',
      cancelado: 'Cancelado',
      renegociado: 'Renegociado',
    };
    return map[status] ?? status;
  }

  statusClass(status: string): string {
    const map: Record<string, string> = {
      em_aberto: 'bg-yellow-500/20 text-yellow-400',
      pago_aguardando_verificacao: 'bg-blue-500/20 text-blue-400',
      pago: 'bg-green-500/20 text-green-400',
      pago_parcial: 'bg-blue-500/20 text-blue-400',
      vencido: 'bg-red-500/20 text-red-400',
      cancelado: 'bg-gray-500/20 text-gray-400',
      renegociado: 'bg-purple-500/20 text-purple-400',
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
}
