import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
  input,
  output,
  OnInit,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CustomSelectComponent, SelectOption } from '../../../shared/components/custom-select/custom-select.component';
import { InputMoedaComponent } from '../../../shared/components/input-moeda/input-moeda.component';
import {
  PayableService,
  TituloPagar,
  TituloPagarCreatePayload,
  CategoriaDespesa,
  Fornecedor,
} from '../../../core/services/payable.service';

@Component({
  selector: 'app-titulo-pagar-form',
  standalone: true,
  imports: [FormsModule, CustomSelectComponent, InputMoedaComponent],
  templateUrl: './titulo-pagar-form.component.html',
  styleUrl: './titulo-pagar-form.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TituloPagarFormComponent implements OnInit {
  private readonly payableService = inject(PayableService);

  readonly payable = input<TituloPagar | null>(null);
  readonly saved = output<void>();
  readonly closed = output<void>();

  readonly description = signal('');
  readonly supplierId = signal('');
  readonly categoryId = signal('');
  readonly amount = signal(0);
  readonly dueDate = signal('');
  readonly notes = signal('');
  readonly isSaving = signal(false);

  readonly categories = signal<CategoriaDespesa[]>([]);
  readonly suppliers = signal<Fornecedor[]>([]);
  readonly supplierSearch = signal('');
  readonly supplierResults = signal<Fornecedor[]>([]);
  readonly selectedSupplier = signal<Fornecedor | null>(null);

  readonly categoryOptions = computed<SelectOption[]>(() =>
    this.categories().map((c) => ({ value: c.id, label: c.nome })),
  );

  ngOnInit(): void {
    this.loadCategories();
    this.loadSuppliers();
    const p = this.payable();
    if (p) {
      this.description.set(p.descricao);
      this.supplierId.set(p.fornecedor_id ?? '');
      this.categoryId.set(p.categoria_id ?? '');
      this.amount.set(p.valor);
      this.dueDate.set(p.data_vencimento);
      this.notes.set(p.observacoes ?? '');
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

  async loadSuppliers(): Promise<void> {
    try {
      const res = await this.payableService.listSuppliers({ size: 100 });
      this.suppliers.set(res.items);
    } catch {
      this.suppliers.set([]);
    }
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
    this.selectedSupplier.set(supplier);
    this.supplierId.set(supplier.id);
    this.supplierSearch.set(supplier.nome);
    this.supplierResults.set([]);
  }

  async submit(): Promise<void> {
    this.isSaving.set(true);
    try {
      const payload: TituloPagarCreatePayload = {
        descricao: this.description(),
        fornecedor_id: this.supplierId() || undefined,
        categoria_id: this.categoryId() || undefined,
        valor: this.amount(),
        data_vencimento: this.dueDate(),
        observacoes: this.notes() || undefined,
      };
      const p = this.payable();
      if (p) {
        await this.payableService.updatePayable(p.id, payload);
      } else {
        await this.payableService.createPayable(payload);
      }
      this.saved.emit();
    } catch {
      // Error handled by interceptor
    } finally {
      this.isSaving.set(false);
    }
  }

  close(): void {
    this.closed.emit();
  }

  isEditing(): boolean {
    return this.payable() !== null;
  }
}
