// One reusable media element keeps playback and cancellation consistent across screens.
const AudioManager = {
  current: new Audio(), isPlaying: false, onEnd: null, version: 0, muted: false,
  init() {
    try { this.muted = localStorage.getItem('sound-muted') === 'true'; } catch {}
    this.updateToggle();
    document.addEventListener('visibilitychange', () => { if (document.hidden) this.stop(); });
    window.addEventListener('pagehide', () => this.stop());
  },
  updateToggle() {
    document.querySelectorAll('[data-audio-toggle]').forEach(b => {
      b.textContent = this.muted ? '🔇 הפעלת שמע' : '🔊 השתקה';
      b.setAttribute('aria-pressed', String(this.muted));
    });
  },
  toggleMute() {
    this.muted = !this.muted;
    this.stop();
    try { localStorage.setItem('sound-muted', String(this.muted)); } catch {}
    this.updateToggle();
  },
  play(src, onEnd) { this.playSequence([src], onEnd); },
  playSequence(sources, onEnd, onNext) {
    this.stop();
    if (this.muted || document.hidden) { if (onEnd) onEnd(); return; }
    const token = this.version;
    const audio = this.current;
    this.onEnd = onEnd || null;
    const status = document.getElementById('audio-status');
    if (status) status.textContent = '';
    let index = 0;
    const finish = (failed = false) => {
      if (token !== this.version) return;
      this.stop();
      if (failed && status) status.textContent = 'לא הצלחנו להשמיע. לחצו שוב על כפתור השמע.';
    };
    const next = () => {
      if (token !== this.version) return;
      if (index >= sources.length) { finish(); return; }
      const src = sources[index++];
      audio.src = src + (src.includes('?') ? '&' : '?') + 'v=20260906';
      audio.onended = next;
      audio.onerror = () => finish(true);
      this.isPlaying = true;
      if (index > 1 && onNext) onNext();
      audio.play().catch(() => finish(true));
    };
    next();
  },
  stop() {
    this.version++;
    this.current.onended = this.current.onerror = null;
    this.current.pause();
    this.isPlaying = false;
    const done = this.onEnd; this.onEnd = null;
    document.querySelectorAll('.btn-action.playing').forEach(b => b.classList.remove('playing'));
    if (done) done();
  },
  playUI(name, onEnd) { this.play(`voice/ui/${name}.mp3`, onEnd); },
};
