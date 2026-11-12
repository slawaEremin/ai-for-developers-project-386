/** Незавершённая попытка принадлежит текущей вкладке, а не текущему окну дат. */
export type BookingAttempt = { key: string; meetingTypeId: string; startsAt: string; meetingTypeName: string; durationMinutes: number };
const storageKey = 'calendar.unfinishedBooking';
export function restoreAttempt(): BookingAttempt | null {
  const raw = sessionStorage.getItem(storageKey);
  if (!raw) return null;
  const value = JSON.parse(raw) as BookingAttempt;
  if (!/^[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$/i.test(value.key)
    || typeof value.meetingTypeId !== 'string' || !value.meetingTypeId
    || typeof value.meetingTypeName !== 'string' || !Number.isInteger(value.durationMinutes)
    || value.durationMinutes < 1 || value.durationMinutes > 540
    || typeof value.startsAt !== 'string' || !Number.isFinite(Date.parse(value.startsAt))) throw new Error('Unreadable booking attempt');
  return value;
}
export function saveAttempt(value: BookingAttempt) { sessionStorage.setItem(storageKey, JSON.stringify(value)); }
export function clearAttempt() { sessionStorage.removeItem(storageKey); }
