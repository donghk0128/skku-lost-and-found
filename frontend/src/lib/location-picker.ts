export type PickedLocation = {
  address: string;
  latitude: number;
  longitude: number;
};

const listeners = new Set<(location: PickedLocation) => void>();

export function pickLocation(location: PickedLocation) {
  listeners.forEach((listener) => listener(location));
}

export function onLocationPicked(listener: (location: PickedLocation) => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
