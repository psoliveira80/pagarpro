import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
} from '@angular/core';
import { CustomSelectComponent, SelectOption } from '../../../shared/components/custom-select/custom-select.component';
import { InputMoedaComponent } from '../../../shared/components/input-moeda/input-moeda.component';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { UiIconComponent } from '../../../shared/components/icon/icon.component';
import {
  VehicleService,
  FipeMarca,
  FipeModelo,
  FipeAno,
  VeiculoCreatePayload,
} from '../../../core/services/vehicle.service';
import {
  CustomerService,
  Cliente,
} from '../../../core/services/customer.service';

@Component({
  selector: 'app-veiculo-wizard',
  standalone: true,
  imports: [FormsModule, UiIconComponent, CustomSelectComponent, InputMoedaComponent],
  templateUrl: './veiculo-wizard.component.html',
  styleUrl: './veiculo-wizard.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VeiculoWizardComponent {
  private readonly vehicleService = inject(VehicleService);
  private readonly customerService = inject(CustomerService);
  private readonly router = inject(Router);

  readonly currentStep = signal(1);
  readonly totalSteps = 4;
  readonly isSaving = signal(false);
  readonly errorMessage = signal('');

  // Step 1 - Veiculo identification
  readonly placa = signal('');
  readonly color = signal('');
  readonly chassi = signal('');
  readonly renavam = signal('');

  // Step 2 - FIPE data
  readonly brands = signal<FipeMarca[]>([]);
  readonly models = signal<FipeModelo[]>([]);
  readonly years = signal<FipeAno[]>([]);
  readonly selectedBrandCode = signal('');
  readonly selectedBrandName = signal('');
  readonly selectedModelCode = signal('');
  readonly selectedModelName = signal('');
  readonly selectedYearCode = signal('');
  readonly selectedYearName = signal('');
  readonly fipeCode = signal('');
  readonly fipeValue = signal(0);
  readonly loadingBrands = signal(false);
  readonly fipeError = signal('');
  readonly loadingModels = signal(false);
  readonly loadingYears = signal(false);
  readonly loadingPrice = signal(false);

  // Step 3 - Cliente & acquisition
  readonly customerSearch = signal('');
  readonly customerResults = signal<Cliente[]>([]);
  readonly selectedCustomer = signal<Cliente | null>(null);
  readonly acquisitionType = signal('compra');
  readonly acquisitionPrice = signal(0);
  readonly acquisitionDate = signal('');
  readonly searchingCustomers = signal(false);

  readonly acquisitionTypeOptions: SelectOption[] = [
    { value: 'compra', label: 'Compra' },
    { value: 'financiamento', label: 'Financiamento' },
    { value: 'leasing', label: 'Leasing' },
    { value: 'consorcio', label: 'Consórcio' },
  ];

  readonly brandOptions = computed<SelectOption[]>(() =>
    this.brands().map((b) => ({ value: b.codigo, label: b.nome })),
  );

  readonly modelOptions = computed<SelectOption[]>(() =>
    this.models().map((m) => ({ value: m.codigo, label: m.nome })),
  );

  readonly yearOptions = computed<SelectOption[]>(() =>
    this.years().map((y) => ({ value: y.codigo, label: y.nome })),
  );

  // Step validation — Step 1 is now FIPE, Step 2 is identification
  readonly step1Valid = computed(() => {
    return (
      this.selectedBrandCode().length > 0 &&
      this.selectedModelCode().length > 0 &&
      this.selectedYearCode().length > 0 &&
      this.fipeCode().length > 0
    );
  });

  readonly step2Valid = computed(() => {
    const plateRegex = /^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$/;
    return (
      plateRegex.test(this.placa().toUpperCase()) &&
      this.color().trim().length > 0
    );
  });

  readonly step3Valid = computed(() => {
    return (
      this.selectedCustomer() !== null &&
      this.acquisitionType().length > 0 &&
      this.acquisitionPrice() > 0 &&
      this.acquisitionDate().length > 0
    );
  });

  readonly canProceed = computed(() => {
    const step = this.currentStep();
    if (step === 1) return this.step1Valid();
    if (step === 2) return this.step2Valid();
    if (step === 3) return this.step3Valid();
    return true;
  });

  readonly steps = [
    { number: 1, label: 'Tabela FIPE' },
    { number: 2, label: 'Identificação' },
    { number: 3, label: 'Cliente e Aquisição' },
    { number: 4, label: 'Revisão' },
  ];

  // Track if user attempted to proceed (to show validation errors)
  readonly stepAttempted = signal(false);

  constructor() {
    this.loadBrands();
  }

  formatPlate(value: string): void {
    const clean = value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 7);
    this.placa.set(clean);
  }

  formatChassi(value: string): void {
    const clean = value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 17);
    this.chassi.set(clean);
  }

  formatRenavam(value: string): void {
    const clean = value.replace(/\D/g, '').slice(0, 11);
    this.renavam.set(clean);
  }

  nextStep(): void {
    if (this.currentStep() >= this.totalSteps) return;
    this.stepAttempted.set(true);
    if (!this.canProceed()) return; // show errors but don't block button
    this.stepAttempted.set(false);
    this.currentStep.update((s) => s + 1);
  }

  prevStep(): void {
    if (this.currentStep() > 1) {
      this.currentStep.update((s) => s - 1);
    }
  }

  goToStep(step: number): void {
    if (step <= this.currentStep()) {
      this.currentStep.set(step);
    }
  }

  async loadBrands(): Promise<void> {
    this.loadingBrands.set(true);
    this.fipeError.set('');
    try {
      const data = await this.vehicleService.getFipeBrands();
      this.brands.set(data);
      if (data.length === 0) {
        this.fipeError.set('Nenhuma marca encontrada. Verifique se a integração FIPE está configurada em Configurações > Integrações.');
      }
    } catch {
      this.brands.set([]);
      this.fipeError.set('Não foi possível carregar a tabela FIPE. Verifique se a integração está configurada em Configurações > Integrações.');
    } finally {
      this.loadingBrands.set(false);
    }
  }

  async onBrandChange(code: string): Promise<void> {
    this.selectedBrandCode.set(code);
    const brand = this.brands().find((b) => b.codigo === code);
    this.selectedBrandName.set(brand?.nome ?? '');
    this.selectedModelCode.set('');
    this.selectedModelName.set('');
    this.selectedYearCode.set('');
    this.selectedYearName.set('');
    this.years.set([]);
    this.fipeCode.set('');
    this.fipeValue.set(0);

    if (!code) {
      this.models.set([]);
      return;
    }

    this.loadingModels.set(true);
    try {
      const data = await this.vehicleService.getFipeModels(code);
      this.models.set(data);
    } catch {
      this.models.set([]);
    } finally {
      this.loadingModels.set(false);
    }
  }

  async onModelChange(code: string): Promise<void> {
    this.selectedModelCode.set(code);
    const model = this.models().find((m) => m.codigo === code);
    this.selectedModelName.set(model?.nome ?? '');
    this.selectedYearCode.set('');
    this.selectedYearName.set('');
    this.fipeCode.set('');
    this.fipeValue.set(0);

    if (!code) {
      this.years.set([]);
      return;
    }

    this.loadingYears.set(true);
    try {
      const data = await this.vehicleService.getFipeYears(this.selectedBrandCode(), code);
      this.years.set(data);
    } catch {
      this.years.set([]);
    } finally {
      this.loadingYears.set(false);
    }
  }

  async onYearChange(code: string): Promise<void> {
    this.selectedYearCode.set(code);
    const year = this.years().find((y) => y.codigo === code);
    this.selectedYearName.set(year?.nome ?? '');
    this.fipeCode.set('');
    this.fipeValue.set(0);

    if (!code) return;

    this.loadingPrice.set(true);
    try {
      const data = await this.vehicleService.getFipePrice(
        this.selectedBrandCode(),
        this.selectedModelCode(),
        code,
      );
      this.fipeCode.set(data.codigo_fipe);
      this.fipeValue.set(parseFloat(data.preco.replace(/[^\d,]/g, '').replace(',', '.')) || 0);
    } catch {
      this.fipeCode.set('');
      this.fipeValue.set(0);
    } finally {
      this.loadingPrice.set(false);
    }
  }

  async searchCustomers(term: string): Promise<void> {
    this.customerSearch.set(term);
    if (term.trim().length < 2) {
      this.customerResults.set([]);
      return;
    }

    this.searchingCustomers.set(true);
    try {
      const response = await this.customerService.list({
        search: term,
        page: 1,
        size: 10,
      });
      this.customerResults.set(response.items);
    } catch {
      this.customerResults.set([]);
    } finally {
      this.searchingCustomers.set(false);
    }
  }

  selectCustomer(customer: Cliente): void {
    this.selectedCustomer.set(customer);
    this.customerSearch.set(customer.nome_completo);
    this.customerResults.set([]);
  }

  clearCustomer(): void {
    this.selectedCustomer.set(null);
    this.customerSearch.set('');
    this.customerResults.set([]);
  }

  formatCurrency(value: number | null | undefined): string {
    const v = typeof value === 'number' && !isNaN(value) ? value : 0;
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v);
  }

  displayPlate(): string {
    const p = this.placa();
    if (p.length === 7) {
      return `${p.slice(0, 3)}-${p.slice(3)}`;
    }
    return p;
  }

  async confirm(): Promise<void> {
    this.isSaving.set(true);
    this.errorMessage.set('');

    const customer = this.selectedCustomer();
    if (!customer) return;

    const yearStr = this.selectedYearName();
    const parsedYear = parseInt(yearStr, 10) || new Date().getFullYear();

    const payload: VeiculoCreatePayload = {
      placa: this.placa().toUpperCase(),
      cor: this.color(),
      chassi: this.chassi().toUpperCase(),
      renavam: this.renavam(),
      marca: this.selectedBrandName(),
      modelo: this.selectedModelName(),
      ano_modelo: parsedYear,
      ano_fabricacao: parsedYear,
      codigo_fipe: this.fipeCode(),
      valor_fipe: this.fipeValue(),
      cliente_id: customer.id,
    };

    try {
      await this.vehicleService.create(payload);
      await this.router.navigate(['/sistema/veiculos']);
    } catch {
      this.errorMessage.set('Erro ao cadastrar veículo. Verifique os dados e tente novamente.');
    } finally {
      this.isSaving.set(false);
    }
  }

  cancel(): void {
    this.router.navigate(['/sistema/veiculos']);
  }
}
