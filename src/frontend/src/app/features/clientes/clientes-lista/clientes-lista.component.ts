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
  CustomerService,
  Cliente,
} from '../../../core/services/customer.service';
@Component({
  selector: 'app-clientes-lista',
  standalone: true,
  imports: [FormsModule, UiIconComponent, CustomSelectComponent],
  templateUrl: './clientes-lista.component.html',
  styleUrl: './clientes-lista.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ClientesListaComponent implements OnInit, OnDestroy {
  private readonly customerService = inject(CustomerService);
  private readonly router = inject(Router);
  private readonly searchSubject = new Subject<string>();
  private searchSub: { unsubscribe(): void } | null = null;

  readonly customers = signal<Cliente[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly size = signal(10);
  readonly search = signal('');
  readonly statusFilter = signal('todos');
  readonly statusOptions: SelectOption[] = [
    { value: 'todos', label: 'Todos os status' },
    { value: 'ativo', label: 'Ativo' },
    { value: 'inativo', label: 'Inativo' },
    { value: 'bloqueado', label: 'Bloqueado' },
  ];
  readonly isLoading = signal(false);
  readonly error = signal('');
  // Uses wizard pattern (same as vehicles/contracts) — navigates to /clientes/novo

  readonly totalPages = computed(() => Math.ceil(this.total() / this.size()) || 1);
  readonly pages = computed(() => {
    const tp = this.totalPages();
    const current = this.page();
    const result: number[] = [];
    const start = Math.max(1, current - 2);
    const end = Math.min(tp, current + 2);
    for (let i = start; i <= end; i++) {
      result.push(i);
    }
    return result;
  });

  ngOnInit(): void {
    this.searchSub = this.searchSubject
      .pipe(debounceTime(300), distinctUntilChanged())
      .subscribe((term) => {
        this.search.set(term);
        this.page.set(1);
        this.loadCustomers();
      });
    this.loadCustomers();
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
    this.loadCustomers();
  }

  goToPage(p: number): void {
    if (p < 1 || p > this.totalPages()) return;
    this.page.set(p);
    this.loadCustomers();
  }

  openCreateWizard(): void {
    this.router.navigate(['/sistema/clientes/novo']);
  }

  openEditWizard(customer: Cliente): void {
    this.router.navigate(['/sistema/clientes', customer.id, 'edit']);
  }

  viewCustomer(customer: Cliente): void {
    this.router.navigate(['/sistema/clientes', customer.id]);
  }

  async loadCustomers(): Promise<void> {
    this.isLoading.set(true);
    this.error.set('');
    try {
      const response = await this.customerService.list({
        search: this.search(),
        status: this.statusFilter() === 'todos' ? undefined : this.statusFilter(),
        page: this.page(),
        size: this.size(),
      });
      this.customers.set(response.items);
      this.total.set(response.total);
    } catch {
      this.customers.set([]);
      this.total.set(0);
      this.error.set('Erro ao carregar clientes. Verifique sua conexão.');
    } finally {
      this.isLoading.set(false);
    }
  }

  formatDocument(customer: Cliente): string {
    const doc = (customer.cpf_cnpj ?? '').replace(/\D/g, '');
    if (doc.length === 11) {
      return `${doc.slice(0, 3)}.${doc.slice(3, 6)}.${doc.slice(6, 9)}-${doc.slice(9)}`;
    }
    if (doc.length === 14) {
      return `${doc.slice(0, 2)}.${doc.slice(2, 5)}.${doc.slice(5, 8)}/${doc.slice(8, 12)}-${doc.slice(12)}`;
    }
    return doc;
  }

  statusLabel(status: string): string {
    const map: Record<string, string> = {
      ativo: 'Ativo',
      inativo: 'Inativo',
      bloqueado: 'Bloqueado',
    };
    return map[status] ?? status;
  }

  statusClass(status: string): string {
    const map: Record<string, string> = {
      ativo: 'bg-green-500/20 text-green-400',
      inativo: 'bg-yellow-500/20 text-yellow-400',
      bloqueado: 'bg-red-500/20 text-red-400',
    };
    return map[status] ?? 'bg-gray-500/20 text-gray-400';
  }

  scoreClass(score: number): string {
    if (score >= 80) return 'text-green-400';
    if (score >= 50) return 'text-yellow-400';
    return 'text-red-400';
  }
}
