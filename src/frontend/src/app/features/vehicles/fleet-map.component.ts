import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  OnInit,
  OnDestroy,
  ElementRef,
  viewChild,
  afterNextRender,
} from '@angular/core';
import { UiIconComponent } from '../../shared/components/icon/icon.component';
import {
  VehicleService,
  Veiculo,
} from '../../core/services/vehicle.service';
import * as L from 'leaflet';

@Component({
  selector: 'app-fleet-map',
  standalone: true,
  imports: [UiIconComponent],
  templateUrl: './fleet-map.component.html',
  styleUrl: './fleet-map.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FleetMapComponent implements OnInit, OnDestroy {
  private readonly vehicleService = inject(VehicleService);

  readonly mapContainer = viewChild<ElementRef<HTMLDivElement>>('mapContainer');
  readonly vehicles = signal<Veiculo[]>([]);
  readonly selectedVehicle = signal<Veiculo | null>(null);
  readonly isLoading = signal(false);
  readonly sidePanelOpen = signal(true);

  private map: L.Map | null = null;
  private markers: L.Marker[] = [];
  private mapReady = false;

  constructor() {
    afterNextRender(() => {
      this.mapReady = true;
      this.initMap();
    });
  }

  ngOnInit(): void {
    this.loadVehicles();
  }

  ngOnDestroy(): void {
    if (this.map) {
      this.map.remove();
      this.map = null;
    }
  }

  private initMap(): void {
    const container = this.mapContainer();
    if (!container || !this.mapReady) return;

    // Fix Leaflet default icon paths
    const iconDefault = L.icon({
      iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
      iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
      shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
      iconSize: [25, 41],
      iconAnchor: [12, 41],
      popupAnchor: [1, -34],
      shadowSize: [41, 41],
    });
    L.Marker.prototype.options.icon = iconDefault;

    this.map = L.map(container.nativeElement).setView([-23.5505, -46.6333], 11);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(this.map);
  }

  private updateMarkers(): void {
    if (!this.map) return;

    // Clear existing markers
    this.markers.forEach((m) => m.remove());
    this.markers = [];

    // Location data is no longer available on the Veiculo model.
    // Markers will be added when a tracking/location source is integrated.
  }

  async loadVehicles(): Promise<void> {
    this.isLoading.set(true);
    try {
      const response = await this.vehicleService.list({ size: 500 });
      this.vehicles.set(response.items);
      this.updateMarkers();
    } catch {
      this.vehicles.set([]);
    } finally {
      this.isLoading.set(false);
    }
  }

  selectVehicle(vehicle: Veiculo): void {
    this.selectedVehicle.set(vehicle);
  }

  toggleSidePanel(): void {
    this.sidePanelOpen.update((v) => !v);
  }

  formatPlate(plate: string): string {
    if (plate.length === 7) {
      return `${plate.slice(0, 3)}-${plate.slice(3)}`;
    }
    return plate;
  }

  statusLabel(status: string): string {
    const map: Record<string, string> = {
      ativo: 'Ativo',
      manutencao: 'Manutenção',
      bloqueado: 'Bloqueado',
      inativo: 'Inativo',
    };
    return map[status] ?? status;
  }

  statusClass(status: string): string {
    const map: Record<string, string> = {
      ativo: 'bg-green-500/20 text-green-400',
      manutencao: 'bg-yellow-500/20 text-yellow-400',
      bloqueado: 'bg-red-500/20 text-red-400',
      inativo: 'bg-gray-500/20 text-gray-400',
    };
    return map[status] ?? 'bg-gray-500/20 text-gray-400';
  }

  statusDotClass(status: string): string {
    const map: Record<string, string> = {
      ativo: 'bg-green-400',
      manutencao: 'bg-yellow-400',
      bloqueado: 'bg-red-400',
      inativo: 'bg-gray-400',
    };
    return map[status] ?? 'bg-gray-400';
  }
}
