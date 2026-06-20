export function systolicToAngle(systolic, min = 90, max = 180) {
  const clamped = Math.min(max, Math.max(min, systolic || min));
  return ((clamped - min) / (max - min)) * 180;
}

export function bpSegment(systolic) {
  if (systolic < 120) return 'teal';
  if (systolic < 140) return 'amber';
  return 'grey';
}
