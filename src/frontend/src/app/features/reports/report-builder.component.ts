import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
} from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { UiIconComponent } from '../../shared/components/icon/icon.component';
import { ModalComponent } from '../../shared/components/modal/modal.component';
import { ToastService } from '../../shared/components/toast/toast.service';
import {
  ReportService,
  ReportColumn,
  ReportRow,
} from '../../core/services/report.service';

interface DimensionOption {
  key: string;
  label: string;
}

interface MeasureOption {
  key: string;
  label: string;
  selected: boolean;
}

@Component({
  selector: 'app-report-builder',
  standalone: true,
  imports: [UiIconComponent, FormsModule, ModalComponent],
  templateUrl: './report-builder.component.html',
  styleUrl: './report-builder.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ReportBuilderComponent {
  private readonly router = inject(Router);
  private readonly reportService = inject(ReportService);
  private readonly toastService = inject(ToastService);

  readonly availableDimensions: DimensionOption[] = [
    { key: 'customer_name', label: 'Cliente' },
    { key: 'contract_number', label: 'Contrato' },
    { key: 'contract_status', label: 'Status Contrato' },
    { key: 'due_month', label: 'Mês Vencimento' },
    { key: 'asset_name', label: 'Ativo' },
    { key: 'installment_status', label: 'Status Parcela' },
  ];

  readonly measures = signal<MeasureOption[]>([
    { key: 'count', label: 'Contagem', selected: true },
    { key: 'sum_value', label: 'Soma Valor', selected: false },
    { key: 'sum_paid', label: 'Soma Pago', selected: false },
    { key: 'avg_value', label: 'Média Valor', selected: false },
  ]);

  readonly selectedDimensions = signal<string[]>([]);
  readonly columns = signal<ReportColumn[]>([]);
  readonly rows = signal<ReportRow[]>([]);
  readonly isLoading = signal(false);
  readonly isSaving = signal(false);
  readonly showSaveDialog = signal(false);
  readonly saveName = signal('');
  readonly saveShared = signal(false);

  // Filters
  readonly dateFrom = signal('');
  readonly dateTo = signal('');

  toggleDimension(key: string): void {
    const current = this.selectedDimensions();
    if (current.includes(key)) {
      this.selectedDimensions.set(current.filter((d) => d !== key));
    } else if (current.length < 3) {
      this.selectedDimensions.set([...current, key]);
    }
  }

  toggleMeasure(key: string): void {
    this.measures.update((list) =>
      list.map((m) => (m.key === key ? { ...m, selected: !m.selected } : m)),
    );
  }

  isDimensionSelected(key: string): boolean {
    return this.selectedDimensions().includes(key);
  }

  async runPreview(): Promise<void> {
    const dims = this.selectedDimensions();
    const meas = this.measures()
      .filter((m) => m.selected)
      .map((m) => m.key);

    if (dims.length === 0 && meas.length === 0) return;

    this.isLoading.set(true);
    try {
      const filters: Record<string, string> = {};
      if (this.dateFrom()) filters['date_from'] = this.dateFrom();
      if (this.dateTo()) filters['date_to'] = this.dateTo();

      const data = await this.reportService.runCustomReport({
        dimensions: dims,
        measures: meas,
        filters: Object.keys(filters).length > 0 ? filters : undefined,
        limit: 100,
      });
      this.columns.set(data.columns);
      this.rows.set(data.rows);
    } catch {
      this.toastService.show({
        message: 'Erro ao gerar relatório',
        type: 'error',
      });
    } finally {
      this.isLoading.set(false);
    }
  }

  openSaveDialog(): void {
    this.showSaveDialog.set(true);
  }

  closeSaveDialog(): void {
    this.showSaveDialog.set(false);
  }

  async saveReport(): Promise<void> {
    if (!this.saveName()) return;

    this.isSaving.set(true);
    try {
      await this.reportService.saveReport({
        name: this.saveName(),
        is_shared: this.saveShared(),
        definition: {
          dimensions: this.selectedDimensions(),
          measures: this.measures()
            .filter((m) => m.selected)
            .map((m) => m.key),
          filters: {
            date_from: this.dateFrom(),
            date_to: this.dateTo(),
          },
        },
      });
      this.toastService.show({
        message: 'Relatório salvo com sucesso',
        type: 'success',
      });
      this.closeSaveDialog();
    } catch {
      this.toastService.show({
        message: 'Erro ao salvar relatório',
        type: 'error',
      });
    } finally {
      this.isSaving.set(false);
    }
  }

  goBack(): void {
    this.router.navigate(['/system/reports']);
  }

  formatCell(value: string, format: string): string {
    if (!value || value === 'None') return '-';
    if (format === 'currency') {
      const num = parseFloat(value);
      if (isNaN(num)) return value;
      return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL',
      }).format(num);
    }
    return value;
  }
}
