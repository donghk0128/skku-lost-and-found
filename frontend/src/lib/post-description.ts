// Preserve the existing backend schema while distinguishing item features from body text.
const marker = "\n\n[물품 특징]\n";
export function splitPostDescription(value: string) {
  const index = value.lastIndexOf(marker);
  return index < 0
    ? { body: value, features: "" }
    : {
        body: value.slice(0, index),
        features: value.slice(index + marker.length),
      };
}
export function joinPostDescription(body: string, features: string) {
  return body.trim() + (features.trim() ? marker + features.trim() : "");
}
