# 🎬 ReelBot: Instagram Trial Reel Automation

> **In one sentence:** I drop car and menswear clips into a Google Drive folder from my phone, and ReelBot edits them, writes the on-screen hooks, posts them as trial reels, and learns from what worked.

🔗 **Code session:** [Instagram trial reel automation system](https://claude.ai/code/session_014xHQ9Rw1Df82M3WnsJ2zDo)

---

## 🚦 Status right now

| Part | Status |
|---|---|
| ✂️ Video editing (cut, 9:16, moody look, text) | ✅ Built + tested |
| ✍️ Hook writing (Claude) | ✅ Built |
| 📊 My Instagram stats (Windsor) | ✅ Connected |
| 📬 Posting trial reels (Meta key) | ✅ Key added |
| 📁 Clip drop folder (Google Drive) | 🟡 Needs sharing + Google key |
| 🛰️ Competitor research (Apify) | 🟡 Needs Apify account + key |
| ⏰ Daily timer | 🔴 Switch on after the first test |

---

## ✅ Next steps (do these in order)

- [ ] **1. Share the Drive folder.** Share → *Anyone with the link* → Viewer
- [ ] **2. Get a Google key.** console.cloud.google.com → new project `ReelBot` → enable **Google Drive API** → Credentials → **API key**
- [ ] **3. Add the Google secret.** Edit environment → Add secret → name `Google Drive`, website `www.googleapis.com`, header `X-Goog-Api-Key`, prefix *empty*
- [ ] **4. Apify.** Sign up at apify.com → Settings → API & Integrations → copy token → secret with website `api.apify.com`, header `Authorization`, prefix `Bearer`
- [ ] **5. Upload 2–3 clips** to the Drive folder from my phone
- [ ] **6. Tell Claude "done"** in the code session, which runs the first test
- [ ] **7. Switch on the daily timer** once the test works

---

## 🔁 How it works (the loop)

```
📱 I upload clips to Google Drive (phone)
        ↓
✂️ ReelBot finds the best moment (the rev / cold start)
   → cuts 8 seconds → vertical → moody look
        ↓
✍️ Claude writes 3 different on-screen hooks per clip
   (based on what's winning for me + competitors)
        ↓
📬 Posts them as TRIAL REELS (non-followers see them first)
        ↓
📊 Checks views, skips, shares a day or two later
        ↓
🧠 Learns what worked → better hooks tomorrow
```

**My only jobs:**
1. 📤 Upload clips
2. 👆 In the Instagram app, tap **"Share to followers"** on trial reels that did well. Instagram won't let a robot do this part.

---

## 📅 Schedule (once switched on)

| When | What happens |
|---|---|
| Every morning | Check stats → edit new clips → write hooks → post |
| Through the day | Post the next videos, spaced out (no spam) |
| Mondays | Competitor research: find reels that blew up and read their on-screen text |

---

## 🧠 What my stats already taught us

| 🔥 Won | 🧊 Flopped |
|---|---|
| "All black spec… always": **1.33M** | "No trends here": ~2–4K (posted 4 times) |
| "Aston Martin sounds….": **292K** | "No trending audio": 3K |
| "DB12 cold starts never sounded better": **173K** | "Tony Soprano is a fashion icon": 1.5K |
| "Zara doing Barbour dupes now?": **107K** | "Barbour dupes in Zara now???": 3K |

**Lessons:**
- 🏎️ "Spec" identity hooks win (all black, Bruce Wayne, no other spec)
- 🔊 Engine-sound hooks win
- 👔 Fashion "dupe" hooks win
- 🚫 Anti-trend hooks flop
- ✏️ **Exact wording matters a lot.** The same Barbour idea did 35× better worded one way, which is why we test 3 hooks per clip

---

## 🔑 Accounts & keys

> ⚠️ Never paste keys into chat. They only go into **Edit environment → Network secrets**.

| What | Where it lives | Notes |
|---|---|---|
| Instagram account | @elliotcameron._ | ID `17841400621094281` |
| Facebook Page | Elliot Cameron | Only exists so the Meta key works |
| Meta business folder | Ell | Holds the Page + Instagram |
| Meta app | ReelBot (developers.facebook.com) | Configuration: ReelBot |
| Secret: `Instagram API` | graph.facebook.com | Authorization / Bearer |
| Secret: `Instagram upload` | rupload.facebook.com | Authorization / OAuth |
| Secret: `Google Drive` | www.googleapis.com | X-Goog-Api-Key / no prefix |
| Secret: `Apify` | api.apify.com | Authorization / Bearer |
| Stats | Windsor.ai | Already connected |
| Code | [GitHub: claude-test](https://github.com/elliotbuglass-blip/claude-test) | Branch `claude/trusting-dijkstra-rrizs1`, private |
| Clip folder | [Google Drive: ReelBot](https://drive.google.com/drive/u/1/folders/1rXjInfkrTN38cSkAtTtVb-8ra4777FQk) | Upload clips here |

---

## ⏰ Important dates

- [ ] **2 December 2026:** remake the Meta key (it expires **12 December 2026**)
  - Graph API Explorer → Generate Access Token → Access Token Debugger → **Extend** → update both Instagram secrets

---

## 💷 Costs

| Thing | Cost |
|---|---|
| Meta / Instagram posting | Free |
| Google Drive | Free |
| Windsor | My existing plan |
| Apify (competitor research) | About $1–2 a week (free plan includes ~$5/month credit) |
| Claude | My Claude plan |

---

## 🎵 Audio rules

- Instagram **doesn't let any app add trending sounds**. Only the Instagram app can.
- **Default:** keep the car's real sound (it does well)
- **Optional:** moody tracks I own the rights to, added to an `audio` folder
- **For a specific trending sound:** post that one manually from the app

---

## 🧭 Decisions made (and why)

| Decision | Why |
|---|---|
| Cloud, not laptop | Clips come from my phone, and the cloud runs daily even when the laptop's off |
| Google Drive for clips | Upload straight from my phone |
| Meta key for posting | Free; supports trial reels |
| Apify for competitors | Automatic and cheap. HikerAPI needed a $50 minimum, and Meta's own tool was blocked for new apps |
| Read **on-screen text**, not post captions | The words on the video are the hook that matters |
| 3 hooks per clip | Wording changes views massively |

---

## 📖 Jargon buster

| Word | Means |
|---|---|
| **Trial reel** | A reel shown to non-followers first, so flops don't hurt my main audience |
| **Hook** | The words on screen in the first second |
| **Outlier** | A competitor reel that did way better than they usually do |
| **API key / token** | A password that lets the robot use a service |
| **Secret** | Where keys are stored safely, so Claude never sees them |
| **Repo / GitHub** | Where the robot's code is saved |
| **Branch** | A copy of the code; ours is `claude/trusting-dijkstra-rrizs1` |

---

## 🆘 If something breaks

1. Open the [code session](https://claude.ai/code/session_014xHQ9Rw1Df82M3WnsJ2zDo)
2. Send a **screenshot** of the error
3. Say "explain simply"

**Common fixes:**
- *"Invalid OAuth access token"* → the Meta key expired → redo it (see dates above)
- *Graph API Explorer error* → check the address says **.facebook.com**, not .instagram.com
- *New chat can't find ReelBot* → it opened the wrong branch → ask it to switch to `claude/trusting-dijkstra-rrizs1`

---

## 💡 Parked ideas (later)

- [ ] Auto-check that trial reels are "graduating" to followers
- [ ] Weekly summary sent to me
- [ ] Try different text styles or positions as another test
- [ ] Add more competitors as I find them
