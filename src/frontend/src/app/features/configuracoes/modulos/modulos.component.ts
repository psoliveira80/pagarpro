import { Component, ChangeDetectionStrategy, inject, signal, OnInit } from '@angular/core';
import { DatePipe, JsonPipe } from '@angular/common';
import { UiIconComponent } from '../../../shared/components/icon/icon.component';
import { ToastService } from '../../../shared/components/toast/toast.service';
import { AdminService, AppModule, ModuleHook } from '../../../core/services/admin.service';

@Component({
  selector: 'app-modulos',
  standalone: true,
  imports: [UiIconComponent, DatePipe, JsonPipe],
  templateUrl: './modulos.component.html',
  styleUrl: './modulos.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ModulosComponent implements OnInit {
  private readonly adminService = inject(AdminService);
  private readonly toastService = inject(ToastService);

  readonly modules = signal<AppModule[]>([]);
  readonly isLoading = signal(true);
  readonly selectedModuleId = signal<string | null>(null);
  readonly hooks = signal<ModuleHook[]>([]);
  readonly hooksLoading = signal(false);
  readonly showConfigModal = signal(false);
  readonly configJson = signal('{}');

  async ngOnInit(): Promise<void> {
    await this.load();
  }

  async load(): Promise<void> {
    this.isLoading.set(true);
    try {
      const data = await this.adminService.listModules();
      this.modules.set(data);
    } catch {
      this.toastService.show({ message: 'Erro ao carregar módulos', type: 'error' });
    } finally {
      this.isLoading.set(false);
    }
  }

  async toggleModule(mod: AppModule): Promise<void> {
    try {
      await this.adminService.updateModule(mod.module_id, {
        is_active: !mod.is_active,
      });
      this.toastService.show({
        message: mod.is_active ? `Módulo "${mod.module_id}" desativado` : `Módulo "${mod.module_id}" ativado`,
        type: 'success',
      });
      await this.load();
    } catch {
      this.toastService.show({ message: 'Erro ao atualizar módulo', type: 'error' });
    }
  }

  async viewHooks(moduleId: string): Promise<void> {
    this.selectedModuleId.set(moduleId);
    this.hooksLoading.set(true);
    try {
      const data = await this.adminService.listModuleHooks(moduleId);
      this.hooks.set(data);
    } catch {
      this.toastService.show({ message: 'Erro ao carregar hooks', type: 'error' });
    } finally {
      this.hooksLoading.set(false);
    }
  }

  openConfig(mod: AppModule): void {
    this.selectedModuleId.set(mod.module_id);
    this.configJson.set(JSON.stringify(mod.config ?? {}, null, 2));
    this.showConfigModal.set(true);
  }

  closeConfigModal(): void {
    this.showConfigModal.set(false);
  }

  async saveConfig(): Promise<void> {
    const moduleId = this.selectedModuleId();
    if (!moduleId) return;
    try {
      const config = JSON.parse(this.configJson());
      await this.adminService.updateModule(moduleId, { config });
      this.toastService.show({ message: 'Configuração salva', type: 'success' });
      this.closeConfigModal();
      await this.load();
    } catch {
      this.toastService.show({ message: 'JSON inválido ou erro ao salvar', type: 'error' });
    }
  }

  moduleLabel(moduleId: string): string {
    const labels: Record<string, string> = {
      vehicles: 'Veículos',
      real_estate: 'Imóveis',
      equipment: 'Equipamentos',
    };
    return labels[moduleId] ?? moduleId;
  }
}
