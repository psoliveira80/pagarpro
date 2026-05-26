import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
} from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { UiIconComponent } from '../../../shared/components/icon/icon.component';
import { SearchableSelectComponent, SearchableOption } from '../../../shared/components/searchable-select/searchable-select.component';
import {
  ContractService,
  PreviewTitulo,
} from '../../../core/services/contract.service';
import {
  CustomerService,
  Cliente,
} from '../../../core/services/customer.service';
import { VehicleService, Veiculo } from '../../../core/services/vehicle.service';

@Component({
  selector: 'app-contrato-wizard',
  standalone: true,
  imports: [FormsModule, UiIconComponent, SearchableSelectComponent],
  templateUrl: './contrato-wizard.component.html',
  styleUrl: './contrato-wizard.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ContratoWizardComponent {
  private readonly contractService = inject(ContractService);
  private readonly customerService = inject(CustomerService);
  private readonly vehicleService = inject(VehicleService);
  private readonly router = inject(Router);

  readonly currentStep = signal(1);
  readonly isLoading = signal(false);
  readonly isSaving = signal(false);

  // Step 1 - Cliente & Asset
  readonly selectedCustomer = signal<Cliente | null>(null);
  readonly selectedAsset = signal<Veiculo | null>(null);
  readonly customerOptions = signal<SearchableOption[]>([]);
  readonly assetOptions = signal<SearchableOption[]>([]);
  readonly customerSearching = signal(false);
  readonly assetSearching = signal(false);
  private customerMap = new Map<string, Cliente>();
  private assetMap = new Map<string, Veiculo>();

  // Step 2 - Terms
  readonly startDate = signal('');
  readonly endDate = signal('');
  readonly totalValue = signal(0);
  readonly notes = signal('');

  // Step 3 - Schedule
  readonly schedulePreview = signal<PreviewTitulo[]>([]);
  readonly scheduleTotal = signal(0);
  readonly numInstallments = signal(12);

  // Step 4 - Review
  readonly activateAfterCreate = signal(false);

  readonly steps = [
    { number: 1, label: 'Cliente e Ativo' },
    { number: 2, label: 'Condições' },
    { number: 3, label: 'Parcelas' },
    { number: 4, label: 'Revisão' },
  ];

  canAdvance(): boolean {
    switch (this.currentStep()) {
      case 1:
        return this.selectedCustomer() !== null && this.selectedAsset() !== null;
      case 2:
        return !!this.startDate() && !!this.endDate() && this.totalValue() > 0;
      case 3:
        return this.schedulePreview().length > 0;
      default:
        return true;
    }
  }

  nextStep(): void {
    if (this.currentStep() < 4 && this.canAdvance()) {
      if (this.currentStep() === 2) {
        this.loadSchedulePreview();
      }
      this.currentStep.update((s) => s + 1);
    }
  }

  prevStep(): void {
    if (this.currentStep() > 1) {
      this.currentStep.update((s) => s - 1);
    }
  }

  goToStep(step: number): void {
    if (step < this.currentStep()) {
      this.currentStep.set(step);
    }
  }

  async onCustomerSearch(term: string): Promise<void> {
    this.customerSearching.set(true);
    try {
      const response = await this.customerService.list({ search: term, size: 20 });
      this.customerMap.clear();
      const opts: SearchableOption[] = [];
      for (const c of response.items) {
        this.customerMap.set(c.id, c);
        opts.push({ value: c.id, label: c.nome_completo, subtitle: c.cpf_cnpj });
      }
      this.customerOptions.set(opts);
    } catch {
      this.customerOptions.set([]);
    } finally {
      this.customerSearching.set(false);
    }
  }

  onCustomerSelected(id: string): void {
    const c = this.customerMap.get(id) ?? null;
    this.selectedCustomer.set(c);
  }

  clearCustomer(): void {
    this.selectedCustomer.set(null);
    this.customerOptions.set([]);
  }

  async onAssetSearch(term: string): Promise<void> {
    this.assetSearching.set(true);
    try {
      const response = await this.vehicleService.list({ search: term, size: 20 });
      this.assetMap.clear();
      const opts: SearchableOption[] = [];
      for (const v of (response as { items: Veiculo[] }).items) {
        this.assetMap.set(v.id, v);
        opts.push({ value: v.id, label: `${v.placa} — ${v.marca} ${v.modelo}`, subtitle: `Ano ${v.ano_modelo} Â· ${v.cor}` });
      }
      this.assetOptions.set(opts);
    } catch {
      this.assetOptions.set([]);
    } finally {
      this.assetSearching.set(false);
    }
  }

  onAssetSelected(id: string): void {
    const v = this.assetMap.get(id) ?? null;
    this.selectedAsset.set(v);
  }

  clearAsset(): void {
    this.selectedAsset.set(null);
    this.assetOptions.set([]);
  }

  async loadSchedulePreview(): Promise<void> {
    this.isLoading.set(true);
    try {
      const result = await this.contractService.previewSchedule({
        valor_total: this.totalValue(),
        quantidade_parcelas: this.numInstallments(),
        data_inicio: this.startDate(),
      });
      this.schedulePreview.set(result.titulos);
      this.scheduleTotal.set(result.total);
    } catch {
      this.schedulePreview.set([]);
    } finally {
      this.isLoading.set(false);
    }
  }

  async submit(): Promise<void> {
    this.isSaving.set(true);
    try {
      const customer = this.selectedCustomer();
      const asset = this.selectedAsset();
      if (!customer || !asset) return;

      const contract = await this.contractService.create({
        cliente_id: customer.id,
        veiculo_id: asset.id,
        numero: `CT-${Date.now()}`,
        data_inicio: this.startDate(),
        data_fim: this.endDate(),
        valor_total: this.totalValue(),
        observacoes: this.notes(),
        quantidade_parcelas: this.numInstallments(),
      });

      if (this.activateAfterCreate()) {
        await this.contractService.activate(contract.id);
      }

      this.router.navigate(['/sistema/contracts', contract.id]);
    } catch {
      // Error handled by interceptor
    } finally {
      this.isSaving.set(false);
    }
  }

  goBack(): void {
    this.router.navigate(['/sistema/contracts']);
  }

  formatCurrency(value: number | null | undefined): string {
    const v = typeof value === 'number' && !isNaN(value) ? value : 0;
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v);
  }

  formatDate(date: string): string {
    return new Date(date).toLocaleDateString('pt-BR');
  }
}
