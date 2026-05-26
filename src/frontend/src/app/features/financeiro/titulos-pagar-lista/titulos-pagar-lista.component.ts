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
import { UiIconComponent } from '../../../shared/components/icon/icon.component';
import { ModalComponent } from '../../../shared/components/modal/modal.component';
import { CustomSelectComponent, SelectOption } from '../../../shared/components/custom-select/custom-select.component';
import {
  PayableService,
  TituloPagar,
} from '../../../core/services/payable.service';
import { TituloPagarFormComponent } from '../titulo-pagar-form/titulo-pagar-form.component';
import { PagamentoRapidoModalComponent } from '../pagamento-rapido-modal/pagamento-rapido-modal.component';

@Component({
  selector: 'app-titulos-pagar-lista',
  standalone: true,
  imports: [FormsModule, UiIconComponent, TituloPagarFormComponent, PagamentoRapidoModalComponent, CustomSelectComponent, ModalComponent],
  templateUrl: './titulos-pagar-lista.component.html',
  styleUrl: './titulos-pagar-lista.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TitulosPagarListaComponent implements OnInit, OnDestroy {
  private readonly payableService = inject(PayableService);
  private readonly searchSubject = new Subject<string>();
  private searchSub: { unsubscribe(): void } | null = null;

  readonly payables = signal<TituloPagar[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly size = signal(10);
  readonly search = signal('');
  readonly statusFilter = signal('todos');
  readonly statusOptions: SelectOption[] = [
    { value: 'todos', label: 'Todos os status' },
    { value: 'pendente', label: 'Pendente' },
    { value: 'pago', label: 'Pago' },
    { value: 'vencido', label: 'Vencido' },
    { value: 'cancelado', label: 'Cancelado' },
  ];
  readonly payMethodOptions: SelectOption[] = [
    { value: 'pix', label: 'Pix' },
    { value: 'boleto', label: 'Boleto' },
    { value: 'transferencia', label: 'Transferência' },
    { value: 'dinheiro', label: 'Dinheiro' },
  ];
  readonly isLoading = signal(false);
  readonly error = signal('');

  // Drawer
  readonly drawerOpen = signal(false);
  readonly editingPayable = signal<TituloPagar | null>(null);

  // Quick Pay
  readonly quickPayOpen = signal(false);

  // Pay modal
  readonly payingPayable = signal<TituloPagar | null>(null);
  readonly payMethod = signal('pix');
  readonly payDate = signal(new Date().toISOString().split('T')[0]);
  readonly isPaying = signal(false);

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
        this.loadPayables();
      });
    this.loadPayables();
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
    this.loadPayables();
  }

  goToPage(p: number): void {
    if (p < 1 || p > this.totalPages()) return;
    this.page.set(p);
    this.loadPayables();
  }

  openCreateDrawer(): void {
    this.editingPayable.set(null);
    this.drawerOpen.set(true);
  }

  openEditDrawer(payable: TituloPagar): void {
    this.editingPayable.set(payable);
    this.drawerOpen.set(true);
  }

  closeDrawer(): void {
    this.drawerOpen.set(false);
    this.editingPayable.set(null);
  }

  onDrawerSaved(): void {
    this.closeDrawer();
    this.loadPayables();
  }

  openQuickPay(): void {
    this.quickPayOpen.set(true);
  }

  closeQuickPay(): void {
    this.quickPayOpen.set(false);
  }

  onQuickPaySaved(): void {
    this.closeQuickPay();
    this.loadPayables();
  }

  openPayModal(payable: TituloPagar): void {
    this.payingPayable.set(payable);
  }

  closePayModal(): void {
    this.payingPayable.set(null);
  }

  async confirmPay(): Promise<void> {
    const p = this.payingPayable();
    if (!p) return;
    this.isPaying.set(true);
    try {
      await this.payableService.payPayable(p.id, {
        forma_pagamento: this.payMethod(),
        data_pagamento: this.payDate(),
      });
      this.closePayModal();
      this.loadPayables();
    } catch {
      // Error handled
    } finally {
      this.isPaying.set(false);
    }
  }

  async loadPayables(): Promise<void> {
    this.isLoading.set(true);
    this.error.set('');
    try {
      const response = await this.payableService.listPayables({
        search: this.search(),
        status: this.statusFilter(),
        page: this.page(),
        size: this.size(),
      });
      this.payables.set(response.items);
      this.total.set(response.total);
    } catch {
      this.payables.set([]);
      this.total.set(0);
      this.error.set('Erro ao carregar contas a pagar. Verifique sua conexão.');
    } finally {
      this.isLoading.set(false);
    }
  }

  statusLabel(status: string): string {
    const map: Record<string, string> = {
      pendente: 'Pendente',
      pago: 'Pago',
      vencido: 'Vencido',
      cancelado: 'Cancelado',
    };
    return map[status] ?? status;
  }

  statusClass(status: string): string {
    const map: Record<string, string> = {
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
}
