export type MapCoordinates = {
  latitude: number;
  longitude: number;
};

type GoogleLatLng = {
  lat: number;
  lng: number;
};

type GoogleMapClickEvent = {
  latLng: {
    lat: () => number;
    lng: () => number;
  } | null;
};

type GoogleMapsListener = {
  remove: () => void;
};

export type GoogleMapInstance = {
  addListener: (
    eventName: string,
    handler: (event: GoogleMapClickEvent) => void,
  ) => GoogleMapsListener;
  setCenter: (center: GoogleLatLng) => void;
};

export type GoogleMapMarker = {
  setMap: (map: GoogleMapInstance | null) => void;
  setPosition: (position: GoogleLatLng | null) => void;
};

type GoogleMapsApi = {
  maps: {
    Geocoder: new () => {
      geocode: (
        request: { location: GoogleLatLng },
        callback: (
          results: { formatted_address: string }[] | null,
          status: string,
        ) => void,
      ) => void;
    };
    Map: new (
      element: HTMLElement,
      options: {
        center: GoogleLatLng;
        zoom: number;
        mapTypeControl: boolean;
        fullscreenControl: boolean;
        streetViewControl: boolean;
        clickableIcons: boolean;
      },
    ) => GoogleMapInstance;
    Marker: new (options: {
      map: GoogleMapInstance;
      position?: GoogleLatLng;
    }) => GoogleMapMarker;
  };
};

declare global {
  interface Window {
    google?: GoogleMapsApi;
    __skkuGoogleMapsReady?: () => void;
  }
}

export class GoogleMapsLoadError extends Error {
  constructor(readonly reason: "missing-key" | "load-failed") {
    super(reason);
  }
}

let googleMapsPromise: Promise<GoogleMapsApi> | null = null;

export function loadGoogleMaps(locale: string): Promise<GoogleMapsApi> {
  if (window.google?.maps) return Promise.resolve(window.google);
  if (googleMapsPromise) return googleMapsPromise;

  const apiKey = process.env.EXPO_PUBLIC_GOOGLE_MAPS_WEB_API_KEY;
  if (!apiKey) {
    return Promise.reject(new GoogleMapsLoadError("missing-key"));
  }

  googleMapsPromise = new Promise<GoogleMapsApi>((resolve, reject) => {
    const script = document.createElement("script");
    script.async = true;
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&callback=__skkuGoogleMapsReady&language=${encodeURIComponent(locale)}`;
    window.__skkuGoogleMapsReady = () => {
      delete window.__skkuGoogleMapsReady;
      if (window.google?.maps) {
        resolve(window.google);
      } else {
        googleMapsPromise = null;
        reject(new GoogleMapsLoadError("load-failed"));
      }
    };
    script.onerror = () => {
      delete window.__skkuGoogleMapsReady;
      script.remove();
      googleMapsPromise = null;
      reject(new GoogleMapsLoadError("load-failed"));
    };
    document.head.appendChild(script);
  });

  return googleMapsPromise;
}

export async function reverseGeocode(
  coordinates: MapCoordinates,
  locale: string,
): Promise<string> {
  const google = await loadGoogleMaps(locale);
  return new Promise((resolve, reject) => {
    new google.maps.Geocoder().geocode(
      {
        location: {
          lat: coordinates.latitude,
          lng: coordinates.longitude,
        },
      },
      (results, status) => {
        const address = results?.[0]?.formatted_address;
        if (status === "OK" && address) {
          resolve(address);
        } else {
          reject(new Error(`Google Maps geocoding failed: ${status}`));
        }
      },
    );
  });
}
