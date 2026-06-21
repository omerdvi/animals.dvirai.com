import re

with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# ============================================================
# 1. Fix home title to match instruments style (no span, emojis on both sides)
# ============================================================
html = html.replace(
    '<h1 class="app-title">🦁 <span>חיות</span> 🐻</h1>',
    '<h1 class="app-title">🦁 חיות 🐻</h1>'
)

# Also remove the .app-title span CSS since we no longer have a span
html = html.replace(
    '''    .app-title span {
      display: inline-block;
      animation: bounce 2s infinite;
    }

    @keyframes bounce {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-6px); }
    }
''',
    ''
)

# ============================================================
# 2. Add "מה לא שייך?" button to quiz menu
# ============================================================
html = html.replace(
    '''      <button class="btn-difficulty hard" onclick="App.startQuiz('hard')">
        <span>🧠</span>
        <span>איפה החיה? (מתקדם)</span>
      </button>
    </div>''',
    '''      <button class="btn-difficulty hard" onclick="App.startQuiz('hard')">
        <span>🧠</span>
        <span>איפה החיה? (מתקדם)</span>
      </button>
      <button class="btn-difficulty" style="border-color:#8B5CF6;background:#EDE9FE;color:#5B21B6;" onclick="App.startOddOne()">
        <span>🧐</span>
        <span>מה לא שייך?</span>
      </button>
    </div>'''
)

# ============================================================
# 3. Add TTS (speak) button to animal detail screen
# ============================================================
html = html.replace(
    '''      <button class="btn-nav-animal" onclick="App.prevAnimal()">›</button>
      <button id="btn-play-sound" class="btn-action" onclick="App.playAnimalSound()">🔊</button>
      <button class="btn-nav-animal" onclick="App.nextAnimal()">‹</button>''',
    '''      <button class="btn-nav-animal" onclick="App.prevAnimal()">›</button>
      <button id="btn-play-sound" class="btn-action" onclick="App.playAnimalSound()">🔊</button>
      <button id="btn-tts" class="btn-action" style="border-color:#3B82F6;" onclick="App.speakAnimalName()">🗣️</button>
      <button class="btn-nav-animal" onclick="App.nextAnimal()">‹</button>'''
)

# ============================================================
# 4. Add CSS for TTS button hover/active states (reuse .btn-action)
#    Just add a small rule for btn-tts playing state if needed
# ============================================================
# We'll add CSS later via a style block injection if needed.

# ============================================================
# 5. Add Odd-One-Out screen HTML after the Quiz screen
# ============================================================
html = html.replace(
    '''  <!-- ===== About Screen ===== -->''',
    '''  <!-- ===== Odd One Out Screen ===== -->
  <div id="screen-odd" class="screen">
    <div class="top-bar">
      <button class="btn-back" onclick="App.quitOddOne()">→</button>
      <div id="odd-score" class="quiz-score">⭐ 0</div>
      <button class="btn-home" onclick="App.goHome()">🏠</button>
    </div>
    <div id="odd-prompt" style="font-size:30px;font-weight:800;text-align:center;padding:12px;color:#065F46;flex-shrink:0;">מצא את הזר!</div>
    <div id="odd-options" style="display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:10px;flex:1;padding:0 10px 10px;min-height:0;"></div>
  </div>

  <!-- ===== About Screen ===== -->'''
)

# ============================================================
# 6. Add JavaScript for TTS and Odd-One-Out
# ============================================================
# Add oddOneScore and currentOddQuestion variables after quizHistory
html = html.replace(
    '''    let quizHistory = [];''',
    '''    let quizHistory = [];
    let oddOneScore = 0;
    let currentOddQuestion = null;'''
)

# Add speakAnimalName method after playAnimalSound
html = html.replace(
    '''      playAnimalSound() {
        if (!ANIMAL_DATA || currentCategory === null) return;
        const animal = ANIMAL_DATA.categories[currentCategory].items[currentAnimalIndex];
        playSound(animal.sound, "btn-play-sound");
      },''',
    '''      playAnimalSound() {
        if (!ANIMAL_DATA || currentCategory === null) return;
        const animal = ANIMAL_DATA.categories[currentCategory].items[currentAnimalIndex];
        playSound(animal.sound, "btn-play-sound");
      },

      speakAnimalName() {
        if (!ANIMAL_DATA || currentCategory === null) return;
        const animal = ANIMAL_DATA.categories[currentCategory].items[currentAnimalIndex];
        if ('speechSynthesis' in window) {
          window.speechSynthesis.cancel();
          const utter = new SpeechSynthesisUtterance(animal.name);
          utter.lang = 'he-IL';
          utter.rate = 0.9;
          utter.pitch = 1.1;
          window.speechSynthesis.speak(utter);
        }
      },'''
)

# Add odd-one-out methods after quitQuiz
html = html.replace(
    '''      quitQuiz() {
        this.goBack();
      },

      // ===== About =====
      openAbout() {
        this.showScreen("about");
      }
    };''',
    '''      quitQuiz() {
        this.goBack();
      },

      // ===== Odd One Out =====
      startOddOne() {
        oddOneScore = 0;
        this.updateOddScore();
        this.nextOddQuestion();
        this.showScreen("odd");
      },

      nextOddQuestion() {
        if (!ANIMAL_DATA || !ANIMAL_DATA.categories) return;
        const cats = ANIMAL_DATA.categories;
        if (cats.length < 2) return;

        // Pick main category and odd category
        const mainCatIdx = Math.floor(Math.random() * cats.length);
        let oddCatIdx = Math.floor(Math.random() * cats.length);
        while (oddCatIdx === mainCatIdx) {
          oddCatIdx = Math.floor(Math.random() * cats.length);
        }

        const mainCat = cats[mainCatIdx];
        const oddCat = cats[oddCatIdx];

        // Pick 3 from main, 1 from odd
        const shuffle = arr => [...arr].sort(() => Math.random() - 0.5);
        const mainItems = shuffle(mainCat.items).slice(0, 3).map(i => ({ ...i, catIdx: mainCatIdx, isOdd: false }));
        const oddItem = { ...shuffle(oddCat.items)[0], catIdx: oddCatIdx, isOdd: true };

        const options = shuffle([...mainItems, oddItem]);
        currentOddQuestion = { options, oddIdx: options.findIndex(o => o.isOdd) };

        document.getElementById("odd-prompt").textContent = "מה לא שייך? 🤔";

        const grid = document.getElementById("odd-options");
        grid.innerHTML = "";

        options.forEach((opt, idx) => {
          const btn = document.createElement("button");
          btn.className = "quiz-option";
          btn.innerHTML = `
            <img src="${opt.image}" alt="${opt.name}" loading="lazy">
            <span>${opt.name}</span>
          `;
          btn.addEventListener("click", () => this.handleOddAnswer(idx, btn));
          grid.appendChild(btn);
        });
      },

      handleOddAnswer(idx, btnElement) {
        if (!currentOddQuestion) return;
        const { options, oddIdx } = currentOddQuestion;

        document.querySelectorAll("#odd-options .quiz-option").forEach(b => b.style.pointerEvents = "none");

        if (idx === oddIdx) {
          btnElement.classList.add("correct");
          oddOneScore++;
          this.updateOddScore();
          this.spawnConfetti(btnElement);
          setTimeout(() => this.nextOddQuestion(), 1500);
        } else {
          btnElement.classList.add("wrong");
          document.querySelectorAll("#odd-options .quiz-option").forEach((b, i) => {
            if (i === oddIdx) setTimeout(() => b.classList.add("hint"), 400);
          });
          setTimeout(() => this.nextOddQuestion(), 2000);
        }
      },

      updateOddScore() {
        document.getElementById("odd-score").textContent = `⭐ ${oddOneScore}`;
      },

      quitOddOne() {
        this.goBack();
      },

      // ===== About =====
      openAbout() {
        this.showScreen("about");
      }
    };'''
)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Done! Changes applied.")
