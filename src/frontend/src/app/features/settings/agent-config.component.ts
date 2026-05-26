import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  OnInit,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { UiIconComponent } from '../../shared/components/icon/icon.component';
import { CustomSelectComponent, SelectOption } from '../../shared/components/custom-select/custom-select.component';
import {
  AgentService,
  AgentTool,
} from '../../core/services/agent.service';

@Component({
  selector: 'app-agent-config',
  standalone: true,
  imports: [UiIconComponent, FormsModule, CustomSelectComponent],
  templateUrl: './agent-config.component.html',
  styleUrl: './agent-config.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AgentConfigComponent implements OnInit {
  private readonly agentService = inject(AgentService);

  readonly isLoading = signal(true);
  readonly isSaving = signal(false);
  readonly isTesting = signal(false);
  readonly testResult = signal<string | null>(null);
  readonly configId = signal<string | null>(null);

  // Form fields
  readonly llmProvider = signal('openai');
  readonly llmModel = signal('gpt-4o');
  readonly whatsappProvider = signal('z-api');
  readonly systemPrompt = signal('');
  readonly rateLimitRpm = signal(60);
  readonly monthlyBudget = signal(100);
  readonly temperature = signal(0.7);
  readonly tools = signal<(AgentTool & { enabled: boolean })[]>([]);

  readonly llmProviderOptions: SelectOption[] = [
    { value: 'openai', label: 'OpenAI' },
    { value: 'anthropic', label: 'Anthropic' },
    { value: 'groq', label: 'Groq' },
    { value: 'gemini', label: 'Google Gemini' },
    { value: 'ollama', label: 'Ollama (Local)' },
  ];

  readonly whatsappProviderOptions: SelectOption[] = [
    { value: 'z-api', label: 'Z-API' },
    { value: 'uazapi', label: 'Uazapi' },
    { value: 'evolution-api', label: 'Evolution API' },
  ];

  ngOnInit(): void {
    this.loadConfig();
  }

  async loadConfig(): Promise<void> {
    this.isLoading.set(true);
    try {
      const [configs, availableTools] = await Promise.all([
        this.agentService.getConfigs(),
        this.agentService.listTools(),
      ]);

      if (configs.length > 0) {
        const config = configs[0];
        this.configId.set(config.id);
        this.llmProvider.set(config.llm_provider);
        this.llmModel.set(config.llm_model);
        this.whatsappProvider.set(config.whatsapp_provider);
        this.systemPrompt.set(config.system_prompt);
        this.rateLimitRpm.set(config.rate_limit_rpm);
        this.monthlyBudget.set(config.monthly_budget);
        this.temperature.set(config.temperature);

        // Merge config tools with available tools
        const configToolMap = new Map(config.tools.map((t) => [t.id, t.enabled]));
        this.tools.set(
          availableTools.map((t) => ({
            ...t,
            enabled: configToolMap.get(t.id) ?? t.enabled,
          })),
        );
      } else {
        this.tools.set(availableTools.map((t) => ({ ...t, enabled: true })));
      }
    } catch {
      // Use defaults
      this.tools.set([]);
    } finally {
      this.isLoading.set(false);
    }
  }

  toggleTool(toolId: string): void {
    this.tools.update((list) =>
      list.map((t) => (t.id === toolId ? { ...t, enabled: !t.enabled } : t)),
    );
  }

  async save(): Promise<void> {
    this.isSaving.set(true);
    try {
      const payload = {
        llm_provider: this.llmProvider(),
        llm_model: this.llmModel(),
        whatsapp_provider: this.whatsappProvider(),
        system_prompt: this.systemPrompt(),
        tools: this.tools().map((t) => ({ id: t.id, enabled: t.enabled })),
        rate_limit_rpm: this.rateLimitRpm(),
        monthly_budget: this.monthlyBudget(),
        temperature: this.temperature(),
      };

      const id = this.configId();
      if (id) {
        await this.agentService.updateConfig(id, payload);
      } else {
        const config = await this.agentService.createConfig(payload);
        this.configId.set(config.id);
      }
    } catch {
      // Handle error
    } finally {
      this.isSaving.set(false);
    }
  }

  async testMessage(): Promise<void> {
    this.isTesting.set(true);
    this.testResult.set(null);
    try {
      let result = '';
      this.agentService.chat({ message: 'Olá, teste de conexão' }).subscribe({
        next: (chunk) => {
          if (chunk.type === 'token' && chunk.content) {
            result += chunk.content;
            this.testResult.set(result);
          } else if (chunk.type === 'error') {
            this.testResult.set(`Erro: ${chunk.error}`);
          }
        },
        complete: () => {
          this.isTesting.set(false);
          if (!result) {
            this.testResult.set('Resposta vazia — verifique a configuração');
          }
        },
      });
    } catch {
      this.testResult.set('Erro ao conectar com o agente');
      this.isTesting.set(false);
    }
  }
}
