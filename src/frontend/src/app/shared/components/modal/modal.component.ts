import {
  Component,
  ChangeDetectionStrategy,
  input,
  output,
  HostListener,
  ElementRef,
  ViewChild,
  AfterViewInit,
  effect,
} from '@angular/core';
import { UiIconComponent } from '../icon/icon.component';

@Component({
  selector: 'app-modal',
  standalone: true,
  imports: [UiIconComponent],
  templateUrl: './modal.component.html',
  styleUrl: './modal.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ModalComponent implements AfterViewInit {
  readonly open = input.required<boolean>();
  readonly size = input<'sm' | 'md' | 'lg' | 'xl' | 'full'>('md');
  readonly title = input<string>('');
  readonly showClose = input<boolean>(true);

  readonly closed = output<void>();

  @ViewChild('modalPanel') modalPanel?: ElementRef<HTMLDivElement>;

  constructor() {
    effect(() => {
      if (this.open() && this.modalPanel) {
        setTimeout(() => this.modalPanel?.nativeElement.focus());
      }
    });
  }

  ngAfterViewInit(): void {
    if (this.open() && this.modalPanel) {
      this.modalPanel.nativeElement.focus();
    }
  }

  @HostListener('document:keydown.escape')
  onEsc(): void {
    if (this.open()) {
      this.closed.emit();
    }
  }

  onBackdropClick(event: MouseEvent): void {
    if (event.target === event.currentTarget) {
      this.closed.emit();
    }
  }

  close(): void {
    this.closed.emit();
  }

  get sizeClass(): string {
    const map: Record<string, string> = {
      sm: 'max-w-sm',
      md: 'max-w-lg',
      lg: 'max-w-2xl',
      xl: 'max-w-4xl',
      full: 'max-w-[90vw]',
    };
    return map[this.size()] ?? 'max-w-lg';
  }
}
