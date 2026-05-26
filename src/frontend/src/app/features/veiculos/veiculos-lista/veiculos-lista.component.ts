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
  VehicleService,
  Veiculo,
} from '../../../core/services/vehicle.service';

@Component({
  selector: 'app-veiculos-lista',
  standalone: true,
  imports: [FormsModule, UiIconComponent, CustomSelectComponent],
  templateUrl: './veiculos-lista.component.html',
  styleUrl: './veiculos-lista.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VeiculosListaComponent implements OnInit, OnDestroy {
  private readonly vehicleService = inject(VehicleService);
  private readonly router = inject(Router);
  private readonly searchSubject = new Subject<string>();
  private searchSub: { unsubscribe(): void } | null = null;

  readonly vehicles = signal<Veiculo[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly size = signal(12);
  readonly search = signal('');
  readonly statusFilter = signal('todos');
  readonly statusOptions: SelectOption[] = [
    { value: 'todos', label: 'Todos os status' },
    { value: 'ativo', label: 'Ativo' },
    { value: 'manutencao', label: 'Manutenção' },
    { value: 'bloqueado', label: 'Bloqueado' },
    { value: 'inativo', label: 'Inativo' },
  ];
  readonly isLoading = signal(false);
  readonly error = signal('');
  readonly viewMode = signal<'table' | 'cards'>('table');

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

  // KPIs
  readonly kpiTotal = computed(() => this.total());
  readonly kpiActive = computed(() => this.vehicles().filter((v) => v.status === 'ativo').length);
  readonly kpiMaintenance = computed(
    () => this.vehicles().filter((v) => v.status === 'manutencao').length,
  );

  ngOnInit(): void {
    this.searchSub = this.searchSubject
      .pipe(debounceTime(300), distinctUntilChanged())
      .subscribe((term) => {
        this.search.set(term);
        this.page.set(1);
        this.loadVehicles();
      });
    this.loadVehicles();
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
    this.loadVehicles();
  }

  goToPage(p: number): void {
    if (p < 1 || p > this.totalPages()) return;
    this.page.set(p);
    this.loadVehicles();
  }

  toggleView(): void {
    this.viewMode.update((v) => (v === 'table' ? 'cards' : 'table'));
  }

  navigateToWizard(): void {
    this.router.navigate(['/sistema/veiculos/novo']);
  }

  async loadVehicles(): Promise<void> {
    this.isLoading.set(true);
    this.error.set('');
    try {
      const response = await this.vehicleService.list({
        search: this.search(),
        status: this.statusFilter(),
        page: this.page(),
        size: this.size(),
      });
      this.vehicles.set(response.items);
      this.total.set(response.total);
    } catch {
      this.vehicles.set([]);
      this.total.set(0);
      this.error.set('Erro ao carregar veículos. Verifique sua conexão.');
    } finally {
      this.isLoading.set(false);
    }
  }

  formatPlate(plate: string): string {
    if (plate.length === 7) {
      return `${plate.slice(0, 3)}-${plate.slice(3)}`;
    }
    return plate;
  }

  formatCurrency(value: number | null | undefined): string {
    const v = typeof value === 'number' && !isNaN(value) ? value : 0;
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v);
  }

  statusLabel(status: string): string {
    const map: Record<string, string> = {
      ativo: 'Ativo',
      manutencao: 'Manutenção',
      bloqueado: 'Bloqueado',
      inativo: 'Inativo',
    };
    return map[status] ?? status;
  }

  statusClass(status: string): string {
    const map: Record<string, string> = {
      ativo: 'bg-green-500/20 text-green-400',
      manutencao: 'bg-yellow-500/20 text-yellow-400',
      bloqueado: 'bg-red-500/20 text-red-400',
      inativo: 'bg-gray-500/20 text-gray-400',
    };
    return map[status] ?? 'bg-gray-500/20 text-gray-400';
  }

  statusDotClass(status: string): string {
    const map: Record<string, string> = {
      ativo: 'bg-green-400',
      manutencao: 'bg-yellow-400',
      bloqueado: 'bg-red-400',
      inativo: 'bg-gray-400',
    };
    return map[status] ?? 'bg-gray-400';
  }
}
