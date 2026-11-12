/** Единое московское представление дат и интервалов встречи. */
const dateFormat = new Intl.DateTimeFormat('ru-RU', { timeZone: 'Europe/Moscow', day: 'numeric', month: 'long', year: 'numeric' });
const timeFormat = new Intl.DateTimeFormat('ru-RU', { timeZone: 'Europe/Moscow', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });

export function formatMoscowDate(instant: string) { return dateFormat.format(new Date(instant)); }
export function formatMoscowTime(instant: string) { return timeFormat.format(new Date(instant)); }
export function formatMoscowInterval(slot: { startsAt: string; endsAt: string }) {
  return `${formatMoscowTime(slot.startsAt)}–${formatMoscowTime(slot.endsAt)}`;
}
