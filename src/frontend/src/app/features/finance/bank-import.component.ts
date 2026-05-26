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
  BankService,
  ContaBancaria,
  ResumoImportacao,
  LinhaPdfParseada,
} from '../../core/services/bank.service';

@Component({
  selector: 'app-bank-import',
  standalone: true,
  imports: [FormsModule, UiIconComponent, CustomSelectComponent],
  templateUrl: './bank-import.component.html',
  styleUrl: './bank-import.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BankImportComponent implements OnInit {
  private readonly bankService = inject(BankService);

  readonly accounts = signal<ContaBancaria[]>([]);
  readonly selectedAccountId = signal('');
  readonly isUploading = signal(false);
  readonly error = signal('');
  readonly importResult = signal<ResumoImportacao | null>(null);
  readonly isDragOver = signal(false);

  // PDF review
  readonly pdfRows = signal<LinhaPdfParseada[]>([]);
  readonly pdfConfidence = signal(0);
  readonly showPdfReview = signal(false);

  readonly accountOptions = signal<SelectOption[]>([]);

  async ngOnInit(): Promise<void> {
    try {
      const accts = await this.bankService.listAccounts();
      this.accounts.set(accts);
      this.accountOptions.set(
        accts.map((a) => ({ value: a.id, label: `${a.nome}${a.nome_banco ? ' - ' + a.nome_banco : ''}` })),
      );
      if (accts.length > 0) {
        this.selectedAccountId.set(accts[0].id);
      }
    } catch {
      this.error.set('Erro ao carregar contas bancárias');
    }
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.isDragOver.set(true);
  }

  onDragLeave(): void {
    this.isDragOver.set(false);
  }

  async onDrop(event: DragEvent): Promise<void> {
    event.preventDefault();
    this.isDragOver.set(false);
    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      await this.processFile(files[0]);
    }
  }

  async onFileSelected(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      await this.processFile(input.files[0]);
      input.value = '';
    }
  }

  private async processFile(file: File): Promise<void> {
    if (!this.selectedAccountId()) {
      this.error.set('Selecione uma conta bancária primeiro');
      return;
    }

    this.error.set('');
    this.importResult.set(null);
    this.showPdfReview.set(false);

    const ext = file.name.split('.').pop()?.toLowerCase();

    if (ext === 'ofx' || ext === 'qfx') {
      await this.importOfx(file);
    } else if (ext === 'pdf') {
      await this.importPdf(file);
    } else {
      this.error.set('Formato não suportado. Use arquivos .ofx ou .pdf');
    }
  }

  private async importOfx(file: File): Promise<void> {
    this.isUploading.set(true);
    try {
      const result = await this.bankService.importOfx(this.selectedAccountId(), file);
      this.importResult.set(result);
    } catch {
      this.error.set('Erro ao importar arquivo OFX');
    } finally {
      this.isUploading.set(false);
    }
  }

  private async importPdf(file: File): Promise<void> {
    this.isUploading.set(true);
    try {
      const result = await this.bankService.importPdfParse(this.selectedAccountId(), file);
      this.pdfRows.set(result.linhas);
      this.pdfConfidence.set(result.confianca);
      this.showPdfReview.set(true);
    } catch {
      this.error.set('Erro ao processar arquivo PDF');
    } finally {
      this.isUploading.set(false);
    }
  }

  togglePdfRow(index: number): void {
    const rows = [...this.pdfRows()];
    rows[index] = { ...rows[index], selecionada: !rows[index].selecionada };
    this.pdfRows.set(rows);
  }

  selectAllPdfRows(): void {
    this.pdfRows.set(this.pdfRows().map((r) => ({ ...r, selecionada: true })));
  }

  deselectAllPdfRows(): void {
    this.pdfRows.set(this.pdfRows().map((r) => ({ ...r, selecionada: false })));
  }

  async confirmPdfImport(): Promise<void> {
    this.isUploading.set(true);
    this.error.set('');
    try {
      const selected = this.pdfRows().filter((r) => r.selecionada);
      const result = await this.bankService.importPdfConfirm(this.selectedAccountId(), selected);
      this.importResult.set(result);
      this.showPdfReview.set(false);
    } catch {
      this.error.set('Erro ao confirmar importação PDF');
    } finally {
      this.isUploading.set(false);
    }
  }

  cancelPdfReview(): void {
    this.showPdfReview.set(false);
    this.pdfRows.set([]);
  }
}
