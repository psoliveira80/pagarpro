import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { UiIconComponent } from '../../../shared/components/icon/icon.component';
import { CustomSelectComponent, SelectOption } from '../../../shared/components/custom-select/custom-select.component';
import { ModalComponent } from '../../../shared/components/modal/modal.component';
import { ToastService } from '../../../shared/components/toast/toast.service';
import { ToastComponent } from '../../../shared/components/toast/toast.component';
import { AdminService, Integration } from '../../../core/services/admin.service';
import { ConfirmService } from '../../../shared/services/confirm.service';

interface ProviderField {
  key: string;
  label: string;
  type: 'text' | 'password' | 'url';
  placeholder: string;
  required: boolean;
}

interface ProviderDef {
  id: string;
  label: string;
  fields: ProviderField[];
  helpText?: string;
}

interface CategoryDef {
  id: string;
  label: string;
  icon: string;
  providers: ProviderDef[];
}

@Component({
  selector: 'app-integracoes',
  standalone: true,
  imports: [UiIconComponent, DatePipe, CustomSelectComponent, ModalComponent, ToastComponent],
  templateUrl: './integracoes.component.html',
  styleUrl: './integracoes.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class IntegracoesComponent implements OnInit {
  private readonly adminService = inject(AdminService);
  private readonly toastService = inject(ToastService);
  private readonly confirmService = inject(ConfirmService);

  readonly integrations = signal<Integration[]>([]);
  readonly isLoading = signal(true);
  readonly showModal = signal(false);
  readonly editingIntegration = signal<Integration | null>(null);
  readonly testingId = signal<string | null>(null);

  readonly formCategory = signal('');
  readonly formProvider = signal('');
  readonly formFields = signal<Record<string, string>>({});

  readonly categories: CategoryDef[] = [
    {
      id: 'whatsapp', label: 'WhatsApp', icon: 'heroChatBubbleLeftRight',
      providers: [
        {
          id: 'zapi', label: 'Z-API',
          helpText: 'Acesse z-api.io para obter suas credenciais',
          fields: [
            { key: 'instance_id', label: 'Instance ID', type: 'text', placeholder: 'Seu Instance ID', required: true },
            { key: 'token', label: 'Token', type: 'password', placeholder: 'Token de acesso', required: true },
            { key: 'client_token', label: 'Client Token', type: 'password', placeholder: 'Client Token (webhook)', required: false },
          ],
        },
        {
          id: 'uazapi', label: 'Uazapi',
          helpText: 'Acesse uazapi.com para obter suas credenciais',
          fields: [
            { key: 'base_url', label: 'URL da API', type: 'url', placeholder: 'https://api.uazapi.com', required: true },
            { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'Sua chave de API', required: true },
            { key: 'instance', label: 'Instância', type: 'text', placeholder: 'Nome da instância', required: true },
          ],
        },
        {
          id: 'evolution_api', label: 'Evolution API',
          helpText: 'Self-hosted. Configure o endereço do seu servidor Evolution API',
          fields: [
            { key: 'base_url', label: 'URL do Servidor', type: 'url', placeholder: 'https://evolution.seuserver.com', required: true },
            { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'Chave de autenticação', required: true },
            { key: 'instance', label: 'Nome da Instância', type: 'text', placeholder: 'default', required: true },
          ],
        },
      ],
    },
    {
      id: 'llm', label: 'Provedor de IA (LLM)', icon: 'heroSparkles',
      providers: [
        { id: 'openai', label: 'OpenAI (GPT)', fields: [
          { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'sk-...', required: true },
          { key: 'model', label: 'Modelo padrão', type: 'text', placeholder: 'gpt-4o-mini', required: false },
        ]},
        { id: 'anthropic', label: 'Anthropic (Claude)', fields: [
          { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'sk-ant-...', required: true },
          { key: 'model', label: 'Modelo padrão', type: 'text', placeholder: 'claude-sonnet-4-20250514', required: false },
        ]},
        { id: 'groq', label: 'Groq (Llama/Mixtral)', fields: [
          { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'gsk_...', required: true },
          { key: 'model', label: 'Modelo padrão', type: 'text', placeholder: 'llama-3.1-70b-versatile', required: false },
        ]},
        { id: 'gemini', label: 'Google Gemini', fields: [
          { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'AIza...', required: true },
          { key: 'model', label: 'Modelo padrão', type: 'text', placeholder: 'gemini-1.5-flash', required: false },
        ]},
        { id: 'ollama', label: 'Ollama (Local)', helpText: 'Rode modelos localmente.', fields: [
          { key: 'base_url', label: 'URL do Ollama', type: 'url', placeholder: 'http://localhost:11434', required: true },
          { key: 'model', label: 'Modelo padrão', type: 'text', placeholder: 'llama3.1', required: false },
        ]},
      ],
    },
    {
      id: 'gps_tracker', label: 'GPS / Rastreador', icon: 'heroMapPin',
      providers: [
        { id: 'generic_rest', label: 'API REST Genérica', helpText: 'Qualquer rastreador com API REST', fields: [
          { key: 'base_url', label: 'URL da API', type: 'url', placeholder: 'https://api.rastreador.com', required: true },
          { key: 'api_key', label: 'API Key / Token', type: 'password', placeholder: 'Token de autenticação', required: true },
        ]},
      ],
    },
    {
      id: 'payment_gateway', label: 'Gateway de Pagamento', icon: 'heroCurrencyDollar',
      providers: [
        { id: 'asaas', label: 'Asaas', fields: [
          { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'Chave de API Asaas', required: true },
        ]},
        { id: 'efi', label: 'Efí (Gerencianet)', fields: [
          { key: 'client_id', label: 'Client ID', type: 'text', placeholder: 'Client ID', required: true },
          { key: 'client_secret', label: 'Client Secret', type: 'password', placeholder: 'Client Secret', required: true },
          { key: 'pix_key', label: 'Chave Pix', type: 'text', placeholder: 'Sua chave Pix', required: true },
        ]},
      ],
    },
    {
      id: 'fipe', label: 'FIPE / Tabela de Preços', icon: 'heroTruck',
      providers: [
        { id: 'brasilapi', label: 'BrasilAPI (gratuita)', helpText: 'API pública, sem autenticação. Já conectada.', fields: [] },
      ],
    },
    {
      id: 'correction_index', label: 'Índice de Correção', icon: 'heroChartBarSquare',
      providers: [
        { id: 'bcb', label: 'Banco Central do Brasil', helpText: 'API pública do BCB (IGPM, IPCA, INPC). Já conectada.', fields: [] },
      ],
    },
  ];

  readonly categoryOptions = computed<SelectOption[]>(() =>
    this.categories.map((c) => ({ value: c.id, label: c.label })),
  );

  readonly selectedCategory = computed(() =>
    this.categories.find((c) => c.id === this.formCategory()) ?? null,
  );

  readonly providerOptions = computed<SelectOption[]>(() =>
    this.selectedCategory()?.providers.map((p) => ({ value: p.id, label: p.label })) ?? [],
  );

  readonly selectedProvider = computed(() =>
    this.selectedCategory()?.providers.find((p) => p.id === this.formProvider()) ?? null,
  );

  // For each category, check if there's a configured integration
  connectedProvider(categoryId: string): Integration | null {
    return this.integrations().find((i) => i.category === categoryId) ?? null;
  }

  async ngOnInit(): Promise<void> {
    await this.load();
  }

  async load(): Promise<void> {
    this.isLoading.set(true);
    try {
      this.integrations.set(await this.adminService.listIntegrations());
    } catch {
      this.toastService.show({ message: 'Erro ao carregar integrações', type: 'error' });
    } finally {
      this.isLoading.set(false);
    }
  }

  openAddModal(categoryId?: string): void {
    this.editingIntegration.set(null);
    this.formCategory.set(categoryId ?? '');
    this.formProvider.set('');
    this.formFields.set({});
    this.showModal.set(true);
  }

  openEditModal(integration: Integration): void {
    this.editingIntegration.set(integration);
    this.formCategory.set(integration.category);
    this.formProvider.set(integration.provider);
    this.formFields.set({ ...(integration.config as Record<string, string>) });
    this.showModal.set(true);
  }

  closeModal(): void {
    this.showModal.set(false);
  }

  onCategoryChange(value: string): void {
    this.formCategory.set(value);
    this.formProvider.set('');
    this.formFields.set({});
  }

  onProviderChange(value: string): void {
    this.formProvider.set(value);
    this.formFields.set({});
  }

  setField(key: string, value: string): void {
    this.formFields.update((f) => ({ ...f, [key]: value }));
  }

  getField(key: string): string {
    return this.formFields()[key] ?? '';
  }

  get canSave(): boolean {
    const provider = this.selectedProvider();
    if (!this.formCategory() || !this.formProvider() || !provider) return false;
    return provider.fields.filter((f) => f.required).every((f) => !!this.getField(f.key));
  }

  async saveIntegration(): Promise<void> {
    if (!this.canSave) return;
    const config = { ...this.formFields() };
    const editing = this.editingIntegration();
    try {
      if (editing) {
        await this.adminService.updateIntegration(editing.id, { provider: this.formProvider(), config });
        this.toastService.show({ message: 'Integração atualizada', type: 'success' });
      } else {
        await this.adminService.createIntegration({ category: this.formCategory(), provider: this.formProvider(), config });
        this.toastService.show({ message: 'Integração criada', type: 'success' });
      }
      this.closeModal();
      await this.load();
    } catch {
      this.toastService.show({ message: 'Erro ao salvar integração', type: 'error' });
    }
  }

  async deleteIntegration(id: string): Promise<void> {
    const ok = await this.confirmService.confirm({ text: 'Tem certeza que deseja remover esta integração?', type: 'danger' });
    if (!ok) return;
    try {
      await this.adminService.deleteIntegration(id);
      this.toastService.show({ message: 'Integração removida', type: 'success' });
      await this.load();
    } catch {
      this.toastService.show({ message: 'Erro ao remover integração', type: 'error' });
    }
  }

  async testConnection(id: string): Promise<void> {
    this.testingId.set(id);
    try {
      const result = await this.adminService.testIntegration(id);
      this.toastService.show({
        message: result.status === 'healthy' ? `Conexão OK (${result.latency_ms}ms)` : `Falha: ${result.error ?? 'Erro'}`,
        type: result.status === 'healthy' ? 'success' : 'error',
      });
      await this.load();
    } catch {
      this.toastService.show({ message: 'Erro ao testar conexão', type: 'error' });
    } finally {
      this.testingId.set(null);
    }
  }

  statusClass(status: string): string {
    return status === 'healthy' ? 'bg-green-500/15 text-green-400' : status === 'error' ? 'bg-red-500/15 text-red-400' : 'bg-yellow-500/15 text-yellow-400';
  }

  statusLabel(status: string): string {
    return status === 'healthy' ? 'Conectado' : status === 'error' ? 'Erro' : 'Não verificado';
  }
}
