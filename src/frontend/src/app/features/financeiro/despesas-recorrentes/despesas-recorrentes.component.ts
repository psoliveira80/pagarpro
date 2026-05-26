import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
  OnInit,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { UiIconComponent } from '../../../shared/components/icon/icon.component';
import { ModalComponent } from '../../../shared/components/modal/modal.component';
import { CustomSelectComponent, SelectOption } from '../../../shared/components/custom-select/custom-select.component';
import {
  PayableService,
  DespesaRecorrente,
  DespesaRecorrenteCreatePayload,
  CategoriaDespesa,
  Fornecedor,
} from '../../../core/services/payable.service';
import { ConfirmService } from '../../../shared/services/confirm.service';

@Component({
  selector: 'app-despesas-recorrentes',
  standalone: true,
  imports: [FormsModule, UiIconComponent, CustomSelectComponent, ModalComponent],
  templateUrl: './despesas-recorrentes.component.html',
  styleUrl: './despesas-recorrentes.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DespesasRecorrentesComponent implements OnInit {
  private readonly payableService = inject(PayableService);
  private readonly confirmService = inject(ConfirmService);

  readonly templates = signal<DespesaRecorrente[]>([]);
  readonly isLoading = signal(false);
  readonly error = signal('');
  readonly formOpen = signal(false);
  readonly editingTemplate = signal<DespesaRecorrente | null>(null);

  // Form fields
  readonly description = signal('');
  readonly supplierId = signal('');
  readonly categoryId = signal('');
  readonly amount = signal(0);
  readonly frequency = signal('mensal');
  readonly dayOfMonth = signal(1);
  readonly isSaving = signal(false);

  readonly categories = signal<CategoriaDespesa[]>([]);
  readonly supplierSearch = signal('');

  readonly frequencyOptions: SelectOption[] = [
    { value: 'mensal', label: 'Mensal' },
    { value: 'semanal', label: 'Semanal' },
    { value: 'quinzenal', label: 'Quinzenal' },
    { value: 'anual', label: 'Anual' },
  ];

  readonly categoryOptions = computed<SelectOption[]>(() =>
    this.categories().map((c) => ({ value: c.id, label: c.nome })),
  );
  readonly supplierResults = signal<Fornecedor[]>([]);

  ngOnInit(): void {
    this.loadTemplates();
    this.loadCategories();
  }

  async loadTemplates(): Promise<void> {
    this.isLoading.set(true);
    this.error.set('');
    try {
      const data = await this.payableService.listRecurring();
      this.templates.set(data);
    } catch {
      this.templates.set([]);
      this.error.set('Erro ao carregar modelos recorrentes. Verifique sua conexão.');
    } finally {
      this.isLoading.set(false);
    }
  }

  async loadCategories(): Promise<void> {
    try {
      const cats = await this.payableService.listCategories();
      this.categories.set(cats);
    } catch {
      this.categories.set([]);
    }
  }

  openCreate(): void {
    this.editingTemplate.set(null);
    this.description.set('');
    this.supplierId.set('');
    this.categoryId.set('');
    this.amount.set(0);
    this.frequency.set('mensal');
    this.dayOfMonth.set(1);
    this.supplierSearch.set('');
    this.formOpen.set(true);
  }

  openEdit(template: DespesaRecorrente): void {
    this.editingTemplate.set(template);
    this.description.set(template.descricao);
    this.supplierId.set(template.fornecedor_id ?? '');
    this.categoryId.set(template.categoria_id ?? '');
    this.amount.set(template.valor);
    this.frequency.set(template.periodicidade);
    this.dayOfMonth.set(template.dia_do_mes ?? 1);
    this.supplierSearch.set('');
    this.formOpen.set(true);
  }

  closeForm(): void {
    this.formOpen.set(false);
  }

  async searchSuppliers(term: string): Promise<void> {
    this.supplierSearch.set(term);
    if (term.length < 2) {
      this.supplierResults.set([]);
      return;
    }
    try {
      const res = await this.payableService.listSuppliers({ search: term, size: 5 });
      this.supplierResults.set(res.items);
    } catch {
      this.supplierResults.set([]);
    }
  }

  selectSupplier(supplier: Fornecedor): void {
    this.supplierId.set(supplier.id);
    this.supplierSearch.set(supplier.nome);
    this.supplierResults.set([]);
  }

  async submit(): Promise<void> {
    this.isSaving.set(true);
    try {
      const editing = this.editingTemplate();
      const payload: DespesaRecorrenteCreatePayload = {
        descricao: this.description(),
        fornecedor_id: this.supplierId() || undefined,
        categoria_id: this.categoryId() || undefined,
        valor: this.amount(),
        periodicidade: this.frequency(),
        dia_do_mes: this.dayOfMonth(),
        proxima_geracao_em: editing?.proxima_geracao_em ?? new Date().toISOString().split('T')[0],
      };
      if (editing) {
        await this.payableService.updateRecurring(editing.id, payload);
      } else {
        await this.payableService.createRecurring(payload);
      }
      this.closeForm();
      this.loadTemplates();
    } catch {
      // Error handled
    } finally {
      this.isSaving.set(false);
    }
  }

  async toggleActive(template: DespesaRecorrente): Promise<void> {
    try {
      await this.payableService.updateRecurring(template.id, { ativo: !template.ativo });
      this.loadTemplates();
    } catch {
      // Error handled
    }
  }

  async deleteTemplate(template: DespesaRecorrente): Promise<void> {
    const ok = await this.confirmService.confirm({ text: 'Tem certeza que deseja excluir este modelo recorrente?', type: 'danger' });
    if (!ok) return;
    try {
      await this.payableService.deleteRecurring(template.id);
      this.loadTemplates();
    } catch {
      // Error handled
    }
  }

  frequencyLabel(freq: string): string {
    const map: Record<string, string> = {
      mensal: 'Mensal',
      semanal: 'Semanal',
      quinzenal: 'Quinzenal',
      anual: 'Anual',
    };
    return map[freq] ?? freq;
  }

  formatCurrency(value: number | null | undefined): string {
    const v = typeof value === 'number' && !isNaN(value) ? value : 0;
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v);
  }

  formatDate(date: string): string {
    return new Date(date).toLocaleDateString('pt-BR');
  }
}
