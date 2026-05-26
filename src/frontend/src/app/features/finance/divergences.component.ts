import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
  OnInit,
} from '@angular/core';
import { UiIconComponent } from '../../shared/components/icon/icon.component';
import {
  BankService,
  DivergenciasResponse,
  DivergenciaItem,
} from '../../core/services/bank.service';

@Component({
  selector: 'app-divergences',
  standalone: true,
  imports: [UiIconComponent],
  templateUrl: './divergences.component.html',
  styleUrl: './divergences.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DivergencesComponent implements OnInit {
  private readonly bankService = inject(BankService);

  readonly divergences = signal<DivergenciasResponse | null>(null);
  readonly isLoading = signal(false);
  readonly error = signal('');
  readonly activeTab = signal<'orphan' | 'suspect' | 'mismatch'>('orphan');
  readonly selectedItem = signal<DivergenciaItem | null>(null);

  readonly currentItems = computed(() => {
    const d = this.divergences();
    if (!d) return [];
    switch (this.activeTab()) {
      case 'orphan':
        return d.transacoes_orfas;
      case 'suspect':
        return d.titulos_suspeitos_pagos;
      case 'mismatch':
        return d.divergencias_valor;
      default:
        return [];
    }
  });

  async ngOnInit(): Promise<void> {
    await this.loadDivergences();
  }

  async loadDivergences(): Promise<void> {
    this.isLoading.set(true);
    this.error.set('');
    try {
      const data = await this.bankService.getDivergences();
      this.divergences.set(data);
    } catch {
      this.error.set('Erro ao carregar divergências');
    } finally {
      this.isLoading.set(false);
    }
  }

  setTab(tab: 'orphan' | 'suspect' | 'mismatch'): void {
    this.activeTab.set(tab);
    this.selectedItem.set(null);
  }

  selectItem(item: DivergenciaItem): void {
    this.selectedItem.set(item);
  }

  closeDetail(): void {
    this.selectedItem.set(null);
  }

  async ignoreItem(item: DivergenciaItem): Promise<void> {
    if (item.tipo_entidade === 'bank_transaction') {
      try {
        await this.bankService.ignoreTransaction(item.entidade_id);
        await this.loadDivergences();
        this.selectedItem.set(null);
      } catch {
        this.error.set('Erro ao ignorar item');
      }
    }
  }
}
