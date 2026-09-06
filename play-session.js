// Small shared interaction pattern, copied into each independently hosted game.
const PlaySession = {
  mode: 'easy', length: 5, hintTimer: null, app: null,
  init(app) {
    this.app = app;
    document.body.insertAdjacentHTML('beforeend', `<div id="screen-complete" class="screen">
      <div class="round-card"><div class="round-stars" aria-hidden="true">⭐ ⭐ ⭐ ⭐ ⭐</div>
      <h2>כל הכבוד! סיימנו סיבוב</h2><p>אפשר לשחק עוד, ואפשר לנוח.</p>
      <button class="round-again" onclick="PlaySession.again()">▶ עוד סיבוב</button>
      <button class="round-home" onclick="App.goHome()">🏠 לבית המשחק</button></div></div>
      <dialog id="parents-dialog"><form method="dialog"><h2>להורים</h2><p id="parents-question"></p>
      <label>התשובה <input id="parents-answer" inputmode="numeric" autocomplete="off" required aria-describedby="parents-error"></label>
      <p id="parents-error" role="status"></p><button type="button" onclick="PlaySession.enterParents()">כניסה</button>
      <button value="cancel" formnovalidate>חזרה למשחק</button></form></dialog>`);
    document.querySelectorAll('.btn-about[onclick="App.openAbout()"]')
      .forEach(b => { b.textContent='להורים'; b.onclick=()=>this.openParents(); });
    for (const event of ['pointerdown','keydown']) document.addEventListener(event, () => this.armHint(), {passive:true});
    document.addEventListener('visibilitychange',()=>{clearTimeout(this.hintTimer);if(!document.hidden)this.armHint()});
  },
  begin(mode) { this.mode=mode; },
  beforeNext(score) {
    if (score < this.length) return true;
    this.app.showScreen('complete',false);
    AudioManager.playUI('complete');
    return false;
  },
  again() {
    // Completion replaces the question; restarting must not create a back stack of old rounds.
    this.app.history=[];
    if(this.mode==='odd') (this.app.startOddOneOut||this.app.startOddOne).call(this.app);
    else this.app.startQuiz(this.mode);
  },
  onScreen() {
    clearTimeout(this.hintTimer);
    document.querySelectorAll('.idle-hint').forEach(e=>e.classList.remove('idle-hint'));
    this.armHint();
  },
  armHint() {
    clearTimeout(this.hintTimer);
    if(document.hidden||!['quiz','odd','odd-quiz'].includes(this.app.currentScreen))return;
    this.hintTimer=setTimeout(()=>this.showHint(),10000);
  },
  showHint() {
    if(document.hidden||!['quiz','odd','odd-quiz'].includes(this.app.currentScreen))return;
    const options=[...document.querySelectorAll('.screen.active .quiz-option:not(:disabled)')];
    if(!options.length)return;
    // Hint at the available actions without choosing the answer for the child.
    options.forEach(b=>b.classList.add('idle-hint'));
    if(!AudioManager.isPlaying)AudioManager.playUI('hint');
  },
  openParents() {
    AudioManager.stop();clearTimeout(this.hintTimer);
    const a=3+Math.floor(Math.random()*5),b=2+Math.floor(Math.random()*5);
    this.parentAnswer=a+b;
    document.getElementById('parents-question').textContent=`כדי לפתוח את פרטי המשחק: כמה הם ${a} ועוד ${b}?`;
    document.getElementById('parents-answer').value='';document.getElementById('parents-error').textContent='';
    document.getElementById('parents-dialog').showModal();
  },
  enterParents() {
    const input=document.getElementById('parents-answer');
    if(input.value.trim()!==''&&Number(input.value)===this.parentAnswer){document.getElementById('parents-dialog').close();this.app.openAbout()}
    else document.getElementById('parents-error').textContent='נסו שוב';
  }
};
