export type DemoPlanId = "square_room" | "two_segments" | "room_door_gap";

export interface DemoPlanMeta {
  id: DemoPlanId;
  file: string;
  label: string;
  description: string;
}

export const DEMO_PLANS: DemoPlanMeta[] = [
  {
    id: "square_room",
    file: "demo_square_room.dxf",
    label: "Basit kare oda",
    description: "Tek kapalı dikdörtgen — pen-safe derleme demosu",
  },
  {
    id: "two_segments",
    file: "demo_two_segments.dxf",
    label: "İki kopuk çizgi",
    description: "Kopuk segmentler — kalem kaldırma davranışı",
  },
  {
    id: "room_door_gap",
    file: "demo_room_door_gap.dxf",
    label: "Oda + kapı boşluğu",
    description: "Alt duvarda kapı açıklığı olan oda",
  },
];

export function getDemoPlanMeta(id: DemoPlanId): DemoPlanMeta {
  const plan = DEMO_PLANS.find((p) => p.id === id);
  if (!plan) throw new Error("Demo plan bulunamadı.");
  return plan;
}

export async function loadDemoPlan(id: DemoPlanId): Promise<File> {
  const plan = getDemoPlanMeta(id);

  const res = await fetch(`/demo/${plan.file}`);
  if (!res.ok) {
    throw new Error(`Demo dosyası yüklenemedi: ${plan.file}`);
  }
  const blob = await res.blob();
  return new File([blob], plan.file, { type: "application/dxf" });
}
