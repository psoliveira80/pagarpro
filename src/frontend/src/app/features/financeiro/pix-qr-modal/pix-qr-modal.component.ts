import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  input,
  output,
  OnInit,
} from '@angular/core';
import { UiIconComponent } from '../../../shared/components/icon/icon.component';
import { ModalComponent } from '../../../shared/components/modal/modal.component';
import {
  ReceivableService,
  PixQrResponse,
} from '../../../core/services/receivable.service';

@Component({
  selector: 'app-pix-qr-modal',
  standalone: true,
  imports: [UiIconComponent, ModalComponent],
  templateUrl: '../pix-qr-modal/pix-qr-modal.component.html',
  styleUrl: '../pix-qr-modal/pix-qr-modal.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PixQrModalComponent implements OnInit {
  private readonly receivableService = inject(ReceivableService);

  readonly open = input(true);
  readonly receivableId = input.required<string>();
  readonly closed = output<void>();

  readonly isLoading = signal(true);
  readonly pixData = signal<PixQrResponse | null>(null);
  readonly copied = signal(false);

  ngOnInit(): void {
    this.loadPixQr();
  }

  async loadPixQr(): Promise<void> {
    this.isLoading.set(true);
    try {
      const data = await this.receivableService.getPixQr(this.receivableId());
      this.pixData.set(data);
    } catch {
      this.pixData.set(null);
    } finally {
      this.isLoading.set(false);
    }
  }

  async copyBrCode(): Promise<void> {
    const data = this.pixData();
    if (!data) return;
    try {
      await navigator.clipboard.writeText(data.brcode);
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 2000);
    } catch {
      // Clipboard not available
    }
  }

  close(): void {
    this.closed.emit();
  }
}
