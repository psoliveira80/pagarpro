import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
  OnInit,
  OnDestroy,
} from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import { UiIconComponent } from '../../../shared/components/icon/icon.component';
import { CustomSelectComponent, SelectOption } from '../../../shared/components/custom-select/custom-select.component';
import {
  ContractService,
  Contrato,
} from '../../../core/services/contract.service';
import { SimulacaoModalComponent } from '../simulacao-modal/simulacao-modal.component';

@Component({
  selector: 'app-contratos-lista',
  standalone: true,
  imports: [FormsModule, UiIconComponent, SimulacaoModalComponent, CustomSelectComponent],
  templateUrl: './contratos-lista.component.html',
  styleUrl: './contratos-lista.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ContratosListaComponent implements OnInit, OnDestroy {
  private readonly contractService = inject(ContractService);
  private readonly router = inject(Router);
  private readonly searchSubject = new Subject<string>();
  private searchSub: { unsubscribe(): void } | null = null;

  readonly contracts = signal<Contrato[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly size = signal(10);
  readonly search = signal('');
  readonly statusFilter = signal('todos');
  readonly statusOptions: SelectOption[] = [
    { value: 'todos', label: 'Todos os status' },
    { value: 'rascunho', label: 'Rascunho' },
    { value: 'ativo', label: 'Ativo' },
    { value: 'encerrado', label: 'Encerrado' },
  ];
  readonly isLoading = signal(false);
  readonly error = signal('');
  readonly simulationOpen = signal(false);

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
        this.loadContracts();
      });
    this.loadContracts();
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
    this.loadContracts();
  }

  goToPage(p: number): void {
    if (p < 1 || p > this.totalPages()) return;
    this.page.set(p);
    this.loadContracts();
  }

  navigateToNew(): void {
    this.router.navigate(['/sistema/contratos/novo']);
  }

  viewContract(contract: Contrato): void {
    this.router.navigate(['/sistema/contratos', contract.id]);
  }

  openSimulation(): void {
    this.simulationOpen.set(true);
  }

  closeSimulation(): void {
    this.simulationOpen.set(false);
  }

  async loadContracts(): Promise<void> {
    this.isLoading.set(true);
    this.error.set('');
    try {
      const response = await this.contractService.list({
        search: this.search(),
        status: this.statusFilter(),
        page: this.page(),
        size: this.size(),
      });
      this.contracts.set(response.items);
      this.total.set(response.total);
    } catch {
      this.contracts.set([]);
      this.total.set(0);
      this.error.set('Erro ao carregar contratos. Verifique sua conexão.');
    } finally {
      this.isLoading.set(false);
    }
  }

  statusLabel(status: string): string {
    const map: Record<string, string> = {
      rascunho: 'Rascunho',
      ativo: 'Ativo',
      encerrado: 'Encerrado',
    };
    return map[status] ?? status;
  }

  statusClass(status: string): string {
    const map: Record<string, string> = {
      rascunho: 'bg-yellow-500/20 text-yellow-400',
      ativo: 'bg-green-500/20 text-green-400',
      encerrado: 'bg-gray-500/20 text-gray-400',
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
