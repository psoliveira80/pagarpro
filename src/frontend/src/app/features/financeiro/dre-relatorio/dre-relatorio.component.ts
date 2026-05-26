import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { UiIconComponent } from '../../../shared/components/icon/icon.component';
import {
  PayableService,
  DreResponse,
} from '../../../core/services/payable.service';

@Component({
  selector: 'app-dre-relatorio',
  standalone: true,
  imports: [FormsModule, UiIconComponent],
  templateUrl: './dre-relatorio.component.html',
  styleUrl: './dre-relatorio.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DreRelatorioComponent {
  private readonly payableService = inject(PayableService);

  readonly periodStart = signal(
    new Date(new Date().getFullYear(), new Date().getMonth(), 1)
      .toISOString()
      .split('T')[0],
  );
  readonly periodEnd = signal(new Date().toISOString().split('T')[0]);
  readonly isLoading = signal(false);
  readonly error = signal('');
  readonly report = signal<DreResponse | null>(null);

  async loadReport(): Promise<void> {
    this.isLoading.set(true);
    this.error.set('');
    try {
      const data = await this.payableService.getDreReport({
        period_start: this.periodStart(),
        period_end: this.periodEnd(),
      });
      this.report.set(data);
    } catch {
      this.report.set(null);
      this.error.set('Erro ao gerar relatório DRE. Verifique sua conexão.');
    } finally {
      this.isLoading.set(false);
    }
  }

  exportCsv(): void {
    const r = this.report();
    if (!r) return;

    const lines: string[] = ['Categoria,Valor'];
    lines.push('--- RECEITAS ---,');
    for (const item of r.receitas.por_categoria) {
      lines.push(`${item.categoria_nome ?? 'Sem categoria'},${item.total.toFixed(2)}`);
    }
    lines.push(`Total Receitas,${r.receitas.total.toFixed(2)}`);
    lines.push('');
    lines.push('--- DESPESAS ---,');
    for (const item of r.despesas.por_categoria) {
      lines.push(`${item.categoria_nome ?? 'Sem categoria'},${item.total.toFixed(2)}`);
    }
    lines.push(`Total Despesas,${r.despesas.total.toFixed(2)}`);
    lines.push('');
    lines.push(`Resultado Líquido,${r.resultado_liquido.toFixed(2)}`);

    const blob = new Blob([lines.join('\n')], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `dre-${this.periodStart()}-${this.periodEnd()}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  }

  formatCurrency(value: number | null | undefined): string {
    const v = typeof value === 'number' && !isNaN(value) ? value : 0;
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v);
  }

  netResultClass(): string {
    const r = this.report();
    if (!r) return '';
    return r.resultado_liquido >= 0 ? 'text-green-400' : 'text-red-400';
  }

  barWidth(amount: number, total: number): string {
    if (total === 0) return '0%';
    return `${Math.round((amount / total) * 100)}%`;
  }
}
