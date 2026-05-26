import {
  Component,
  ChangeDetectionStrategy,
  signal,
} from '@angular/core';
import { UiIconComponent } from '../../../shared/components/icon/icon.component';

interface PreviewRow {
  nome_completo: string;
  cpf_cnpj: string;
  email: string;
  telefone: string;
  status: string;
}

@Component({
  selector: 'app-importar-clientes',
  standalone: true,
  imports: [UiIconComponent],
  templateUrl: './importar-clientes.component.html',
  styleUrl: './importar-clientes.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ImportarClientesComponent {
  readonly selectedFile = signal<File | null>(null);
  readonly previewRows = signal<PreviewRow[]>([]);
  readonly isParsingFile = signal(false);
  readonly importStatus = signal<'idle' | 'parsing' | 'ready' | 'importing' | 'done'>('idle');
  readonly errorMessage = signal('');

  onFileSelect(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];

    if (!file) return;

    const validTypes = [
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-excel',
      'text/csv',
    ];
    const validExtensions = ['.xlsx', '.xls', '.csv'];
    const extension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();

    if (!validTypes.includes(file.type) && !validExtensions.includes(extension)) {
      this.errorMessage.set('Formato inválido. Use arquivos .xlsx, .xls ou .csv');
      return;
    }

    this.errorMessage.set('');
    this.selectedFile.set(file);
    this.importStatus.set('parsing');
    this.isParsingFile.set(true);

    // Simulate parsing - in real app would use a library like xlsx
    setTimeout(() => {
      this.previewRows.set([
        {
          nome_completo: 'Exemplo - João Silva',
          cpf_cnpj: '12345678901',
          email: 'joao@exemplo.com',
          telefone: '11999998888',
          status: 'ativo',
        },
        {
          nome_completo: 'Exemplo - Maria Santos',
          cpf_cnpj: '98765432100',
          email: 'maria@exemplo.com',
          telefone: '21988887777',
          status: 'ativo',
        },
      ]);
      this.isParsingFile.set(false);
      this.importStatus.set('ready');
    }, 1000);
  }

  clearFile(): void {
    this.selectedFile.set(null);
    this.previewRows.set([]);
    this.importStatus.set('idle');
    this.errorMessage.set('');
  }

  startImport(): void {
    // Backend not ready — show placeholder message
    this.importStatus.set('importing');
    setTimeout(() => {
      this.importStatus.set('done');
    }, 500);
  }
}
