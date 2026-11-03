document.querySelectorAll('form[method="post"]').forEach(form => {
  form.addEventListener('submit', () => {
    if (!form.checkValidity()) return;
    const button = form.querySelector('button[type="submit"], button:not([type])');
    if (button) { button.disabled = true; button.dataset.original = button.textContent; button.textContent = 'Saving…'; }
  });
});
window.addEventListener('pageshow', () => document.querySelectorAll('button[data-original]').forEach(b => { b.disabled=false; b.textContent=b.dataset.original; }));
const errors = document.querySelector('.form-error');
if (errors) errors.focus();
const form = document.querySelector('[data-slot-url]');
if (form) {
  const date = form.querySelector('[data-slots-date]'), hour=form.querySelector('[data-slots-hour]'), status=document.querySelector('#slot-status');
  let generation=0;
  async function update() {
    if (!date.value) return;
    const current=++generation;
    status.textContent='Checking available slots…';
    const url=new URL(form.dataset.slotUrl,location.origin); url.searchParams.set('day',date.value);
    try {
      const response=await fetch(url); if (!response.ok) throw new Error();
      const data=await response.json(); if (current!==generation) return;
      let available=0;
      for (const option of hour.options) {
        const slot=data.slots.find(s=>s.value===option.value);
        option.disabled=!slot?.available; option.textContent=slot ? slot.label+(slot.available?'':' · unavailable') : option.value;
        if (slot?.available) available++;
      }
      if (hour.selectedOptions[0]?.disabled) hour.value=Array.from(hour.options).find(o=>!o.disabled)?.value || '';
      status.textContent=available ? `${available} available slot${available===1?'':'s'} for the assigned Judge. Availability is checked again when you save.` : 'No slots available on this day. Choose another weekday.';
    } catch { if(current===generation) status.textContent='Availability could not be loaded. You can retry by choosing the date again; the server checks conflicts when saving.'; }
  }
  date.addEventListener('change',update); update();
}
