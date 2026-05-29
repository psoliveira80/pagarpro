import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
  effect,
  HostListener,
  ElementRef,
} from '@angular/core';
import {
  RouterOutlet,
  RouterLink,
  RouterLinkActive,
  Router,
  NavigationEnd,
} from '@angular/router';
import { filter } from 'rxjs';
import { toSignal } from '@angular/core/rxjs-interop';
import { UiIconComponent } from '../icon/icon.component';
import { AiChatComponent } from '../ai-chat/ai-chat.component';
import { CommandPaletteComponent } from '../command-palette/command-palette.component';
import { ThemeService } from '../../../core/services/theme.service';
import { AuthService } from '../../../core/services/auth.service';
import { CommandPaletteService } from '../command-palette/command-palette.service';
import { environment } from '../../../../environments/environment';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, UiIconComponent, AiChatComponent, CommandPaletteComponent],
  templateUrl: './app-shell.component.html',
  styleUrl: './app-shell.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppShellComponent {
  private readonly themeService = inject(ThemeService);
  private readonly router = inject(Router);
  private readonly elementRef = inject(ElementRef);
  readonly authService = inject(AuthService);
  readonly paletteService = inject(CommandPaletteService);

  readonly productName = environment.productName;
  readonly sidebarCollapsed = signal(false);
  readonly mobileSidebarOpen = signal(false);
  readonly settingsSidebarOpen = signal(false);
  readonly profileSidebarOpen = signal(false);
  readonly userMenuOpen = signal(false);
  readonly currentTheme = this.themeService.theme;
  readonly themeIcon = this.themeService.themeIcon;

  readonly currentUser = this.authService.currentUser;

  readonly isAdmin = computed(() => {
    const user = this.currentUser();
    return user?.roles?.some((r) => r.toLowerCase() === 'admin') ?? false;
  });

  readonly userInitials = computed(() => {
    const user = this.currentUser();
    if (!user?.nome_completo) return '?';
    const parts = user.nome_completo.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return parts[0].substring(0, 2).toUpperCase();
  });

  private readonly navigationEnd = toSignal(
    this.router.events.pipe(filter((e) => e instanceof NavigationEnd)),
  );

  readonly profileMenuItems = [
    {
      section: 'Conta',
      items: [
        { label: 'Meu Perfil', route: '/sistema/perfil' },
        { label: 'Preferências', route: '/sistema/preferencias' },
        { label: 'Segurança', route: '/sistema/seguranca' },
      ],
    },
  ];

  readonly settingsMenuItems = [
    {
      section: 'Acesso',
      items: [
        { label: 'Usuários', route: '/sistema/configuracoes/usuarios' },
        { label: 'Roles & Permissões', route: '/sistema/configuracoes/papeis' },
      ],
    },
    {
      section: 'Canais',
      items: [
        { label: 'WhatsApp', route: '/sistema/configuracoes/canais/whatsapp' },
      ],
    },
    {
      section: 'Parâmetros',
      items: [
        { label: 'Financeiro', route: '/sistema/configuracoes/financeiro' },
        { label: 'Contratos', route: '/sistema/configuracoes/contratos' },
        { label: 'Integrações', route: '/sistema/configuracoes/integracoes' },
        { label: 'Módulos', route: '/sistema/configuracoes/modulos' },
      ],
    },
    {
      section: 'Inteligência',
      items: [
        { label: 'Agente IA', route: '/sistema/configuracoes/agente' },
      ],
    },
    {
      section: 'Sistema',
      items: [
        { label: 'Log de Auditoria', route: '/sistema/configuracoes/log-auditoria' },
      ],
    },
  ];

  constructor() {
    // Auto-open correct sidebar if initial URL matches
    const initialUrl = this.router.url;
    if (initialUrl.startsWith('/sistema/configuracoes/')) {
      this.settingsSidebarOpen.set(true);
    } else if (initialUrl.startsWith('/sistema/perfil') || initialUrl.startsWith('/sistema/preferencias') || initialUrl.startsWith('/sistema/seguranca')) {
      this.profileSidebarOpen.set(true);
    }

    effect(() => {
      const nav = this.navigationEnd();
      if (nav) {
        this.mobileSidebarOpen.set(false);

        const url = this.router.url;
        if (url.startsWith('/sistema/configuracoes/')) {
          this.settingsSidebarOpen.set(true);
        } else if (url.startsWith('/sistema/perfil') || url.startsWith('/sistema/preferencias') || url.startsWith('/sistema/seguranca')) {
          this.profileSidebarOpen.set(true);
        }
      }
    });
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    const target = event.target as HTMLElement;
    const userMenuEl = this.elementRef.nativeElement.querySelector(
      '[data-user-menu]',
    );
    if (userMenuEl && !userMenuEl.contains(target)) {
      this.userMenuOpen.set(false);
    }
  }

  toggleSidebar(): void {
    this.sidebarCollapsed.update((v) => !v);
  }

  toggleMobileSidebar(): void {
    this.mobileSidebarOpen.update((v) => !v);
  }

  closeMobileSidebar(): void {
    this.mobileSidebarOpen.set(false);
  }

  toggleSettingsSidebar(): void {
    if (this.settingsSidebarOpen()) {
      this.closeSettingsSidebar();
    } else {
      this.profileSidebarOpen.set(false);
      this.settingsSidebarOpen.set(true);
      this.router.navigate(['/sistema/configuracoes/usuarios']);
    }
  }

  closeSettingsSidebar(): void {
    this.settingsSidebarOpen.set(false);
    this.router.navigate(['/sistema/dashboard']);
  }

  openProfileSidebar(): void {
    this.settingsSidebarOpen.set(false);
    this.userMenuOpen.set(false);
    this.profileSidebarOpen.set(true);
    this.router.navigate(['/sistema/perfil']);
  }

  closeProfileSidebar(): void {
    this.profileSidebarOpen.set(false);
    this.router.navigate(['/sistema/dashboard']);
  }

  toggleUserMenu(): void {
    this.userMenuOpen.update((v) => !v);
  }

  toggleTheme(): void {
    this.themeService.toggle();
  }

  logout(): void {
    this.authService.logout();
  }

  isSettingsRouteActive(route: string): boolean {
    return this.router.url === route;
  }

  isProfileRouteActive(route: string): boolean {
    return this.router.url === route;
  }
}
